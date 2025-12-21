#!/bin/bash
# Pull remote comani from VastAI instance with backup

set -e

if [ -z "$SERVER_IP" ] || [ -z "$SERVER_PORT" ]; then
    echo "Error: SERVER_IP and SERVER_PORT must be set"
    echo "Usage: export SERVER_IP=x.x.x.x SERVER_PORT=xxxxx && ./pull.sh"
    exit 1
fi

# Use environment variable or default to current directory
LOCAL_DIR="${COMANI_LOCAL:-$(pwd)}"
BACKUP_DIR="${LOCAL_DIR}-old"
REMOTE_DIR="${COMANI_REMOTE:-root@$SERVER_IP:/workspace/ComfyUI/comani/}"

cd "$LOCAL_DIR"

# Create backup
echo "Creating backup..."
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/backup_$(date +%Y%m%d_%H%M%S).tar.gz" -C "$(dirname "$LOCAL_DIR")" "$(basename "$LOCAL_DIR")"

# Pull from remote
echo "Pulling from $SERVER_IP:$SERVER_PORT..."
rsync -avz --delete -e "ssh -p $SERVER_PORT" "$REMOTE_DIR" .

echo "Done!"
