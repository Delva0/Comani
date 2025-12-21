"""
Civitai API utilities.
"""
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests

REQUEST_TIMEOUT = 30


class _TokenStore:
    """Lazy-loaded Civitai token with one-time warning."""

    def __init__(self):
        self._token: str | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = os.environ.get("CIVITAI_API_TOKEN", "")
            if not self._token:
                print("Warning: CIVITAI_API_TOKEN not set. Civitai downloads may fail.")
                print("  Get token: https://civitai.com/user/account -> API Keys")
        return self._token


_tokens = _TokenStore()


def get_token() -> str:
    return _tokens.token


@dataclass(frozen=True)
class CivitaiFileInfo:
    """Parsed Civitai file download info."""
    version_id: str
    filename: str
    download_url: str
    headers: dict


def get_version_info(url: str) -> tuple[str, str]:
    """
    Extract version_id and filename from Civitai URL.
    Supports: model page URLs, versioned URLs, api/download URLs.
    """
    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    version_id: str | None = query.get("modelVersionId", [None])[0]
    model_id: str | None = None

    if not version_id:
        # Check for api/download URL format: /api/download/models/{version_id}
        api_download_match = re.search(r"/api/download/models/(\d+)", url)
        if api_download_match:
            version_id = api_download_match.group(1)
        else:
            # Standard model page URL: /models/{model_id}
            match = re.search(r"/models/(\d+)", url)
            if not match:
                raise ValueError(f"Invalid Civitai URL: {url}")
            model_id = match.group(1)

    # Fetch version info from API
    if version_id:
        api_url = f"https://civitai.com/api/v1/model-versions/{version_id}"
    else:
        api_url = f"https://civitai.com/api/v1/models/{model_id}"

    resp = requests.get(api_url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    if not version_id:
        # Get first version from model response
        version_data = data["modelVersions"][0]
        version_id = str(version_data["id"])
    else:
        version_data = data

    # Extract filename from files array
    files = version_data.get("files", [])
    filename = files[0]["name"] if files else f"model_{version_id}.safetensors"

    return version_id, filename


def parse_civitai_url(url: str) -> CivitaiFileInfo:
    """Parse Civitai URL into download info."""
    version_id, filename = get_version_info(url)

    download_url = f"https://civitai.com/api/download/models/{version_id}"
    token = get_token()
    if token:
        download_url = f"{download_url}?token={token}"

    return CivitaiFileInfo(
        version_id=version_id,
        filename=filename,
        download_url=download_url,
        headers={},
    )


def get_model_info(model_id: str | int) -> dict | None:
    """Fetch model info from Civitai API."""
    api_url = f"https://civitai.com/api/v1/models/{model_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    token = get_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(api_url, headers=headers, timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            print(f"  ⚠️  Failed to fetch model {model_id}: {resp.status_code}")
            return None
        return resp.json()
    except Exception as e:
        print(f"  ❌ Error requesting model {model_id}: {e}")
        return None
