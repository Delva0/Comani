#!/usr/bin/env python
"""
Plant Milk model.
https://civitai.com/models/1282887/anikawaxl
"""
from comfy_anime_pack.models.download import run_download_urls

if __name__ == "__main__":
    run_download_urls("Plant Milk", {
        "checkpoints": [
            "https://civitai.com/api/download/models/1714314?type=Model&format=SafeTensor&size=pruned&fp=fp16",  # V2 ~6.46 GB
        ],
    })
