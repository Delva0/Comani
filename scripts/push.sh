#!/bin/bash
# Push local comani to remote VastAI instance

set -e

if [ -z "$SERVER_IP" ] || [ -z "$SERVER_PORT" ]; then
    echo "Error: SERVER_IP and SERVER_PORT must be set"
    echo "Usage: export SERVER_IP=x.x.x.x SERVER_PORT=xxxxx && ./push.sh"
    exit 1
fi

# Use environment variable or default to current directory
LOCAL_DIR="${COMANI_LOCAL:-$(pwd)/}"
REMOTE_DIR="${COMANI_REMOTE:-root@$SERVER_IP:/workspace/ComfyUI/comani/}"

echo "Pushing to $SERVER_IP:$SERVER_PORT..."
rsync -avz --delete -e "ssh -p $SERVER_PORT" "$LOCAL_DIR" "$REMOTE_DIR"

echo "Fixing permissions..."
ssh -p "$SERVER_PORT" "root@$SERVER_IP" "chown -R root:root /workspace/ComfyUI/comani"

echo "Done!"
