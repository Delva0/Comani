#!/usr/bin/env python
"""
RealESRGAN_x4plus_anime_6B model.
https://github.com/xinntao/Real-ESRGAN
"""
from comfy_anime_pack.models.download import run_download_urls

if __name__ == "__main__":
    run_download_urls("RealESRGAN x4plus Anime 6B", {
        "upscale_models": [
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth",
        ],
    })
