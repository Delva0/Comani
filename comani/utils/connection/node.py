#!/usr/bin/env python
"""
Unified execution node abstraction (Local/Remote).
"""
from __future__ import annotations

import abc
import base64
import inspect
import logging
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
import textwrap
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Optional, Union

from comani.utils.connection.ssh import SSHConnection
from comani.config import get_config

logger = logging.getLogger(__name__)

@dataclass
class ExecResult:
    stdout: str
    stderr: str
    code: int

    @property
    def ok(self) -> bool:
        return self.code == 0

class Node(abc.ABC):
    def __init__(self, host: str):
        self.host = host

    @abc.abstractmethod
    def exec_shell(self, cmd: str, workdir: Optional[str] = None) -> ExecResult: ...

    @abc.abstractmethod
    def exec_python(self, target: Union[str, Callable], args: tuple = (), kwargs: dict = None, isolate: bool = True) -> Any: ...

    @abc.abstractmethod
    def put(self, local_path: str, remote_path: str) -> None: ...

    @abc.abstractmethod
    def get(self, remote_path: str, local_path: str) -> None: ...

    @abc.abstractmethod
    def exists(self, path: str) -> bool: ...

    @abc.abstractmethod
    def close(self) -> None: ...

    def __enter__(self) -> Node: return self
    def __exit__(self, exc_type, exc_val, exc_tb): self.close()

class LocalNode(Node):
    def __init__(self):
        super().__init__("localhost")

    def exec_shell(self, cmd: str, workdir: Optional[str] = None) -> ExecResult:
        try:
            r = subprocess.run(
                cmd, shell=True, cwd=workdir,
                capture_output=True, text=True, encoding='utf-8'
            )
            return ExecResult(r.stdout.strip(), r.stderr.strip(), r.returncode)
        except Exception as e:
            return ExecResult("", str(e), -1)

    def exec_python(self, target: Union[str, Callable], args: tuple = (), kwargs: dict = None, isolate: bool = True) -> Any:
        kwargs = kwargs or {}

        if callable(target) and not isolate:
            return target(*args, **kwargs)

        script = _gen_bootstrap(target, args, kwargs)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(script)
            fname = f.name

        try:
            r = subprocess.run([sys.executable, fname], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError(f"Local python execution failed: {r.stderr}")
            return r.stdout.strip()
        finally:
            if os.path.exists(fname):
                os.remove(fname)

    def put(self, local_path: str, remote_path: str) -> None:
        if os.path.abspath(local_path) != os.path.abspath(remote_path):
            shutil.copy2(local_path, remote_path)

    def get(self, remote_path: str, local_path: str) -> None:
        if os.path.abspath(remote_path) != os.path.abspath(local_path):
            shutil.copy2(remote_path, local_path)

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def close(self) -> None: pass

class RemoteNode(Node):
    def __init__(self, host: str, user: str, port: int, key_path: str = None, password: str = None):
        super().__init__(host)
        self.conn = SSHConnection(host, port, user, key_path, password)
        self.conn.connect()
        self._tmp = "/tmp/comani_node_exec"
        self.conn.exec(f"mkdir -p {self._tmp}", check=False)

    def exec_shell(self, cmd: str, workdir: Optional[str] = None) -> ExecResult:
        c = f"cd {workdir} && {cmd}" if workdir else cmd
        out, err, code = self.conn.exec(c, check=False)
        return ExecResult(out, err, code)

    def exec_python(self, target: Union[str, Callable], args: tuple = (), kwargs: dict = None, isolate: bool = True) -> Any:
        kwargs = kwargs or {}
        script = _gen_bootstrap(target, args, kwargs)

        rname = f"{uuid.uuid4()}.py"
        rpath = f"{self._tmp}/{rname}"

        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(script)
            lpath = f.name

        try:
            self.put(lpath, rpath)
            res = self.exec_shell(f"python3 {rpath}")
            if not res.ok:
                raise RuntimeError(f"Remote python execution failed: {res.stderr}")
            return res.stdout.strip()
        finally:
            if os.path.exists(lpath):
                os.remove(lpath)
            self.exec_shell(f"rm -f {rpath}")

    def put(self, local_path: str, remote_path: str) -> None:
        self.conn.sftp.put(local_path, remote_path)

    def get(self, remote_path: str, local_path: str) -> None:
        self.conn.sftp.get(remote_path, local_path)

    def exists(self, path: str) -> bool:
        res = self.exec_shell(f"test -f '{path}'")
        return res.ok

    def close(self) -> None:
        self.conn.close()

def _gen_bootstrap(target: Union[str, Callable], args: tuple, kwargs: dict) -> str:
    p_data = base64.b64encode(pickle.dumps({'a': args, 'k': kwargs})).decode('ascii')

    if callable(target):
        try:
            src = textwrap.dedent(inspect.getsource(target))
            call = f"{target.__name__}(*d['a'], **d['k'])"
        except OSError:
            raise ValueError("Cannot inspect source of function")
    else:
        src = target
        call = "None"

    return f"""
import sys, os, pickle, base64
{src}
if __name__ == '__main__':
    d = pickle.loads(base64.b64decode('{p_data}'))
    try:
        res = {call}
        if res is not None: print(res)
    except Exception as e:
        sys.stderr.write(str(e))
        sys.exit(1)
"""

@lru_cache(maxsize=1)  # 如果paramiko提供了ssh复用+连接失败自动创建新ssh conn，那么这里不再需要缓存
def connect_node(
    host: str = None,
    ssh_user: str = "root",
    ssh_port: int = 22,
    ssh_key: str = None,
    ssh_password: str = None,
    force_ssh: bool = False
) -> Node:
    """Factory to create LocalNode or RemoteNode."""
    is_local_host = not host or host.lower() in ("localhost", "127.0.0.1")

    if is_local_host and not force_ssh:
        logger.debug("Connecting to LocalNode")
        return LocalNode()

    logger.debug(f"Connecting to RemoteNode: {host}")
    return RemoteNode(host or "127.0.0.1", ssh_user, ssh_port, ssh_key, ssh_password)


def get_node() -> Node:
    """Get or create a cached Node instance based on config."""
    config = get_config()
    return connect_node(
        config.host,
        config.user,
        config.port,
        ssh_key=config.ssh_key,
        ssh_password=config.password.get_secret_value() if config.password else None
    )
