#!/usr/bin/env python
"""
Remote infrastructure utilities for SSH connections and port forwarding.

This module provides low-level SSH tunnel functionality used by remote downloaders.
"""

from __future__ import annotations

import logging
import os
import socket
import select
import threading
import atexit
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import paramiko

from comani.config import get_config

logger = logging.getLogger(__name__)


class SSHTunnel:
    """
    SSH tunnel using paramiko native port forwarding.
    Creates a local port that forwards to a remote host:port via SSH.

    Example:
        >>> with SSHTunnel(ssh_client, "127.0.0.1", 6800) as tunnel:
        ...     print(f"Local port: {tunnel.local_bind_port}")
        ...     # Connect to localhost:{tunnel.local_bind_port} to reach remote:6800
    """

    def __init__(
        self,
        ssh_client: "paramiko.SSHClient",
        remote_host: str,
        remote_port: int,
    ):
        """
        Initialize SSH tunnel.

        Args:
            ssh_client: Connected paramiko SSH client
            remote_host: Remote host to tunnel to (usually "127.0.0.1" for localhost on remote)
            remote_port: Remote port to tunnel to
        """
        self._ssh = ssh_client
        self._remote_host = remote_host
        self._remote_port = remote_port
        self._local_port: int = 0
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._client_threads: list[threading.Thread] = []

        self._start()

    def _start(self) -> None:
        """Start the tunnel."""
        # Find free local port
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind(("127.0.0.1", 0))
        self._local_port = self._server_socket.getsockname()[1]
        self._server_socket.listen(5)
        self._server_socket.settimeout(1.0)

        self._running = True
        self._thread = threading.Thread(target=self._forward_handler, daemon=True)
        self._thread.start()

        logger.debug(
            "SSH tunnel started: localhost:%d -> %s:%d",
            self._local_port,
            self._remote_host,
            self._remote_port,
        )

    def _forward_handler(self) -> None:
        """Accept connections and forward them through SSH."""
        while self._running:
            try:
                client_socket, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            try:
                transport = self._ssh.get_transport()
                if transport is None:
                    client_socket.close()
                    continue

                channel = transport.open_channel(
                    "direct-tcpip",
                    (self._remote_host, self._remote_port),
                    client_socket.getpeername(),
                )
            except Exception as e:
                logger.debug("Failed to open channel: %s", e)
                client_socket.close()
                continue

            # Start data forwarding thread
            thread = threading.Thread(
                target=self._tunnel_data,
                args=(client_socket, channel),
                daemon=True,
            )
            thread.start()
            self._client_threads.append(thread)

    def _tunnel_data(self, client_socket: socket.socket, channel) -> None:
        """Forward data between local socket and SSH channel."""
        try:
            while self._running:
                r, _, _ = select.select([client_socket, channel], [], [], 1.0)
                if client_socket in r:
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    channel.send(data)
                if channel in r:
                    data = channel.recv(4096)
                    if not data:
                        break
                    client_socket.send(data)
        except Exception as e:
            logger.debug("Tunnel data error: %s", e)
        finally:
            try:
                channel.close()
            except Exception:
                pass
            try:
                client_socket.close()
            except Exception:
                pass

    @property
    def local_bind_port(self) -> int:
        """Get the local port number."""
        return self._local_port

    @property
    def is_running(self) -> bool:
        """Check if tunnel is running."""
        return self._running

    def stop(self) -> None:
        """Stop the tunnel and clean up resources."""
        self._running = False

        if self._server_socket:
            try:
                self._server_socket.close()
            except Exception:
                pass
            self._server_socket = None

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        # Clean up client threads
        for thread in self._client_threads:
            if thread.is_alive():
                thread.join(timeout=1)
        self._client_threads.clear()

        logger.debug("SSH tunnel stopped")

    def __enter__(self) -> "SSHTunnel":
        return self

    def __exit__(self, *args) -> None:
        self.stop()


