"""
Civitai API and Collection utilities.
"""
import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs

import requests
import yaml
from comani.config import get_config

REQUEST_TIMEOUT = 30

# Civitai model type to ComfyUI directory mapping
MODEL_TYPE_MAP = {
    "LORA": "loras",
    "LoCon": "loras",
    "DoRA": "loras",
    "Checkpoint": "checkpoints",
    "TextualInversion": "embeddings",
    "VAE": "vae",
    "ControlNet": "controlnet",
    "Upscaler": "upscale_models",
    "Poses": "poses",
    "Wildcards": "wildcards",
    "MotionModule": "animatediff_models",
    "AestheticGradient": "aesthetic_embeddings",
}


class _TokenStore:
    """Lazy-loaded Civitai token with one-time warning."""

    def __init__(self):
        self._token: str | None = None

    @property
    def token(self) -> str:
        if self._token is None:
            config = get_config()
            if config.civitai_api_token:
                self._token = config.civitai_api_token.get_secret_value()
            else:
                self._token = ""

            if not self._token:
                print("Warning: CIVITAI_API_TOKEN not set. Civitai downloads may fail.")
                print("  Get token: https://civitai.com/user/account -> API Keys")
        return self._token


_tokens = _TokenStore()


def get_token() -> str:
    """Get the Civitai API token."""
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


def get_collection_items(collection_id: int, api_token: str | None = None) -> list[dict]:
    """
    Get items from a Civitai collection.
    Requires API token for private collections or TRPC endpoint.
    """
    api_url = "https://civitai.com/api/trpc/collection.getAllCollectionItems"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    all_items = []
    print(f"Fetching collection {collection_id}...\n")

    if not api_token:
        print("⚠️  Warning: No API Token provided, collection access may require authentication")
        print("   Set env CIVITAI_API_TOKEN or pass api_token parameter")
        print("   Get token: https://civitai.com/user/account -> API Keys\n")

    cursor = None
    page = 1

    while True:
        try:
            input_obj = {"collectionId": collection_id}
            if cursor:
                input_obj["cursor"] = cursor
            params = {"input": json.dumps({"json": input_obj})}

            response = requests.get(api_url, params=params, headers=headers)

            if response.status_code == 401:
                print("❌ Auth failed: Valid API Token required")
                print("   Set env: export CIVITAI_API_TOKEN='your_token_here'")
                return all_items

            if response.status_code != 200:
                print(f"Request failed, status: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return all_items

            data = response.json()

            if "error" in data:
                error_msg = data.get("error", {}).get("json", {}).get("message", "Unknown error")
                print(f"❌ API error: {error_msg}")
                return all_items

            json_data = data.get("result", {}).get("data", {}).get("json", {})
            items = json_data.get("collectionItems", []) if isinstance(json_data, dict) else []
            next_cursor = json_data.get("nextCursor") if isinstance(json_data, dict) else None

            if not items:
                if page == 1:
                    print("Collection empty or inaccessible")
                break

            for item in items:
                item_type = item.get("type", "unknown").lower()
                name = "Unknown"
                url = "#"
                item_id = item.get("id")
                data_obj = item.get("data", {})

                if item_type == "model":
                    name = data_obj.get("name", f"Model ID: {item_id}")
                    model_id = data_obj.get("id", item_id)
                    url = f"https://civitai.com/models/{model_id}"
                elif item_type == "image":
                    image_id = data_obj.get("id", item_id)
                    name = f"Image ID: {image_id}"
                    url = f"https://civitai.com/images/{image_id}"
                elif item_type == "post":
                    post_id = data_obj.get("id", item_id)
                    name = data_obj.get("title") or f"Post ID: {post_id}"
                    url = f"https://civitai.com/posts/{post_id}"
                elif item_type == "article":
                    article_id = data_obj.get("id", item_id)
                    name = data_obj.get("title") or f"Article ID: {article_id}"
                    url = f"https://civitai.com/articles/{article_id}"

                all_items.append({"type": item_type, "name": name, "url": url})
                print(f"[{item_type.upper()}] {name}")

            if not next_cursor:
                break

            cursor = next_cursor
            page += 1
            time.sleep(0.5)

        except requests.exceptions.RequestException as e:
            print(f"Network error: {e}")
            break
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break

    print(f"\nDone! Found {len(all_items)} items.")
    return all_items


def export_models(
    collection_id: int,
    output_file: str = "collection_models.yml",
    prefix: str = "",
    api_token: str | None = None
) -> dict:
    """
    Export collection models to a YML dict grouped by model type.
    Example: export_models(123456, prefix="my_") generates {loras: [{url: ..., filename: my_xxx.safetensors}]}
    """
    if not api_token:
        config = get_config()
        if config.civitai_api_token:
            api_token = config.civitai_api_token.get_secret_value()
    items = get_collection_items(collection_id, api_token)

    model_items = [item for item in items if item["type"] == "model"]
    print(f"\nFetching details for {len(model_items)} models...")

    result: dict[str, list[dict]] = {}

    for i, item in enumerate(model_items, 1):
        url = item["url"]
        match = re.search(r"/models/(\d+)", url)
        if not match:
            print(f"  [{i}/{len(model_items)}] Skipping invalid URL: {url}")
            continue

        model_id = match.group(1)
        print(f"  [{i}/{len(model_items)}] Fetching model {model_id}: {item['name'][:40]}...")

        info = get_model_info(model_id)
        if not info:
            continue

        model_type = info.get("type", "Unknown")
        subdir = MODEL_TYPE_MAP.get(model_type, "other")

        versions = info.get("modelVersions", [])
        if not versions:
            print("    ⚠️  No version info")
            continue

        files = versions[0].get("files", [])
        if not files:
            print("    ⚠️  No file info")
            continue

        original_filename = files[0].get("name", f"model_{model_id}.safetensors")
        filename = f"{prefix}{original_filename}" if prefix else original_filename

        if subdir not in result:
            result[subdir] = []

        result[subdir].append({
            "url": url,
            "filename": filename,
        })

        time.sleep(0.3)

    # Save to YML
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(result, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"\n✅ Export complete! Saved to {output_file}")
    for subdir, models in result.items():
        print(f"   {subdir}: {len(models)} models")

    return result


__all__ = [
    "get_token",
    "get_version_info",
    "parse_civitai_url",
    "get_model_info",
    "CivitaiFileInfo",
    "get_collection_items",
    "export_models",
]
