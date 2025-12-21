#!/usr/bin/env python
"""
Dupli-Cat Flat V1.0 models (diffusers format).
Use --obsession for Obsession OBS variant, otherwise Illustrious variant.
"""
import argparse

from comfy_anime_pack.models.download import run_download_repo

REPOS = {
    "illustrious": ("Dupli-Cat Flat Illustrious V1.0", "John6666/dupli-cat-flat-illustrious-v10-sdxl"),
    "obsession": ("Dupli-Cat Flat Obsession OBS V1.0", "John6666/dupli-cat-flat-obsession-obs-v10-sdxl"),
}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--obsession", action="store_true", help="Use Obsession OBS variant")
    args, _ = parser.parse_known_args()

    variant = "obsession" if args.obsession else "illustrious"
    name, repo = REPOS[variant]
    run_download_repo(name, repo)
