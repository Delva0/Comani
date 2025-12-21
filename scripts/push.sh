#!/bin/bash
# Push local comfy_anime_pack to remote VastAI instance

set -e

if [ -z "$SERVER_IP" ] || [ -z "$SERVER_PORT" ]; then
    echo "Error: SERVER_IP and SERVER_PORT must be set"
    echo "Usage: export SERVER_IP=x.x.x.x SERVER_PORT=xxxxx && ./push.sh"
    exit 1
fi

# Use environment variable or default to current directory
LOCAL_DIR="${COMFY_ANIME_PACK_LOCAL:-$(pwd)/}"
REMOTE_DIR="${COMFY_ANIME_PACK_REMOTE:-root@$SERVER_IP:/workspace/ComfyUI/comfy_anime_pack/}"

echo "Pushing to $SERVER_IP:$SERVER_PORT..."
rsync -avz --delete -e "ssh -p $SERVER_PORT" "$LOCAL_DIR" "$REMOTE_DIR"

echo "Fixing permissions..."
ssh -p "$SERVER_PORT" "root@$SERVER_IP" "chown -R root:root /workspace/ComfyUI/comfy_anime_pack"

echo "Done!"
