#!/usr/bin/env python
"""
Download utilities with multiple backend implementations.

This module provides a unified interface for downloading files with support for:
  - Local Aria2 daemon (high-speed, multi-connection downloads)
  - Remote Aria2 via SSH tunnel (for remote servers)
  - Requests fallback (when Aria2 is not available)
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from tqdm import tqdm

import re
from comani.utils.connection.ssh import is_remote_mode
from comani.utils.connection.node import Node
from comani.utils.connection.node import get_node

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

REQUEST_TIMEOUT = 30
ARIA2_RPC_PORT = 6800
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ============================================================================
# Utility Functions
# ============================================================================

def human_size(size: int) -> str:
    """Convert bytes to human-readable format."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def is_html_content(data: bytes) -> bool:
    """Check if data starts with HTML content (indicates failed auth/redirect)."""
    return data.startswith(b"<!DOCTYPE") or data.startswith(b"<html")


def is_html_file(path: Path) -> bool:
    """Check if file starts with HTML content."""
    try:
        with open(path, "rb") as f:
            return is_html_content(f.read(50))
    except (OSError, IOError):
        return False


def get_url_size(url: str, headers: dict | None = None) -> int:
    """Get file size from URL using HEAD request, fallback to GET with Range if HEAD fails."""
    req_headers = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)

    # Try HEAD request first
    try:
        resp = requests.head(url, headers=req_headers, allow_redirects=True, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        size = int(resp.headers.get("content-length", 0))
        if size > 0:
            return size
    except Exception:
        pass  # Fallback to GET

    # Fallback: GET with Range header (some servers reject HEAD but accept GET)
    try:
        range_headers = {**req_headers, "Range": "bytes=0-0"}
        resp = requests.get(url, headers=range_headers, allow_redirects=True, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 206:
            content_range = resp.headers.get("content-range", "")
            if "/" in content_range:
                return int(content_range.split("/")[-1])
    except Exception:
        pass

    return 0


# def is_aria2_available() -> bool:  # TODO: if remote mode, check if aria2c is available on remote server
#     """Check if aria2c is available locally."""
#     try:
#         result = subprocess.run(
#             ["aria2c", "--version"],
#             capture_output=True,
#             timeout=5,
#         )
#         return result.returncode == 0
#     except Exception:
#         return False


# ============================================================================
# Abstract Base Downloader
# ============================================================================

class BaseDownloader(ABC):
    """
    Abstract base class for file downloaders.
    Provides unified interface for local and remote downloading.
    """

    @abstractmethod
    def download_file(
        self,
        url: str,
        out_path: str | Path,
        headers: dict | None = None,
        total_size: int = 0,
    ) -> bool:
        """
        Download a single file.

        Args:
            url: Download URL
            out_path: Output file path
            headers: Optional HTTP headers (e.g., auth tokens)
            total_size: Expected file size (0 if unknown)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def file_exists(self, path: Path) -> bool:
        """Check if file exists."""
        pass

    @abstractmethod
    def file_size(self, path: Path) -> int:
        """Get file size. Returns 0 if not exists."""
        pass

    @abstractmethod
    def read_file_header(self, path: Path, size: int = 50) -> bytes:
        """Read first N bytes of file for validation."""
        pass

    @abstractmethod
    def delete_file(self, path: Path) -> None:
        """Delete a file."""
        pass

    @abstractmethod
    def mkdir(self, path: Path) -> None:
        """Create directory (recursive)."""
        pass

    def is_html_file(self, path: Path) -> bool:
        """Check if file is HTML (indicates auth failure)."""
        try:
            header = self.read_file_header(path, 50)
            return is_html_content(header)
        except Exception:
            return False

    def validate_and_prepare(
        self,
        out_path: str | Path,
        url: str,
        headers: dict | None,
        total_size: int,
    ) -> tuple[int, int, bool]:
        """
        Validate existing file and prepare for download.

        Args:
            out_path: Output file path
            url: Download URL (for size check if needed)
            headers: HTTP headers for size check
            total_size: Expected total size (0 to fetch from URL)

        Returns:
            Tuple of (existing_size, total_size, should_download)
        """
        out_path = Path(out_path)
        existing_size = self.file_size(out_path)

        if total_size == 0:
            total_size = get_url_size(url, headers)

        # Check for corrupted HTML file
        if existing_size > 0 and self.is_html_file(out_path):
            print(f"⚠️  Detected invalid file (HTML), removing: {out_path.name}")
            self.delete_file(out_path)
            existing_size = 0

        # Check for oversized file (corrupted)
        if total_size > 0 and existing_size > total_size:
            print(f"⚠️  File larger than expected ({human_size(existing_size)} > {human_size(total_size)}), removing")
            self.delete_file(out_path)
            existing_size = 0

        # Skip if complete
        if total_size > 0 and existing_size == total_size:
            print(f"✅ Skipped (complete): {out_path.name} ({human_size(existing_size)})")
            return existing_size, total_size, False

        return existing_size, total_size, True

    def close(self) -> None:
        """Clean up resources. Override in subclasses if needed."""
        pass

    def __enter__(self) -> "BaseDownloader":
        return self

    def __exit__(self, *args) -> None:
        self.close()


def parse_aria2_size(size_str: str) -> int:
    """Parse aria2 size string (e.g. 400.0KiB) to bytes."""
    units = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    match = re.match(r"([\d\.]+)([KMGT]?i?B)?", size_str)
    if not match:
        return 0
    val, unit = match.groups()
    if not unit:
        return int(float(val))
    unit = unit[0].upper()
    return int(float(val) * units.get(unit, 1))


# ============================================================================
# Aria2 Downloader (via Node)
# ============================================================================

class Aria2Downloader(BaseDownloader):
    """
    Unified downloader using Aria2 via Node abstraction.
    Runs aria2c in background and polls progress from log.
    """

    def __init__(self, node: Node):
        self.node = node

    def file_exists(self, path: Path) -> bool:
        return self.node.exec_shell(f'test -f "{path}"').ok

    def file_size(self, path: Path) -> int:
        # aria2c doesn't provide a direct way to get file size,
        # if we use stat command, it does not work.

        # res = self.node.exec_shell(f'stat -c %s "{path}" 2>/dev/null')
        # if res.ok:
        #     try:
        #         return int(res.stdout.strip())
        #     except (ValueError, TypeError):
        #         pass
        return 0    # TODO: Is there any other way to get file size downloaded by aria2c?

    def read_file_header(self, path: Path, size: int = 50) -> bytes:
        # Use dd to read first N bytes and base64 to transfer safely
        res = self.node.exec_shell(f'dd if="{path}" bs=1 count={size} 2>/dev/null | base64')
        if not res.ok:
            return b""
        import base64
        return base64.b64decode(res.stdout.strip())

    def delete_file(self, path: Path) -> None:
        aria2c_path = path.with_suffix(path.suffix + ".aria2")
        # meta_path = path.with_suffix(path.suffix + ".download")
        # self.node.exec_shell(f'rm -f "{path}" ＆& rm -f "{aria2c_path}" "{meta_path}"')
        self.node.exec_shell(f'rm -f "{path}" ＆& rm -f "{aria2c_path}"')

    def mkdir(self, path: Path) -> None:
        self.node.exec_shell(f'mkdir -p "{path}"')

    def download_file(
            self,
            url: str,
            out_path: Path,
            headers: dict | None = None,
            total_size: int = 0,
        ) -> bool:
            """Download using aria2 via Node exec_shell."""
            existing_size, total_size, should_download = self.validate_and_prepare(
                out_path, url, headers, total_size
            )

            if not should_download:
                return True

            self.mkdir(out_path.parent)

            # meta_path = out_path.with_suffix(out_path.suffix + ".download")

            # def update_meta(size: int):
            #     meta = {
            #         "url": url,
            #         "existing_size": size,
            #         "total_size": total_size,
            #         "timestamp": time.time()
            #     }
            #     self.node.exec_shell(f"echo '{json.dumps(meta)}' > \"{meta_path}\"")

            existing_size = self.file_size(out_path)
            if existing_size > 0:
                print(f"⏳ Resuming from {human_size(existing_size)}: {out_path.name}")
            else:
                print(f"📥 Downloading: {out_path.name}")

            log_file = f"/tmp/aria2_{os.urandom(4).hex()}.log"

            # Build command
            cmd = [
                "aria2c",
                "-c",
                f'--dir="{out_path.parent}"',
                f'--out="{out_path.name}"',
                "--continue=true",
                "--max-connection-per-server=16",
                "--split=16",
                "--min-split-size=1M",
                "--auto-file-renaming=false",
                "--allow-overwrite=false",
                "--summary-interval=1",
            ]
            if headers:
                for k, v in headers.items():
                    cmd.append(f'--header="{k}: {v}"')
            cmd.append(f'"{url}"')

            full_cmd = f"nohup {' '.join(cmd)} > {log_file} 2>&1 & echo $!"
            res = self.node.exec_shell(full_cmd)
            pid = res.stdout.strip()

            if not pid or not pid.isdigit():
                print(f"❌ Failed to start aria2c: {res.stderr}")
                return False

            try:
                pbar = None  # We need to lazy load tqdm timer after first update to avoid old existing size.

                last_completed = existing_size
                while True:
                    # Check if process still running
                    is_running = self.node.exec_shell(f"ps -p {pid}").ok

                    # Get last progress line
                    log_res = self.node.exec_shell(f'grep "\\[#" {log_file} | tail -n 1')
                    line = log_res.stdout.strip()

                    # Parse progress: [#bc97c8 5.4GiB/6.4GiB(84%) CN:16 DL:87MiB ETA:11s]
                    match = re.search(r"\[#\w+\s+([\d\.]+\w+)/([\d\.]+\w+)\((\d+)%\)", line)
                    if match:
                        curr_str, total_str, percent = match.groups()
                        completed = parse_aria2_size(curr_str)
                        if completed > last_completed:
                            if pbar is None:
                                pbar = tqdm(
                                    total=total_size or 100,
                                    initial=completed,
                                    unit="B" if total_size else "%",
                                    unit_scale=total_size > 0,
                                    unit_divisor=1024,
                                )
                            else:
                                pbar.update(completed - last_completed)
                            last_completed = completed
                            # update_meta(completed)


                    if not is_running:
                        # Final update to 100% if total_size is known
                        if total_size and total_size > last_completed:
                            pbar.update(total_size - last_completed)
                            # update_meta(last_completed)
                        break

                    time.sleep(1)

                # Final check logic (Success/Failure)
                final_size = self.file_size(out_path)
                if final_size == 0 or (total_size > 0 and final_size < total_size) or self.is_html_file(out_path):
                    error_msg = f"Download failed for {out_path.name}: "
                    if final_size == 0:
                        error_msg += "File not found or empty."
                    elif total_size > 0 and final_size < total_size:
                        error_msg += f"Size mismatch ({human_size(final_size)} < {human_size(total_size)})."
                    elif self.is_html_file(out_path):
                        error_msg += "Downloaded file is HTML (possibly authentication failure)."
                        self.delete_file(out_path)

                    logger.error(error_msg)

                    # Try to read log for error details
                    log_res = self.node.exec_shell(f"cat {log_file}")
                    if log_res.ok:
                        logger.error(f"Aria2 Log Output:\n{log_res.stdout}")
                    return False

                logger.info("Successfully downloaded: %s (%s)", out_path.name, human_size(final_size))
                return True

            except KeyboardInterrupt:
                logger.warning(f"Download cancelled by user. Killing remote aria2 process (PID: {pid})...")
                self.node.exec_shell(f"kill {pid}")
                raise

            finally:
                self.node.exec_shell(f"rm -f {log_file}")

    def close(self) -> None:
        self.node.close()


# ============================================================================
# Fallback Requests Downloader
# ============================================================================

class RequestsDownloader(BaseDownloader):
    """
    Fallback downloader using pure requests.
    Used when aria2 is not available.
    """

    CHUNK_SIZE = 8192

    def file_exists(self, path: Path) -> bool:
        return path.exists()

    def file_size(self, path: Path) -> int:
        return path.stat().st_size if path.exists() else 0

    def read_file_header(self, path: Path, size: int = 50) -> bytes:
        with open(path, "rb") as f:
            return f.read(size)

    def delete_file(self, path: Path) -> None:
        path.unlink(missing_ok=True)

    def mkdir(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def download_file(
        self,
        url: str,
        out_path: Path,
        headers: dict | None = None,
        total_size: int = 0,
    ) -> bool:
        """Download using requests with resume support."""
        existing_size, total_size, should_download = self.validate_and_prepare(
            out_path, url, headers, total_size
        )

        if not should_download:
            return True

        self.mkdir(out_path.parent)

        request_headers = {"User-Agent": USER_AGENT}
        if headers:
            request_headers.update(headers)

        # Resume download
        if existing_size > 0:
            request_headers["Range"] = f"bytes={existing_size}-"
            print(f"⏳ Resuming from {human_size(existing_size)}: {out_path.name}")
        else:
            print(f"📥 Downloading: {out_path.name}")

        if total_size > 0:
            print(f"   Size: {human_size(total_size)}")
        print(f"   Path: {out_path}")

        try:
            with requests.get(
                url,
                stream=True,
                allow_redirects=True,
                headers=request_headers,
                timeout=REQUEST_TIMEOUT,
            ) as r:
                if r.status_code == 416:
                    print(f"✅ Already complete: {out_path.name}")
                    return True

                r.raise_for_status()

                if existing_size == 0:
                    total_size = int(r.headers.get("content-length", 0))

                mode = "ab" if existing_size > 0 else "wb"
                with open(out_path, mode) as f:
                    with tqdm(
                        total=total_size,
                        initial=existing_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                    ) as pbar:
                        for chunk in r.iter_content(chunk_size=self.CHUNK_SIZE):
                            f.write(chunk)
                            pbar.update(len(chunk))

        except Exception as e:
            print(f"❌ Download failed: {e}")
            return False

        # Validate
        if self.is_html_file(out_path):
            print("❌ Downloaded file is HTML (auth failure)")
            self.delete_file(out_path)
            return False

        print(f"✅ Complete: {out_path.name}")
        return True


def get_downloader() -> BaseDownloader:
    # TODO: all downloader should handle clearing cache of this function when node is not available
    # 或者如果我们可以直接给node api 下层的ssh conn做连接池，那么可以在更底层实现cache，就不必这么乱了
    """
    Factory function to create appropriate downloader based on environment.

    Returns:
        Appropriate BaseDownloader subclass instance
    """
    node = get_node()
    if node.exec_shell("aria2c --version").ok:
        return Aria2Downloader(node)

    if not is_remote_mode():
        logger.warning("Aria2 is not available, falling back to requests downloader")
        return RequestsDownloader()

    raise RuntimeError("Unsupported download mode configuration")


def download_url(url: str, out_path: str | Path, headers: dict | None = None) -> Path:
    """
    Legacy download function for backward compatibility.

    Args:
        url: Download URL
        out_path: Output file path
        headers: Optional HTTP headers

    Returns:
        Output path as Path object
    """
    downloader = get_downloader()
    downloader.download_file(url, out_path, headers)
    return Path(out_path)
