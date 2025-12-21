#!/bin/bash
# Install ComfyUI on remote VastAI instance (run on remote)

set -e

COMFYUI_ROOT="${COMFYUI_ROOT:-/workspace/ComfyUI}"

echo "Installing comfy-cli..."
pip install comfy-cli

echo "Installing ComfyUI..."
comfy --workspace "$COMFYUI_ROOT" install

echo "Done! Run 'python main.py --listen 0.0.0.0 --multi-user' to start"
