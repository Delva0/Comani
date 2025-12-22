"""
Dependency resolver for preset model dependencies.

Resolves dependencies in these formats:
  - Model name: checkpoint: "model.safetensors"
  - Model list: checkpoint: ["model1.safetensors", "model2.safetensors"]
  - Direct URL: checkpoint: "https://..."
  - Dict with url/name: checkpoint: {"url": "...", "name": "..."}
"""

import os
from dataclasses import dataclass
from pathlib import Path

from ..utils.model_downloader import (
    DownloadItem,
    normalize_item,
    resolve_download,
    download_url,
    detect_type,
    DownloadType,
)


# Model type to ComfyUI subdirectory mapping
MODEL_TYPE_DIRS = {
    "checkpoint": "checkpoints",
    "lora": "loras",
    "vae": "vae",
    "unet": "unet",
    "clip": "clip",
    "controlnet": "controlnet",
    "upscale_model": "upscale_models",
    "embedding": "embeddings",
    "diffusion_model": "diffusion_models",
    "text_encoder": "text_encoders",
}


@dataclass
class ResolvedDependency:
    """A resolved dependency with model path info."""
    model_type: str
    name: str
    path: Path
    needs_download: bool = False
    download_item: DownloadItem | None = None


class DependencyError(Exception):
    """Raised when dependency cannot be resolved."""
    pass


def _is_url(value: str) -> bool:
    """Check if value looks like a URL."""
    return value.startswith(("http://", "https://"))


def _normalize_dependency_item(item: str | dict) -> DownloadItem | None:
    """
    Normalize a single dependency item.
    Returns DownloadItem for URL-like items, None for model names.
    """
    if isinstance(item, dict):
        return normalize_item(item)

    if _is_url(item):
        return normalize_item(item)

    # Plain model name - not a download item
    return None


class DependencyResolver:
    """
    Resolves and downloads preset dependencies.
    Example: resolver = DependencyResolver(comfyui_models_dir)
    """

    def __init__(
        self,
        comfyui_models_dir: Path | str | None = None,
    ):
        self.comfyui_models_dir = self._resolve_comfyui_models(comfyui_models_dir)

    def _resolve_comfyui_models(self, comfyui_models_dir: Path | str | None) -> Path | None:
        """Resolve ComfyUI models directory."""
        if comfyui_models_dir:
            return Path(comfyui_models_dir).resolve()
        # Try COMFY_UI_DIR env var
        comfyui_root = os.environ.get("COMFY_UI_DIR")
        if comfyui_root:
            return Path(comfyui_root).resolve() / "models"
        return None

    def _get_model_subdir(self, model_type: str) -> str:
        """Get ComfyUI subdirectory for model type."""
        return MODEL_TYPE_DIRS.get(model_type, model_type)

    def _model_exists(self, model_type: str, name: str) -> Path | None:
        """Check if model file exists in ComfyUI models directory."""
        if not self.comfyui_models_dir:
            return None
        subdir = self._get_model_subdir(model_type)
        model_path = self.comfyui_models_dir / subdir / name
        if model_path.exists():
            return model_path
        # Also check without subdir (flat structure)
        flat_path = self.comfyui_models_dir / name
        if flat_path.exists():
            return flat_path
        return None

    def _extract_filename_from_url(self, url: str) -> str:
        """Extract filename from URL."""
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        filename = unquote(parsed.path.split("/")[-1])
        return filename if filename else "unknown"

    def _resolve_single_item(
        self,
        model_type: str,
        item: str | dict,
    ) -> ResolvedDependency:
        """Resolve a single dependency item."""
        subdir = self._get_model_subdir(model_type)

        # Try to normalize as download item (URL or dict)
        download_item = _normalize_dependency_item(item)

        if download_item:
            # URL-like item - temporary dependency
            if download_item.name:
                name = download_item.name
            elif isinstance(item, str):
                name = self._extract_filename_from_url(item)
            elif isinstance(item, dict):
                name = item.get("name") or self._extract_filename_from_url(item.get("url", ""))
            else:
                name = "unknown"

            # Check if already exists
            existing = self._model_exists(model_type, name)
            if existing:
                return ResolvedDependency(
                    model_type=model_type,
                    name=name,
                    path=existing,
                    needs_download=False,
                )

            # Need to download
            if not self.comfyui_models_dir:
                raise DependencyError(
                    f"Cannot download {name}: COMFY_UI_DIR not set"
                )
            target_path = self.comfyui_models_dir / subdir / name
            return ResolvedDependency(
                model_type=model_type,
                name=name,
                path=target_path,
                needs_download=True,
                download_item=download_item,
            )

        # Plain model name
        name = item if isinstance(item, str) else str(item)

        # Check if exists locally
        existing = self._model_exists(model_type, name)
        if existing:
            return ResolvedDependency(
                model_type=model_type,
                name=name,
                path=existing,
                needs_download=False,
            )

        # Model not found - must use URL in preset
        raise DependencyError(
            f"Model '{name}' not found in ComfyUI models directory. "
            f"Use URL or dict format in preset dependencies."
        )

    def resolve(
        self,
        dependencies: dict[str, str | list | dict],
    ) -> list[ResolvedDependency]:
        """
        Resolve all dependencies from preset.
        Example: deps = resolver.resolve({"checkpoint": "model.safetensors"})
        """
        results = []

        for model_type, value in dependencies.items():
            if isinstance(value, list):
                for item in value:
                    results.append(self._resolve_single_item(model_type, item))
            else:
                results.append(self._resolve_single_item(model_type, value))

        return results

    def ensure_dependencies(
        self,
        dependencies: dict[str, str | list | dict],
        dry_run: bool = False,
    ) -> list[ResolvedDependency]:
        """
        Resolve and download all missing dependencies.
        Example: deps = resolver.ensure_dependencies(preset.dependencies)
        """
        resolved = self.resolve(dependencies)

        for dep in resolved:
            if dep.needs_download and dep.download_item:
                if dry_run:
                    print(f"[DRY-RUN] Would download: {dep.name} -> {dep.path}")
                    continue

                print(f"Downloading {dep.name}...")
                resolved_dl = resolve_download(dep.download_item)

                if isinstance(resolved_dl, list):
                    # hf_repo type
                    for dl in resolved_dl:
                        target = dep.path.parent / dl.filename
                        download_url(dl.url, target, dl.headers)
                else:
                    download_url(resolved_dl.url, dep.path, resolved_dl.headers)

                print(f"Downloaded: {dep.name}")

        return resolved

    def validate_only(
        self,
        dependencies: dict[str, str | list | dict],
    ) -> tuple[list[ResolvedDependency], list[str]]:
        """
        Validate dependencies without downloading.
        Returns (resolved_deps, error_messages)
        """
        resolved = []
        errors = []

        for model_type, value in dependencies.items():
            items = value if isinstance(value, list) else [value]
            for item in items:
                try:
                    dep = self._resolve_single_item(model_type, item)
                    resolved.append(dep)
                except DependencyError as e:
                    errors.append(str(e))

        return resolved, errors
