import argparse
from pathlib import Path

from comani.models.download import download_urls

DIFFUSION_MODELS_BF16 = [
    "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/diffusion_models/z_image_turbo_bf16.safetensors",
]

DIFFUSION_MODELS_GGUF = [
    "https://huggingface.co/jayn7/Z-Image-Turbo-GGUF/blob/main/z_image_turbo-Q5_K_M.gguf",  # ~5.52 GB
]

TEXT_ENCODERS_BF16 = [
    "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/text_encoders/qwen_3_4b.safetensors",
]

TEXT_ENCODERS_GGUF = [
    "https://huggingface.co/unsloth/Qwen3-4B-GGUF/blob/main/Qwen3-4B-UD-Q4_K_XL.gguf",  # ~2.55 GB
]

VAE = [
    "https://huggingface.co/Comfy-Org/z_image_turbo/blob/main/split_files/vae/ae.safetensors",
]

LORAS = [
    "https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/blob/main/pixel_art_style_z_image_turbo.safetensors",
]

MODEL_PATCHES = [
    "https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/blob/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
]


def download_z_image_turbo(
    quant: bool = False,
    comfyui_root: Path | str | None = None
) -> None:
    """
    Download Z-Image-Turbo models.
    Args:
        quant: Use GGUF quantized models instead of bf16
    """
    name = "Z-Image-Turbo GGUF" if quant else "Z-Image-Turbo bf16"
    diffusion_models = DIFFUSION_MODELS_GGUF if quant else DIFFUSION_MODELS_BF16
    text_encoders = TEXT_ENCODERS_GGUF if quant else TEXT_ENCODERS_BF16

    specs: dict[str, list[str]] = {
        "diffusion_models": diffusion_models,
        "text_encoders": text_encoders,
        "vae": VAE,
    }

    if not quant:
        specs["loras"] = LORAS
        specs["model_patches"] = MODEL_PATCHES

    download_urls(name, specs, comfyui_root)


__all__ = ["download_z_image_turbo"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--quant", action="store_true", help="Use GGUF quantized models")
    args, _ = parser.parse_known_args()

    download_z_image_turbo(quant=args.quant)