class SSHConnection:
    """
    Managed SSH connection with SFTP support.

    Example:
        >>> with SSHConnection("remote.host", user="root") as conn:
        ...     stdout, stderr, code = conn.exec("ls -la")
        ...     conn.sftp.listdir("/")
    """

    def __init__(
        self,
        host: str,
        port: int = 22,
        user: str = "root",
        key_path: str | None = None,
        password: str | None = None,
        timeout: int = 30,
    ):
        """
        Initialize SSH connection.

        Args:
            host: Remote hostname or IP
            port: SSH port (default: 22)
            user: SSH username (default: "root")
            key_path: Path to private key file (default: ~/.ssh/id_rsa)
            password: SSH password (default: None)
            timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.user = user
        self.key_path = key_path or os.path.expanduser("~/.ssh/id_rsa")
        self.password = password
        self.timeout = timeout

        self._ssh: "paramiko.SSHClient | None" = None
        self._sftp: "paramiko.SFTPClient | None" = None


    @property
    def client(self) -> "paramiko.SSHClient":
        """Get SSH client (must be connected)."""
        if self._ssh is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._ssh

    @property
    def sftp(self) -> "paramiko.SFTPClient":
        """Get SFTP client (must be connected)."""
        if self._sftp is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return self._sftp

    @property
    def is_connected(self) -> bool:
        """Check if connected and transport is active."""
        if self._ssh is None:
            return False
        transport = self._ssh.get_transport()
        return transport is not None and transport.is_active()

    def connect(self) -> None:
        """Establish SSH connection or Re-connect if dead."""
        if self.is_connected:
            return

        # Clean up old dead connection
        if self._ssh is not None:
            self.close()

        import paramiko

        self._ssh = paramiko.SSHClient()
        self._ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Prepare connection arguments
        connect_kwargs = {
            "hostname": self.host,
            "port": self.port,
            "username": self.user,
            "timeout": self.timeout,
            "allow_agent": True,
            "look_for_keys": True,
        }

        if self.password:
            connect_kwargs["password"] = self.password

        if self.key_path and os.path.exists(self.key_path):
            connect_kwargs["key_filename"] = self.key_path

        logger.info("Connecting to %s@%s:%d", self.user, self.host, self.port)
        try:
            self._ssh.connect(**connect_kwargs)
        except (paramiko.ssh_exception.AuthenticationException, paramiko.ssh_exception.BadAuthenticationType) as e:
            # If password was provided and failed, try falling back to keys only if they exist
            if self.password:
                logger.warning("Authentication with password failed, retrying with keys only...")
                connect_kwargs.pop("password", None)
                try:
                    self._ssh.connect(**connect_kwargs)
                except Exception:
                    raise e
            else:
                raise e
        self._sftp = self._ssh.open_sftp()
        logger.info("SSH connection established")

    def close(self) -> None:
        """Close SSH connection."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None

        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

        logger.debug("SSH connection closed")

    def exec(self, cmd: str, check: bool = True) -> tuple[str, str, int]:
            """
            Execute command on remote server.

            Supports handling Ctrl+C (KeyboardInterrupt) by sending SIGINT
            to the remote process.

            Args:
                cmd: Command to execute
                check: If True, raise exception on non-zero exit code

            Returns:
                Tuple of (stdout, stderr, exit_code)

            Raises:
                RuntimeError: If check=True and command fails
                KeyboardInterrupt: If user interrupts the execution
            """
            if self._ssh is None:
                raise RuntimeError("Not connected")

            stdin, stdout, stderr = self._ssh.exec_command(cmd)
            channel = stdout.channel

            try:
                exit_code = channel.recv_exit_status()
            except KeyboardInterrupt:
                logger.warning("Caught Ctrl+C. Sending SIGINT to remote process...")
                try:
                    channel.send_signal("INT")
                except Exception as e:
                    logger.debug("Failed to send SIGINT: %s", e)
                channel.close()
                raise

            out = stdout.read().decode().strip()
            err = stderr.read().decode().strip()

            if check and exit_code != 0:
                raise RuntimeError(f"Command failed (exit {exit_code}): {cmd}\n{err}")

            return out, err, exit_code

    def create_tunnel(self, remote_host: str, remote_port: int) -> SSHTunnel:
        """
        Create SSH tunnel to remote host:port.

        Args:
            remote_host: Remote host to tunnel to
            remote_port: Remote port to tunnel to

        Returns:
            SSHTunnel instance (caller is responsible for stopping it)
        """
        if self._ssh is None:
            raise RuntimeError("Not connected")

        return SSHTunnel(self._ssh, remote_host, remote_port)

    def __enter__(self) -> "SSHConnection":
        self.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()


class SSHConnectionManager:
    """
    Global manager for SSH connections to ensure reuse.
    Thread-safe singleton pattern.
    """
    _instance = None
    _lock = threading.Lock()
    _connections: dict[str, SSHConnection] = {}

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def get_connection(
        self,
        host: str,
        port: int = 22,
        user: str = "root",
        key_path: str | None = None,
        password: str | None = None,
        timeout: int = 30,
    ) -> SSHConnection:
        """Get an existing active connection or create a new one."""
        # Generate unique key including all authentication factors
        conn_key = f"{user}@{host}:{port}"

        with self._lock:
            conn = self._connections.get(conn_key)

            # 1. If connection exists and is active, return it
            if conn and conn.is_connected:
                return conn

            # 2. If connection exists but is dead, try reconnecting
            if conn and not conn.is_connected:
                logger.info(f"SSH connection to {conn_key} is dead. Reconnecting...")
                try:
                    conn.connect()
                    return conn
                except Exception:
                    # Reconnect failed, remove old object and prepare for new one
                    self.close_connection(conn_key)

            # 3. Create new connection
            logger.debug(f"Creating new SSH connection for {conn_key}")
            new_conn = SSHConnection(host, port, user, key_path, password, timeout)
            new_conn.connect()
            self._connections[conn_key] = new_conn
            return new_conn

    def close_connection(self, conn_key: str) -> None:
        """Close and remove a specific connection."""
        with self._lock:
            if conn_key in self._connections:
                conn = self._connections.pop(conn_key)
                conn.close()

    def close_all(self) -> None:
        """Close all managed connections."""
        with self._lock:
            for conn in self._connections.values():
                conn.close()
            self._connections.clear()


# Register cleanup on exit
atexit.register(SSHConnectionManager().close_all)


# Utility functions for remote file operations

def remote_file_exists(sftp: "paramiko.SFTPClient", path: str) -> bool:
    """Check if file exists on remote server."""
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False


def remote_file_size(sftp: "paramiko.SFTPClient", path: str) -> int:
    """Get file size on remote server. Returns 0 if not exists."""
    try:
        return sftp.stat(path).st_size
    except FileNotFoundError:
        return 0


def remote_read_header(sftp: "paramiko.SFTPClient", path: str, size: int = 50) -> bytes:
    """Read first N bytes of file on remote server."""
    with sftp.open(path, "rb") as f:
        return f.read(size)


def remote_delete_file(sftp: "paramiko.SFTPClient", path: str) -> None:
    """Delete file on remote server (ignore if not exists)."""
    try:
        sftp.remove(path)
    except FileNotFoundError:
        pass

def is_remote_mode() -> bool:
    """Check if running in remote mode based on configuration."""
    config = get_config()
    host = config.host
    if not host:
        return False
    return host.strip().lower() != "localhost" and not host.strip().startswith("127.0.0.")
