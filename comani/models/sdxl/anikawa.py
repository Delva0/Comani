#!/usr/bin/env python
"""
AniKawaXL model (NoobAI-based checkpoint).
https://civitai.com/models/1282887/anikawaxl
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "AniKawaXL (NoobAI)"
SPECS = {
    "checkpoints": [
        "https://civitai.com/models/1282887?modelVersionId=2148084",  # V2 ~6.46 GB
    ],
}


def download_anikawa(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)


__all__ = ["download_anikawa"]

if __name__ == "__main__":
    download_anikawa()
