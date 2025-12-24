#!/usr/bin/env python
"""
Model downloader business logic layer.

This module provides high-level APIs for downloading models from various sources:
  - HuggingFace repos and files
  - Civitai models
  - Direct URL downloads

It handles URL parsing, type detection, and orchestrates downloads using the
underlying download infrastructure (comani.utils.download).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlparse, unquote

from comani.model.model_pack import ModelPackRegistry, ModelDef
from comani.utils.api.hf import parse_hf_file_url, list_repo_files, get_auth_headers as get_hf_headers
from comani.utils.api.civitai import parse_civitai_url
from comani.utils.connection.ssh import is_remote_mode
from comani.utils.download import (
    BaseDownloader,
    get_downloader,
)

# ============================================================================
# Enums and Data Classes
# ============================================================================

class DownloadType(str, Enum):
    """Type of download source."""
    HF_REPO = "hf_repo"
    HF_FILE = "hf_file"
    CIVIT_FILE = "civit_file"
    DIRECT_URL = "direct_url"


@dataclass(frozen=True)
class DownloadItem:
    """Standardized download item with explicit type."""
    type: DownloadType
    url: str
    name: str | None = None


@dataclass(frozen=True)
class ResolvedDownloadItem:
    """Resolved download with final URL, filepath, and headers."""
    url: str
    filepath: str
    headers: dict


# ============================================================================
# URL Type Detection and Resolution
# ============================================================================

def detect_type(url: str) -> DownloadType:
    """
    Auto-detect download type from URL.

    Args:
        url: Source URL

    Returns:
        Detected DownloadType
    """
    if "huggingface.co" in url:
        if re.search(r"/(blob|resolve)/[^/]+/.+", url):
            return DownloadType.HF_FILE
        if re.match(r"https://huggingface\.co/[^/]+/[^/]+/?$", url):
            return DownloadType.HF_REPO
        return DownloadType.HF_FILE
    if "civitai.com" in url:
        return DownloadType.CIVIT_FILE
    return DownloadType.DIRECT_URL


def normalize_item(item: str | dict) -> DownloadItem:
    """
    Normalize yml item to standardized DownloadItem.

    Args:
        item: URL string or dict with url/type/name fields

    Returns:
        DownloadItem instance
    """
    if isinstance(item, str):
        return DownloadItem(type=detect_type(item), url=item)

    url = item.get("url", "")
    explicit_type = item.get("type")
    dtype = DownloadType(explicit_type) if explicit_type else detect_type(url)
    name = item.get("name") or item.get("filename") or item.get("dirname")
    return DownloadItem(type=dtype, url=url, name=name)


def resolve_download(item: DownloadItem) -> ResolvedDownloadItem | list[ResolvedDownloadItem]:
    """
    Resolve DownloadItem to final download URL(s) with headers.

    Args:
        item: DownloadItem to resolve

    Returns:
        ResolvedDownload for single files, or list for repos

    Raises:
        ValueError: If URL format is invalid
    """
    match item.type:
        case DownloadType.HF_FILE:
            info = parse_hf_file_url(item.url)
            filename = item.name or info.filename
            return ResolvedDownloadItem(info.download_url, filename, info.headers)

        case DownloadType.HF_REPO:
            match_result = re.match(r"https://huggingface\.co/([^/]+/[^/]+)", item.url)
            if not match_result:
                raise ValueError(f"Invalid HuggingFace repo URL: {item.url}")
            repo_id = match_result.group(1)
            files = list_repo_files(repo_id)
            headers = get_hf_headers()
            return [
                ResolvedDownloadItem(
                    f"https://huggingface.co/{repo_id}/resolve/main/{f}",
                    f,
                    headers,
                )
                for f in files
            ]

        case DownloadType.CIVIT_FILE:
            info = parse_civitai_url(item.url)
            filename = item.name or info.filename
            return ResolvedDownloadItem(info.download_url, filename, info.headers)

        case DownloadType.DIRECT_URL:
            parsed = urlparse(item.url)
            filename = item.name or unquote(parsed.path.split("/")[-1])
            return ResolvedDownloadItem(item.url, filename, {})


# ============================================================================
# Model Downloader Class
# ============================================================================

class ModelDownloader:
    """
    High-level model downloader with automatic backend selection.

    Example:
        >>> with ModelDownloader.create() as dl:
        ...     dl.download_ids(["wan.wan2_1_vae_bf16"], registry)
    """

    def __init__(self, downloader: BaseDownloader, base_path: Path | str | None = None):
        """
        Initialize ModelDownloader.

        Args:
            downloader: Underlying download backend
            base_path: Base path for relative model paths
        """
        self._downloader = downloader
        self._base_path = Path(base_path) if base_path else None

    @classmethod
    def create(cls, base_path: Path | str | None = None) -> "ModelDownloader":
        """
        Create ModelDownloader with appropriate backend.
        """
        return cls(get_downloader(), base_path)

    def download_by_ids(self, ids: list[str], model_pack_registry: ModelPackRegistry, dry_run: bool = False) -> bool:
        """
        Download models.

        Args:
            ids: List of model IDs or group IDs.
            model_pack_registry: Model pack registry to resolve targets.
            dry_run: If True, only simulate download.

        Returns:
            True if successful, False otherwise.
        """
        if not ids:
            return False

        # Resolve targets
        mode_str = "Remote" if is_remote_mode() else "Local"

        if len(ids) == 1:
            resolved = model_pack_registry.resolve_to_group(ids[0])
            if not resolved.models:
                print(f"Error: No models found for '{ids[0]}'")
                return False
            print(f"\n📦 [{mode_str}] Downloading: {resolved.id}")
            print(f"   {resolved.description}")
            print(f"   {len(resolved.models)} model(s) to download\n")
        else:
            resolved, ref_info = model_pack_registry.resolve_multiple(ids)
            if not resolved.models:
                print("Error: No models found for any of the specified targets")
                return False

            print(f"\n📊 [{mode_str}] Total: {len(resolved.models)} unique models to download\n")

        if dry_run:
            print(f"[DRY-RUN] Would download ({mode_str}):")
            for model in resolved.models:
                print(f"  - {model.source_module}.{model.id}: {model.path}")
            return True

        try:
            self.download_by_defs(resolved.id, resolved.models)
            return True
        except Exception:
            import traceback
            traceback.print_exc()
            # print(f"❌ Download error: {e}")
            return False

    def download_by_defs(self, name: str, models: list[ModelDef]) -> None:
        """
        Download models by ModelDef list.

        Args:
            name: Display name for the download batch
            models: List of ModelDef objects
        """
        print("=" * 60)
        print(f"📦 Downloading: {name[1:]}")
        print("=" * 60)

        total = len(models)
        for i, model in enumerate(models, 1):
            # Determine target path
            path = Path(model.path)
            if self._base_path and not path.is_absolute():
                target_path = self._base_path / path
            else:
                target_path = path

            # For display purposes, show path
            print(f"\n[{i}/{total}] -> {target_path}")

            item = DownloadItem(type=detect_type(model.url), url=model.url, name=path.name)
            resolved = resolve_download(item)

            if isinstance(resolved, list):
                # Repo download (multiple files)
                # target_path is the destination directory for the repo content
                for j, dl in enumerate(resolved, 1):
                    print(f"  [{j}/{len(resolved)}] {dl.filepath}")
                    out_path = target_path / dl.filepath
                    self._downloader.mkdir(out_path.parent)
                    self._downloader.download_file(dl.url, out_path, dl.headers)
            else:
                # Single file download
                # target_path is the full path to the file
                self._downloader.mkdir(target_path.parent)
                self._downloader.download_file(resolved.url, target_path, resolved.headers)

        print(f"\n{'=' * 60}")
        print(f"✅ {name} download complete!")
        print("=" * 60)

    def close(self) -> None:
        """Clean up resources."""
        self._downloader.close()

    def __enter__(self) -> "ModelDownloader":
        # Trigger connection for remote downloaders
        if hasattr(self._downloader, "connect"):
            self._downloader.connect()
        return self

    def __exit__(self, *args) -> None:
        self.close()
