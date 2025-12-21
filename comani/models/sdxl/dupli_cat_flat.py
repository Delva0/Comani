#!/usr/bin/env python
"""
Dupli-Cat Flat V1.0 models (diffusers format).
Use --obsession for Obsession OBS variant, otherwise Illustrious variant.
"""
import argparse
from pathlib import Path

from comani.models.download import download_urls

REPOS = {
    "illustrious": ("Dupli-Cat Flat Illustrious V1.0", "https://huggingface.co/John6666/dupli-cat-flat-illustrious-v10-sdxl"),
    "obsession": ("Dupli-Cat Flat Obsession OBS V1.0", "https://huggingface.co/John6666/dupli-cat-flat-obsession-obs-v10-sdxl"),
}


def download_dupli_cat_flat(
    variant: str = "illustrious",
    comfyui_root: Path | str | None = None
) -> None:
    """
    Download Dupli-Cat Flat model.
    Args:
        variant: "illustrious" or "obsession"
    """
    name, repo_url = REPOS[variant]
    download_urls(name, {"diffusers": [repo_url]}, comfyui_root)


__all__ = ["download_dupli_cat_flat"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--obsession", action="store_true", help="Use Obsession OBS variant")
    args, _ = parser.parse_known_args()

    variant = "obsession" if args.obsession else "illustrious"
    download_dupli_cat_flat(variant)
