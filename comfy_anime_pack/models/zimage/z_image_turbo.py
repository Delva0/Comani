#!/usr/bin/env python
"""
Z-Image-Turbo models.
Use --quant for GGUF quantized models, otherwise bf16.
"""
import argparse

from comfy_anime_pack.models.download import run_download_urls

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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--quant", action="store_true", help="Use GGUF quantized models")
    args, _ = parser.parse_known_args()

    name = "Z-Image-Turbo GGUF" if args.quant else "Z-Image-Turbo bf16"
    diffusion_models = DIFFUSION_MODELS_GGUF if args.quant else DIFFUSION_MODELS_BF16
    text_encoders = TEXT_ENCODERS_GGUF if args.quant else TEXT_ENCODERS_BF16

    urls = {
        "diffusion_models": diffusion_models,
        "text_encoders": text_encoders,
        "vae": VAE,
    }

    if not args.quant:
        urls["loras"] = [
            "https://huggingface.co/tarn59/pixel_art_style_lora_z_image_turbo/blob/main/pixel_art_style_z_image_turbo.safetensors",
        ]
        urls["model_patches"] = [
            "https://huggingface.co/alibaba-pai/Z-Image-Turbo-Fun-Controlnet-Union/blob/main/Z-Image-Turbo-Fun-Controlnet-Union.safetensors",
        ]

    run_download_urls(name, urls)
