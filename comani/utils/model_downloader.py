#!/usr/bin/env python
"""
Unified model downloader with standardized type detection.

Supported types:
  - hf_repo: Download entire HuggingFace repo
  - hf_file: Download single file from HuggingFace
  - civit_file: Download file from Civitai
  - direct_url: Direct download from any URL

Usage:
  python -m comani.models.download <yml_file> [--comfyui-root PATH]
"""
import argparse
import os
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests
import yaml
from tqdm import tqdm

from comani.utils.hf import parse_hf_file_url, list_repo_files, get_auth_headers as get_hf_headers
from comani.utils.civitai import parse_civitai_url

# Constants
REQUEST_TIMEOUT = 30
CHUNK_SIZE = 8192
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


class DownloadType(str, Enum):
    HF_REPO = "hf_repo"
    HF_FILE = "hf_file"
    CIVIT_FILE = "civit_file"
    DIRECT_URL = "direct_url"


@dataclass(frozen=True)
class DownloadItem:
    """Standardized download item with explicit type."""
    type: DownloadType
    url: str
    name: str | None = None  # filename for files, dirname for repos


def detect_type(url: str) -> DownloadType:
    """
    Auto-detect download type from URL.
    Priority: HF repo pattern > HF file pattern > Civitai > direct URL.
    """
    # HuggingFace patterns
    if "huggingface.co" in url:
        # hf_file: contains /blob/ or /resolve/ with file path
        if re.search(r"/(blob|resolve)/[^/]+/.+", url):
            return DownloadType.HF_FILE
        # hf_repo: just repo URL like https://huggingface.co/user/repo
        if re.match(r"https://huggingface\.co/[^/]+/[^/]+/?$", url):
            return DownloadType.HF_REPO
        # Default to file if has path components
        return DownloadType.HF_FILE

    # Civitai patterns
    if "civitai.com" in url:
        return DownloadType.CIVIT_FILE

    # Everything else is direct URL
    return DownloadType.DIRECT_URL


def normalize_item(item: str | dict) -> DownloadItem:
    """
    Normalize yml item to standardized DownloadItem.
    Supports both simple URL strings and dicts with explicit type.
    """
    if isinstance(item, str):
        url = item
        detected_type = detect_type(url)
        return DownloadItem(type=detected_type, url=url)

    url = item.get("url", "")
    explicit_type = item.get("type")

    if explicit_type:
        dtype = DownloadType(explicit_type)
    else:
        dtype = detect_type(url)

    # Support both legacy 'filename'/'dirname' and new unified 'name'
    name = item.get("name") or item.get("filename") or item.get("dirname")

    return DownloadItem(
        type=dtype,
        url=url,
        name=name,
    )


@dataclass(frozen=True)
class ResolvedDownload:
    """Resolved download with final URL, filename, and headers."""
    url: str
    filename: str
    headers: dict


def resolve_download(item: DownloadItem) -> ResolvedDownload | list[ResolvedDownload]:
    """
    Resolve DownloadItem to final download URL(s) with headers.
    Returns list for hf_repo (multiple files), single item otherwise.
    """
    match item.type:
        case DownloadType.HF_FILE:
            info = parse_hf_file_url(item.url)
            filename = item.name or info.filename
            return ResolvedDownload(info.download_url, filename, info.headers)

        case DownloadType.HF_REPO:
            # Extract repo_id from URL
            match_result = re.match(r"https://huggingface\.co/([^/]+/[^/]+)", item.url)
            if not match_result:
                raise ValueError(f"Invalid HuggingFace repo URL: {item.url}")
            repo_id = match_result.group(1)
            files = list_repo_files(repo_id)
            headers = get_hf_headers()
            return [
                ResolvedDownload(
                    f"https://huggingface.co/{repo_id}/resolve/main/{f}",
                    f,
                    headers,
                )
                for f in files
            ]

        case DownloadType.CIVIT_FILE:
            info = parse_civitai_url(item.url)
            filename = item.name or info.filename
            return ResolvedDownload(info.download_url, filename, info.headers)

        case DownloadType.DIRECT_URL:
            parsed = urlparse(item.url)
            filename = item.name or unquote(parsed.path.split("/")[-1])
            return ResolvedDownload(item.url, filename, {})


# ============================================================================
# Download utilities
# ============================================================================

def human_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _is_html_file(path: Path) -> bool:
    """Check if file starts with HTML content (indicates failed auth redirect)."""
    try:
        with open(path, "rb") as f:
            header = f.read(50)
        return header.startswith(b"<!DOCTYPE") or header.startswith(b"<html")
    except (OSError, IOError):
        return False


def _do_download(
    response: requests.Response,
    out_path: Path,
    total: int,
    initial: int = 0,
    mode: str = "wb"
) -> None:
    with open(out_path, mode) as f:
        with tqdm(total=total, initial=initial, unit="B", unit_scale=True, unit_divisor=1024) as pbar:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                f.write(chunk)
                pbar.update(len(chunk))


def download_url(url: str, out_path: str | Path, headers: dict | None = None) -> Path:
    """Download file with resume support."""
    out_path = Path(out_path)

    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)

    local_size = out_path.stat().st_size if out_path.exists() else 0

    # Check if existing file is HTML (failed auth redirect)
    if local_size > 0 and _is_html_file(out_path):
        print("Detected invalid file (HTML content), removing and re-downloading...")
        out_path.unlink()
        local_size = 0

    # Resume incomplete download
    if local_size > 0:
        range_headers = {**request_headers, "Range": f"bytes={local_size}-"}
        with requests.get(url, stream=True, allow_redirects=True, headers=range_headers, timeout=REQUEST_TIMEOUT) as r:
            if r.status_code == 416:
                print(f"Skipped (complete): {out_path.name} ({human_size(local_size)})")
                return out_path

            r.raise_for_status()
            remaining = int(r.headers.get("content-length", 0))
            total = local_size + remaining

            print(f"Resuming from {human_size(local_size)}")
            print(f"File: {out_path.name}")
            print(f"Size: {human_size(total)}")
            print(f"Saving to: {out_path}")

            _do_download(r, out_path, total, initial=local_size, mode="ab")
        return out_path

    # New download
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(url, stream=True, allow_redirects=True, headers=request_headers, timeout=REQUEST_TIMEOUT) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))

        print(f"File: {out_path.name}")
        print(f"Size: {human_size(total)}")
        print(f"Saving to: {out_path}")

        _do_download(r, out_path, total)

    return out_path
