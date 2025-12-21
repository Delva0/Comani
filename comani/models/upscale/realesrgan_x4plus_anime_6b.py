#!/usr/bin/env python
"""
RealESRGAN_x4plus_anime_6B model.
https://github.com/xinntao/Real-ESRGAN
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "RealESRGAN x4plus Anime 6B"
SPECS = {
    "upscale_models": [
        "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
    ],
}


def download_realesrgan_x4plus_anime_6b(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)

__all__ = ["download_realesrgan_x4plus_anime_6b"]

if __name__ == "__main__":
    download_realesrgan_x4plus_anime_6b()
