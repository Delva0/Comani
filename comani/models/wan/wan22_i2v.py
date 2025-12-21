#!/usr/bin/env python
"""
WAN 2.2 I2V models.
Use --quant for GGUF quantized models, otherwise fp8 scaled.
"""
import argparse
from pathlib import Path

from comani.models.download import download_urls

DIFFUSION_MODELS_FP8 = [
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors",
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors",
]

DIFFUSION_MODELS_GGUF = [
    "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/blob/main/HighNoise/Wan2.2-I2V-A14B-HighNoise-Q4_K_M.gguf",
    "https://huggingface.co/QuantStack/Wan2.2-I2V-A14B-GGUF/blob/main/LowNoise/Wan2.2-I2V-A14B-LowNoise-Q4_K_M.gguf",
]

TEXT_ENCODERS = [
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors",
]

VAE = [
    "https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/blob/main/split_files/vae/wan_2.1_vae.safetensors",
]

LORAS = [
    "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_HIGH_fp16.safetensors",
    "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/LoRAs/Wan22-Lightning/old/Wan2.2-Lightning_I2V-A14B-4steps-lora_LOW_fp16.safetensors",
    "https://huggingface.co/lopi999/Wan2.2-I2V_General-NSFW-LoRA/blob/main/NSFW-22-H-e8.safetensors",
    "https://huggingface.co/lopi999/Wan2.2-I2V_General-NSFW-LoRA/blob/main/NSFW-22-L-e8.safetensors",
]


def download_wan22_i2v(
    quant: bool = False,
    comfyui_root: Path | str | None = None
) -> None:
    """
    Download WAN 2.2 I2V models.
    Args:
        quant: Use GGUF quantized models instead of fp8 scaled
    """
    name = "WAN 2.2 GGUF" if quant else "WAN 2.2"
    diffusion_models = DIFFUSION_MODELS_GGUF if quant else DIFFUSION_MODELS_FP8

    download_urls(name, {
        "diffusion_models": diffusion_models,
        "text_encoders": TEXT_ENCODERS,
        "vae": VAE,
        "loras": LORAS,
    }, comfyui_root)


__all__ = ["download_wan22_i2v"]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--quant", action="store_true", help="Use GGUF quantized models")
    args, _ = parser.parse_known_args()

    download_wan22_i2v(quant=args.quant)
