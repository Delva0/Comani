#!/usr/bin/env python
"""
AniKawaXL model (NoobAI-based checkpoint).
https://civitai.com/models/1282887/anikawaxl
"""
from comfy_anime_pack.models.download import run_download_urls

if __name__ == "__main__":
    run_download_urls("AniKawaXL (NoobAI)", {
        "checkpoints": [
            "https://civitai.com/models/1282887?modelVersionId=2148084",  # V2 ~6.46 GB
        ],
    })
