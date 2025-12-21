1. 为什么基模不全部使用更简洁的yml？因为yml的格式过于死板，不能很好得展现模型下载中的最佳实践。
2. 为什么lora又使用yml？因为lora通常的需求是大批量下载、由用户谨慎挑选，无需在代码中展现进行复杂选择逻辑，因此使用yml更合适。


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
