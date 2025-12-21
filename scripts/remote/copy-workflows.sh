#!/bin/bash
# Copy workflows to ComfyUI user directory (run on remote)

set -e

COMFYUI_ROOT="${COMFYUI_ROOT:-/workspace/ComfyUI}"
PACK_DIR="${COMFY_ANIME_PACK_DIR:-$COMFYUI_ROOT/comfy_anime_pack}"
WORKFLOW_DIR="$COMFYUI_ROOT/user/default/workflows"

mkdir -p "$WORKFLOW_DIR"
cp "$PACK_DIR/workflows/"*.json "$WORKFLOW_DIR/"

echo "Workflows copied to $WORKFLOW_DIR"
