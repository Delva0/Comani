#!/usr/bin/env python
"""
Hassaku XL Illustrious model.
https://civitai.com/models/140272/hassaku-xl-illustrious
"""
from comfy_anime_pack.models.download import run_download_urls

if __name__ == "__main__":
    run_download_urls("Hassaku XL Illustrious", {
        "checkpoints": [
            "https://civitai.com/models/140272?modelVersionId=1240288",  # Hassaku XL Illustrious
        ],
    })
