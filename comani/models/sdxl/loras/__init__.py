"""SDXL LoRA download wrappers."""
from pathlib import Path

from comani.models.download import make_yml_download_func

_DIR = Path(__file__).parent


# ===============================
# Download functions
# ===============================

download_artists = make_yml_download_func(_DIR / "artists.yml")
download_misc = make_yml_download_func(_DIR / "misc.yml")
download_sliders = make_yml_download_func(_DIR / "sliders.yml")

__all__ = ["download_artists", "download_misc", "download_sliders"]




def download_all(comfyui_root: Path | str | None = None) -> None:
    """Download all LoRAs."""
    for func_name in __all__:
        func = globals()[func_name]
        func(comfyui_root)

__all__ += ["download_all"]
