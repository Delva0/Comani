"""
HuggingFace API utilities.
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import unquote

import requests

REQUEST_TIMEOUT = 30


class _TokenStore:
    """Lazy-loaded HF token with one-time warning."""

    def __init__(self):
        self._token: str | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = os.environ.get("HF_API_TOKEN", "") or os.environ.get("HF_TOKEN", "")
            if not self._token:
                print("Warning: HF_API_TOKEN not set. Some HuggingFace downloads may fail.")
                print("  Get token: https://huggingface.co/settings/tokens")
        return self._token


_tokens = _TokenStore()


def get_token() -> str:
    return _tokens.token


def get_auth_headers() -> dict:
    token = get_token()
    return {"Authorization": f"Bearer {token}"} if token else {}


@dataclass(frozen=True)
class HFFileInfo:
    """Parsed HuggingFace file download info."""
    repo_id: str
    revision: str
    file_path: str
    download_url: str
    filename: str
    headers: dict


def parse_hf_file_url(url: str) -> HFFileInfo:
    """
    Parse HuggingFace file URL into download info.
    Supports: https://huggingface.co/user/repo/blob/main/path/to/file.ext
    """
    pattern = r"https://huggingface\.co/([^/]+/[^/]+)/(blob|resolve)/([^/]+)/(.+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Invalid HuggingFace file URL: {url}")

    repo_id, _, revision, file_path = match.groups()
    download_url = f"https://huggingface.co/{repo_id}/resolve/{revision}/{file_path}"
    filename = unquote(file_path.split("/")[-1])

    return HFFileInfo(
        repo_id=repo_id,
        revision=revision,
        file_path=file_path,
        download_url=download_url,
        filename=filename,
        headers=get_auth_headers(),
    )


def list_repo_files(repo_id: str, skip: set[str] | None = None) -> list[str]:
    """List all files in a HuggingFace repo, excluding skip patterns."""
    skip = skip or {".gitattributes", "README.md"}

    url = f"https://huggingface.co/api/models/{repo_id}"
    resp = requests.get(url, headers=get_auth_headers(), timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()

    siblings = resp.json().get("siblings") or []
    files = [s["rfilename"] for s in siblings if isinstance(s, dict) and s.get("rfilename")]
    return [f for f in files if f not in skip]


def build_file_url(repo_id: str, file_path: str, revision: str = "main") -> str:
    return f"https://huggingface.co/{repo_id}/resolve/{revision}/{file_path}"
