# Comani

**Comani** = **Com**(fy) + **Ani**(me) — Personal ComfyUI resource pack for anime-style image/video generation.

## VastAI x ComfyUI

### 1. Rent GPU Instance

- **GPU**: 4096+ VRAM × 1
- **Sort**: by price
- **Exclude**: HK region

### 2. Template Settings

- **Template**: SSH Container / ComfyUI Template / Ubuntu Desktop Container
- **Disk**: 100G
- **Expose Ports**: 8188, 8080

### 3. Wait for Instance Ready

### 4. Connect via SSH

```bash
export SERVER_IP=85.51.34.67 SERVER_PORT=42017

ssh -p "${SERVER_PORT}" "root@${SERVER_IP}" -L 8080:localhost:8080
```

> **Tip**: Enable tmux mouse scroll: `Ctrl+b` then `:set -g mouse on`

> **Note**: VastAI venv is at `/venv/main`

### 5. Install ComfyUI (Skip if using ComfyUI template)

```bash
pip install comfy-cli
comfy --workspace /workspace/ComfyUI install
```

### 6. Start ComfyUI

```bash
cd /workspace/ComfyUI
python main.py --listen 0.0.0.0 --multi-user
```

Access via browser: `http://<SERVER_IP>:8188`

> **Note**: If using Jupyter SSH, kill existing process first: `pkill -f python`

### 7. Setup Comani

```bash
cd /workspace && git clone https://github.com/Delva0/Comani
cd /workspace/comani && pip install -e .
```

---

## CLI Usage

```bash
# Check ComfyUI connection
comani health

# List available presets/workflows
comani list-presets
comani list-workflows

# Execute a preset
comani execute anikawaxl_girl
comani execute cyberpunk_city -p seed=42 -p steps=30

# Download models (interactive)
comani download

# Download models from package path
comani download sdxl/loras/artists
comani download wan/base

# List all available model packages
comani download --list

# Queue management
comani queue
comani interrupt
comani clear
```

---

## Installation

```bash
# Install from source
pip install -e .

# Or install directly
pip install git+https://github.com/Delva0/Comani
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `COMFYUI_URL` | ComfyUI server URL | `http://127.0.0.1:8188` |
| `COMFYUI_ROOT` | ComfyUI installation directory | `/workspace/ComfyUI` |
| `CIVITAI_API_TOKEN` | Civitai API token for model downloads | - |
| `HF_TOKEN` | HuggingFace API token | - |
| `SERVER_IP` | Remote server IP for sync scripts | - |
| `SERVER_PORT` | Remote server SSH port for sync scripts | - |
