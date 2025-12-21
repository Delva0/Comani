#!/usr/bin/env python
"""
Hassaku XL Illustrious model.
https://civitai.com/models/140272/hassaku-xl-illustrious
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "Hassaku XL Illustrious"
SPECS = {
    "checkpoints": [
        "https://civitai.com/models/140272?modelVersionId=1240288",
    ],
}


def download_hassaku(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)


__all__ = ["download_hassaku"]

if __name__ == "__main__":
    download_hassaku()
