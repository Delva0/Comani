#!/usr/bin/env python
"""
WAN Animate models.
https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled
"""
from pathlib import Path

from comani.models.download import download_urls

MODEL_NAME = "WAN Animate"
SPECS = {
    "diffusion_models": [
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/blob/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/blob/main/Wan22Animate/Wan2_2-Animate-14B_fp8_scaled_e4m3fn_KJ_v2.safetensors",
    ],
    "vae": [
        "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/Wan2_1_VAE_bf16.safetensors",
    ],
    "text_encoders": [
        "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/umt5-xxl-enc-bf16.safetensors",
    ],
    "detection": [
        "https://huggingface.co/JunkyByte/easy_ViTPose/blob/main/onnx/wholebody/vitpose-l-wholebody.onnx",
        "https://huggingface.co/Wan-AI/Wan2.2-Animate-14B/blob/main/process_checkpoint/det/yolov10m.onnx",
    ],
    "loras": [
        "https://huggingface.co/vrgamedevgirl84/Wan14BT2VFusioniX/blob/main/FusionX_LoRa/Phantom_Wan_14B_FusionX_LoRA.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/LoRAs/Wan22_relight/WanAnimate_relight_lora_fp16.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy/blob/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank128_bf16.safetensors",
    ],
}


def download_wan22_animate(comfyui_root: Path | str | None = None) -> None:
    download_urls(MODEL_NAME, SPECS, comfyui_root)

__all__ = ["download_wan22_animate"]


if __name__ == "__main__":
    download_wan22_animate()
