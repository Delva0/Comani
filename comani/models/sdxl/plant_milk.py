#!/usr/bin/env python
"""
Plant Milk model.
https://civitai.com/models/1318509/plantmilk
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "Plant Milk"
SPECS = {
    "checkpoints": [
        "https://civitai.com/api/download/models/1714314?type=Model&format=SafeTensor&size=pruned&fp=fp16",
    ],
}


def download_plant_milk(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)


__all__ = ["download_plant_milk"]

if __name__ == "__main__":
    download_plant_milk()
