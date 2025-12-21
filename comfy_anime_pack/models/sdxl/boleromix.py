#!/usr/bin/env python
"""
BoleroMix Illustrious model with recommended LoRAs.
https://civitai.com/models/869634/boleromixillustrious
"""
from comfy_anime_pack.models.download import run_download_urls

if __name__ == "__main__":
    run_download_urls("BoleroMix Illustrious", {
        "checkpoints": [
            "https://civitai.com/models/869634?modelVersionId=1412789",  # BoleroMix Illustrious
        ],
    })
