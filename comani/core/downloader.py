"""
Model downloader for ComfyUI models.
"""

import os
from pathlib import Path

from ..utils.model_downloader import (
    DownloadItem,
    normalize_item,
    resolve_download,
    download_url,
)


class ModelDownloader:
    """
    High-level model downloader for ComfyUI.
    Example: downloader = ModelDownloader("/workspace/ComfyUI")
    """

    def __init__(self, comfyui_root: Path | str | None = None):
        self.models_dir = self._resolve_models_dir(comfyui_root)

    def _resolve_models_dir(self, comfyui_root: Path | str | None = None) -> Path:
        """
        Resolve ComfyUI models directory.
        Priority: argument > COMFY_UI_DIR env var.
        """
        root = comfyui_root or os.environ.get("COMFY_UI_DIR")
        if not root:
            raise ValueError("COMFY_UI_DIR environment variable is not set")
        root = Path(root).resolve()
        return root / "models"

    def _print_banner(self, name: str, action: str = "Downloading"):
        print("=" * 60)
        print(f"{action} {name}...")
        print("=" * 60)

    def download_spec(
        self,
        name: str,
        specs: dict[str, list[str | dict[str, str]]],
    ) -> None:
        """
        Download models by spec dict.
        Example: downloader.download_spec("WAN 2.2", {"vae": ["https://..."]})
        """
        self._print_banner(name)

        total = sum(len(items) for items in specs.values())
        i = 0
        for subdir, items in specs.items():
            out_dir = self.models_dir / subdir
            for raw_item in items:
                i += 1
                print(f"\n[{i}/{total}] -> {subdir}/")

                item = normalize_item(raw_item)
                resolved = resolve_download(item)

                if isinstance(resolved, list):
                    # hf_repo: download all files
                    dirname = item.name or item.url.split("/")[-1]
                    base_dir = out_dir / dirname
                    for j, dl in enumerate(resolved, 1):
                        print(f"  [{j}/{len(resolved)}] {dl.filename}")
                        download_url(dl.url, base_dir / dl.filename, dl.headers)
                else:
                    download_url(resolved.url, out_dir / resolved.filename, resolved.headers)

        print(f"\n{'=' * 60}")
        print(f"{name} download complete!")
        print("=" * 60)

    def download_yml(self, yml_path: Path | str) -> None:
        """
        Download models from YML file.
        YML format: {subdir: [items...]} where items can be URLs or dicts with url/filename/type.
        """
        import yaml

        yml_path = Path(yml_path)
        with open(yml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            print(f"Empty or invalid YML file: {yml_path}")
            return

        name = yml_path.stem
        self.download_spec(name, data)
