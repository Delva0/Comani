#!/usr/bin/env python
"""
Generate a consolidated inventory of models defined under ``comani/models``.

The output CSV includes the model architecture, type, name, download URL,
provider, and file size (when discoverable via the provider APIs or HTTP
headers). This is intended to give a single reference sheet for the currently
tracked resources.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlunparse

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
MODELS_DIR = REPO_ROOT / "comani" / "models"
REQUEST_TIMEOUT = 10

# Ensure repository root is importable
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from comani.core.model_pack import ModelPackRegistry


@dataclass
class InventoryEntry:
    architecture: str
    subdir: str
    item_type: str
    name: str
    url: str
    source: str
    size_bytes: int | None
    save_path: str

    @property
    def size_human(self) -> str:
        return human_readable_size(self.size_bytes)


def human_readable_size(size: int | None) -> str:
    if size is None:
        return ""

    step = 1024.0
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < step or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= step

    return f"{value:.2f} B"


def map_source(url: str) -> str:
    hostname = urlparse(url).hostname or ""
    if "huggingface.co" in hostname:
        return "HuggingFace"
    if "civitai.com" in hostname:
        return "CivitAI"
    if "github.com" in hostname:
        return "GitHub"
    return hostname or "Unknown"


def map_item_type(path: str) -> str:
    path_lower = path.lower()
    if "lora" in path_lower:
        return "LoRA"
    if "/vae/" in path_lower:
        return "VAE"
    if "text_encoder" in path_lower:
        return "Text encoder"
    if "onnx" in path_lower or "/det/" in path_lower:
        return "Detection"
    if "diffusion" in path_lower:
        return "Base model"
    if "checkpoint" in path_lower:
        return "Checkpoint"
    if "upscale" in path_lower:
        return "Upscaler"
    if "patch" in path_lower:
        return "Model patch"
    return "Model"


def extract_civitai_ids(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    version_ids = qs.get("modelVersionId")
    version_id = version_ids[0] if version_ids else None

    parts = [p for p in parsed.path.split("/") if p]
    model_id = parts[1] if len(parts) >= 2 and parts[0] == "models" and parts[1].isdigit() else None

    if parsed.path.startswith("/api/download/models/"):
        suffix = parsed.path.split("/")[-1]
        if suffix.isdigit():
            version_id = version_id or suffix

    return version_id, model_id


def normalize_huggingface_url(url: str) -> str:
    parsed = urlparse(url)
    if "huggingface.co" not in (parsed.hostname or ""):
        return url

    path = parsed.path
    if "/blob/" in path:
        path = path.replace("/blob/", "/resolve/", 1)
    return urlunparse(parsed._replace(path=path))


def head_content_length(url: str) -> int | None:
    try:
        response = requests.head(url, allow_redirects=True, timeout=REQUEST_TIMEOUT)
        if response.status_code >= 400:
            return None
        length = response.headers.get("content-length")
        return int(length) if length is not None else None
    except requests.RequestException:
        return None


civitai_version_cache: dict[str, dict] = {}
civitai_model_cache: dict[str, dict] = {}


def fetch_civitai_version(version_id: str) -> dict | None:
    if version_id in civitai_version_cache:
        return civitai_version_cache[version_id]
    try:
        resp = requests.get(f"https://civitai.com/api/v1/model-versions/{version_id}", timeout=REQUEST_TIMEOUT)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        civitai_version_cache[version_id] = data
        return data
    except requests.RequestException:
        return None


def fetch_civitai_model(model_id: str) -> dict | None:
    if model_id in civitai_model_cache:
        return civitai_model_cache[model_id]
    try:
        resp = requests.get(f"https://civitai.com/api/v1/models/{model_id}", timeout=REQUEST_TIMEOUT)
        if resp.status_code >= 400:
            return None
        data = resp.json()
        civitai_model_cache[model_id] = data
        return data
    except requests.RequestException:
        return None


def resolve_civitai_size(url: str) -> int | None:
    version_id, model_id = extract_civitai_ids(url)
    if version_id:
        return civitai_version_size(version_id)

    if model_id:
        return civitai_model_size(model_id)

    if urlparse(url).path.startswith("/api/download/models/"):
        return head_content_length(url)

    return None


def civitai_version_size(version_id: str) -> int | None:
    data = fetch_civitai_version(version_id)
    if not data:
        return None
    files = data.get("files") or []
    if not files:
        return None
    size_kb = files[0].get("sizeKB")
    if size_kb is None:
        return None
    return int(float(size_kb) * 1024)


def civitai_model_size(model_id: str) -> int | None:
    data = fetch_civitai_model(model_id)
    if not data:
        return None
    versions = data.get("modelVersions") or []
    for version in versions:
        files = version.get("files") or []
        if files:
            size_kb = files[0].get("sizeKB")
            if size_kb is not None:
                return int(float(size_kb) * 1024)
    return None


def resolve_size(url: str) -> int | None:
    if "civitai.com" in url:
        return resolve_civitai_size(url)

    normalized_url = normalize_huggingface_url(url)
    return head_content_length(normalized_url)


def collect_inventory() -> list[InventoryEntry]:
    """Collect inventory from new YAML model pack format."""
    entries: list[InventoryEntry] = []
    registry = ModelPackRegistry(MODELS_DIR)

    for model in registry.list_models():
        # Extract architecture from source file
        source_file = model.source_file
        if "/" in source_file:
            architecture = source_file.split("/")[0]
        else:
            architecture = source_file

        # Extract subdir from path
        path_parts = model.path.split("/")
        if len(path_parts) >= 2 and path_parts[0] == "models":
            subdir = path_parts[1]
        else:
            subdir = "unknown"

        entries.append(
            InventoryEntry(
                architecture=architecture,
                subdir=subdir,
                item_type=map_item_type(model.path),
                name=model.id,
                url=model.url,
                source=map_source(model.url),
                size_bytes=resolve_size(model.url),
                save_path=model.path,
            )
        )

    return entries


def write_csv(entries: list[InventoryEntry], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["architecture", "type", "name", "url", "source", "save_path", "size_bytes", "size_human"])
        for entry in sorted(entries, key=lambda e: (e.architecture, e.subdir, e.item_type, e.name, e.url)):
            writer.writerow([
                entry.architecture,
                entry.item_type,
                entry.name,
                entry.url,
                entry.source,
                entry.save_path,
                entry.size_bytes or "",
                entry.size_human,
            ])


def main(output_path: Path) -> None:
    entries = collect_inventory()
    write_csv(entries, output_path)
    print(f"Saved {len(entries)} records to {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=MODELS_DIR / "model_inventory.csv",
        help="Destination path for the generated CSV",
    )
    args = parser.parse_args()

    main(args.output)
