#!/usr/bin/env python
"""
BoleroMix Illustrious model with recommended LoRAs.
https://civitai.com/models/869634/boleromixillustrious
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "BoleroMix Illustrious"
SPECS = {
    "checkpoints": [
        "https://civitai.com/models/869634?modelVersionId=1412789",
    ],
}


def download_boleromix(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)

__all__ = ["download_boleromix"]

if __name__ == "__main__":
    download_boleromix()
