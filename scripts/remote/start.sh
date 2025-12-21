#!/bin/bash
# Start ComfyUI server (run on remote)

COMFYUI_ROOT="${COMFYUI_ROOT:-/workspace/ComfyUI}"

cd "$COMFYUI_ROOT"
python main.py --listen 0.0.0.0 --multi-user
