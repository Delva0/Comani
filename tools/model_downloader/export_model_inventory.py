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
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = REPO_ROOT / "comani" / "models"
REQUEST_TIMEOUT = 10

# Ensure repository root is importable for dynamic module loading.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


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


def map_item_type(spec_key: str) -> str:
    key = spec_key.lower()
    if "lora" in key:
        return "LoRA"
    if "vae" == key:
        return "VAE"
    if "text_encoder" in key:
        return "Text encoder"
    if "detection" in key:
        return "Detection"
    if "diffusion" in key or "checkpoint" in key or "diffuser" in key:
        return "Base model"
    if "upscale" in key:
        return "Upscaler"
    if "patch" in key:
        return "Model patch"
    return spec_key


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


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def resolve_filename(url: str, fallback: str | None = None) -> str:
    if "civitai.com" in url:
        name = resolve_civitai_filename(url)
        if name:
            return name

    parsed = urlparse(url)
    tail = Path(parsed.path).name
    if tail:
        return tail

    return fallback or ""


def derive_save_path(subdir: str, url: str, fallback: str | None = None) -> str:
    filename = resolve_filename(url, fallback)
    if filename:
        return f"models/{subdir}/{filename}"
    return f"models/{subdir}/"


def collect_from_model_py(path: Path, architecture: str) -> Iterator[InventoryEntry]:
    module = load_module(path)

    if hasattr(module, "MODEL_NAME") and hasattr(module, "SPECS"):
        name = getattr(module, "MODEL_NAME")
        specs: dict[str, list[str]] = getattr(module, "SPECS")
        for key, urls in specs.items():
            item_type = map_item_type(key)
            for url in urls:
                yield InventoryEntry(
                    architecture=architecture,
                    subdir=key,
                    item_type=item_type,
                    name=name,
                    url=url,
                    source=map_source(url),
                    size_bytes=resolve_size(url),
                    save_path=derive_save_path(key, url, name),
                )
        return

    if path.name == "dupli_cat_flat.py":
        repos: dict[str, tuple[str, str]] = getattr(module, "REPOS")
        for name, repo_url in repos.values():
            yield InventoryEntry(
                architecture=architecture,
                subdir="diffusers",
                item_type="Diffusers pipeline",
                name=name,
                url=repo_url,
                source=map_source(repo_url),
                size_bytes=resolve_size(repo_url),
                save_path=derive_save_path("diffusers", repo_url, name),
            )
        return

    if path.name == "wan22_i2v.py":
        name_regular = "WAN 2.2"
        name_quant = "WAN 2.2 GGUF"

        for url in getattr(module, "DIFFUSION_MODELS_FP8"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="diffusion_models",
                item_type="Base model",
                name=name_regular,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("diffusion_models", url, name_regular),
            )
        for url in getattr(module, "DIFFUSION_MODELS_GGUF"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="diffusion_models",
                item_type="Quantized model",
                name=name_quant,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("diffusion_models", url, name_quant),
            )
        for url in getattr(module, "TEXT_ENCODERS"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="text_encoders",
                item_type="Text encoder",
                name=name_regular,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("text_encoders", url, name_regular),
            )
        for url in getattr(module, "VAE"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="vae",
                item_type="VAE",
                name=name_regular,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("vae", url, name_regular),
            )
        for url in getattr(module, "LORAS"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="loras",
                item_type="LoRA",
                name=name_regular,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("loras", url, name_regular),
            )
        return

    if path.name == "wan22_animate.py":
        name = getattr(module, "MODEL_NAME")
        specs: dict[str, list[str]] = getattr(module, "SPECS")
        for key, urls in specs.items():
            item_type = map_item_type(key)
            for url in urls:
                yield InventoryEntry(architecture, key, item_type, name, url, map_source(url), resolve_size(url), derive_save_path(key, url, name))
        return

    if path.name == "z_image_turbo.py":
        bf16_name = "Z-Image-Turbo bf16"
        gguf_name = "Z-Image-Turbo GGUF"

        for url in getattr(module, "DIFFUSION_MODELS_BF16"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="diffusion_models",
                item_type="Base model",
                name=bf16_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("diffusion_models", url, bf16_name),
            )
        for url in getattr(module, "TEXT_ENCODERS_BF16"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="text_encoders",
                item_type="Text encoder",
                name=bf16_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("text_encoders", url, bf16_name),
            )
        for url in getattr(module, "VAE"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="vae",
                item_type="VAE",
                name=bf16_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("vae", url, bf16_name),
            )
        for url in getattr(module, "LORAS"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="loras",
                item_type="LoRA",
                name=bf16_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("loras", url, bf16_name),
            )
        for url in getattr(module, "MODEL_PATCHES"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="model_patches",
                item_type="Model patch",
                name=bf16_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("model_patches", url, bf16_name),
            )

        for url in getattr(module, "DIFFUSION_MODELS_GGUF"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="diffusion_models",
                item_type="Quantized model",
                name=gguf_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("diffusion_models", url, gguf_name),
            )
        for url in getattr(module, "TEXT_ENCODERS_GGUF"):
            yield InventoryEntry(
                architecture=architecture,
                subdir="text_encoders",
                item_type="Quantized text encoder",
                name=gguf_name,
                url=url,
                source=map_source(url),
                size_bytes=resolve_size(url),
                save_path=derive_save_path("text_encoders", url, gguf_name),
            )
        return


def collect_from_yaml(path: Path, architecture: str) -> Iterator[InventoryEntry]:
    data = yaml.safe_load(path.read_text()) or {}
    loras: Iterable[str | dict] = data.get("loras", [])
    for entry in loras:
        if isinstance(entry, str):
            url = entry
            name = infer_name_from_url(url)
        else:
            url = entry.get("url") or ""
            name = entry.get("filename") or infer_name_from_url(url)

        if not url:
            continue

        yield InventoryEntry(
            architecture=architecture,
            subdir="loras",
            item_type="LoRA",
            name=name,
            url=url,
            source=map_source(url),
            size_bytes=None,
            save_path=derive_save_path("loras", url, name),
        )


def infer_name_from_url(url: str) -> str:
    parsed = urlparse(url)
    tail = Path(parsed.path).name
    if tail:
        return tail
    return url


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


def civitai_version_filename(version_id: str) -> str | None:
    data = civitai_version_cache.get(version_id)
    if data is None:
        return None
    if not data:
        return None
    files = data.get("files") or []
    if not files:
        return None
    return files[0].get("name")


def civitai_model_filename(model_id: str) -> str | None:
    data = civitai_model_cache.get(model_id)
    if not data:
        return None
    versions = data.get("modelVersions") or []
    for version in versions:
        files = version.get("files") or []
        if files:
            name = files[0].get("name")
            if name:
                return name
    return None


def resolve_civitai_filename(url: str) -> str | None:
    version_id, model_id = extract_civitai_ids(url)
    if version_id:
        return civitai_version_filename(version_id)
    if model_id:
        return civitai_model_filename(model_id)
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
    entries: list[InventoryEntry] = []
    for path in MODELS_DIR.rglob("*.py"):
        if path.name in {"__init__.py", "download.py"}:
            continue
        arch = path.parent.name
        entries.extend(list(collect_from_model_py(path, arch)))

    for path in MODELS_DIR.rglob("*.yml"):
        arch = path.parent.parent.name if path.parent.name == "loras" else path.parent.name
        entries.extend(list(collect_from_yaml(path, arch)))

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
