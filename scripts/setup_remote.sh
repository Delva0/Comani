#!/bin/bash
# Setup remote VastAI instance for comani (install aria2, etc.)

set -e

if [ -z "$SERVER_IP" ] || [ -z "$SERVER_PORT" ]; then
    echo "Error: SERVER_IP and SERVER_PORT must be set"
    echo "Usage: export SERVER_IP=x.x.x.x SERVER_PORT=xxxxx && ./scripts/setup_remote.sh"
    exit 1
fi

echo "Connecting to $SERVER_IP:$SERVER_PORT to install dependencies..."

# Install aria2 and other useful tools with lock waiting
ssh -p "$SERVER_PORT" "root@$SERVER_IP" "
    while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 ; do
        echo 'Waiting for other apt process to finish...'
        sleep 2
    done
    apt-get update && apt-get install -y aria2 curl wget
"

echo "Remote setup complete!"
