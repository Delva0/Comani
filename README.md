# Comani

Personal ComfyUI resource pack for anime-style image generation, optimized for VastAI GPU instances.

## Installation

```bash
# Install from source
pip install -e .

# Or install directly
pip install git+https://github.com/delva/comani.git
```

## CLI Usage

```bash
# Download models from YML file
comani-download-model models/sdxl/loras/artists.yml --comfyui-root /path/to/ComfyUI

# Or use Python module
python -m comani.models.download models/sdxl/loras/misc.yml
```

## VastAI x ComfyUI Quick Start

### 1. Rent GPU Instance

- **GPU**: 4096+ VRAM × 1
- **Sort**: by price
- **Exclude**: HK region

### 2. Template Settings

- **Template**: SSH Container / ComfyUI Template / Ubuntu Desktop Container
- **Disk**: 100G
- **Expose Ports**: 8188, 8080

### 3. Connect via SSH

```bash
export SERVER_IP=<your_server_ip> SERVER_PORT=<your_ssh_port>

# Connect with port forwarding
ssh -p "${SERVER_PORT}" "root@${SERVER_IP}" -L 8080:localhost:8080
```

> **Tip**: Enable tmux mouse scroll: `Ctrl+b` then `:set -g mouse on`

### 4. Install ComfyUI (Skip if using ComfyUI template)

```bash
pip install comfy-cli
comfy --workspace /workspace/ComfyUI install
```

### 5. Start ComfyUI

```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --multi-user
```

> **Note**: If using Jupyter SSH, kill existing process first: `pkill -f python`

Access via browser: `http://<SERVER_IP>:8188`

---

## Resource Sync

### Push Local → Remote

```bash
export SERVER_IP=<ip> SERVER_PORT=<port>

# Option 1: Use the provided script
cd /path/to/comani
./scripts/push.sh

# Option 2: Manual rsync
rsync -avz --delete -e "ssh -p $SERVER_PORT" \
  ./ root@$SERVER_IP:/workspace/ComfyUI/comani/

# Fix permissions on remote
ssh -p $SERVER_PORT root@$SERVER_IP "chown -R root:root /workspace/ComfyUI/comani"
```

### Pull Remote → Local

```bash
export SERVER_IP=<ip> SERVER_PORT=<port>

# Option 1: Use the provided script
cd /path/to/comani
./scripts/pull.sh

# Option 2: Manual rsync
rsync -avz --delete -e "ssh -p $SERVER_PORT" \
  root@$SERVER_IP:/workspace/ComfyUI/comani/ .
```

---

## Remote Setup Scripts

### Copy Workflows

```bash
# On remote server
./scripts/remote/copy-workflows.sh

# Or manually
mkdir -p /workspace/ComfyUI/user/default/workflows
cp workflows/*.json /workspace/ComfyUI/user/default/workflows
```

### Download Models

```bash
export CIVITAI_API_TOKEN=<your_token>
export HF_API_TOKEN=<your_token>

# Using CLI
comani-download-model comani/models/sdxl/loras/artists.yml

# Or using Python script directly
python -m comani.models.sdxl.anikawa
```

# Download Utilities

This directory has been deprecated. The download logic has been reorganized:

- **Model download**: `models/download.py`
- **HuggingFace API**: `utils/hf/`
- **Civitai API**: `utils/civitai/`

## Usage Examples

### Download models from YML file
```bash
python -m models.download misc.yml
python -m models.download artists.yml --comfyui-root /path/to/ComfyUI
```

### Export Civitai collection to YML
```bash
# Export collection 6453691 with artist_ prefix
python -m utils.civitai.collection 6453691 --export model --output artists.yml --prefix artist_

# Export collection 106511 with slider_ prefix
python -m utils.civitai.collection 106511 --export model --output sliders.yml --prefix slider_
```


---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COMFYUI_ROOT` | ComfyUI installation directory | `/workspace/ComfyUI` |
| `CIVITAI_API_TOKEN` | Civitai API token for model downloads | - |
| `HF_API_TOKEN` | HuggingFace API token | - |
| `SERVER_IP` | Remote server IP for sync scripts | - |
| `SERVER_PORT` | Remote server SSH port for sync scripts | - |
