"""
Tests for DependencyResolver.

Tests all dependency parsing formats:
1. Plain model name: checkpoint: "model.safetensors"
2. Model name list: checkpoint: ["model1.safetensors", "model2.safetensors"]
3. Direct URL: checkpoint: "https://example.com/model.safetensors"
4. Dict with url/name: checkpoint: {"url": "https://...", "name": "model.safetensors"}
"""

import tempfile
from pathlib import Path

import pytest

from comani.core.dependency import (
    DependencyResolver,
    DependencyError,
    _is_url,
    _normalize_dependency_item,
)
from comani.utils.model_downloader import DownloadItem, DownloadType


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_url_http(self):
        assert _is_url("http://example.com/model.safetensors")

    def test_is_url_https(self):
        assert _is_url("https://example.com/model.safetensors")

    def test_is_url_plain_name(self):
        assert not _is_url("model.safetensors")

    def test_is_url_path(self):
        assert not _is_url("/path/to/model.safetensors")

    def test_normalize_plain_name_returns_none(self):
        """Plain model names should return None (not URL-like)."""
        result = _normalize_dependency_item("model.safetensors")
        assert result is None

    def test_normalize_direct_url(self):
        """URLs should be normalized to DownloadItem."""
        result = _normalize_dependency_item("https://example.com/model.safetensors")
        assert result is not None
        assert isinstance(result, DownloadItem)
        assert result.url == "https://example.com/model.safetensors"
        assert result.type == DownloadType.DIRECT_URL

    def test_normalize_dict_with_url(self):
        """Dict with url should be normalized."""
        result = _normalize_dependency_item({
            "url": "https://example.com/model.safetensors",
            "name": "custom_name.safetensors",
        })
        assert result is not None
        assert result.url == "https://example.com/model.safetensors"
        assert result.name == "custom_name.safetensors"

    def test_normalize_civitai_url(self):
        """Civitai URLs should be detected correctly."""
        result = _normalize_dependency_item("https://civitai.com/models/123456")
        assert result is not None
        assert result.type == DownloadType.CIVIT_FILE

    def test_normalize_hf_file_url(self):
        """HuggingFace file URLs should be detected correctly."""
        result = _normalize_dependency_item(
            "https://huggingface.co/user/repo/blob/main/model.safetensors"
        )
        assert result is not None
        assert result.type == DownloadType.HF_FILE


class TestDependencyResolver:
    """Test DependencyResolver with various dependency formats."""

    @pytest.fixture
    def temp_comfyui_dir(self):
        """Create a temporary ComfyUI directory structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            comfyui_root = Path(tmpdir)
            models_dir = comfyui_root / "models"

            # Create subdirectories
            (models_dir / "checkpoints").mkdir(parents=True)
            (models_dir / "loras").mkdir()
            (models_dir / "vae").mkdir()

            yield comfyui_root

    # =========================================================================
    # Test format 1: Plain model name (existing file)
    # =========================================================================
    def test_resolve_plain_name_exists(self, temp_comfyui_dir):
        """Plain model name should resolve if file exists."""
        # Create fake model file
        model_path = temp_comfyui_dir / "models" / "checkpoints" / "existing_model.safetensors"
        model_path.write_bytes(b"fake model data")

        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({"checkpoint": "existing_model.safetensors"})
        assert len(deps) == 1
        assert deps[0].name == "existing_model.safetensors"
        assert deps[0].needs_download is False
        assert deps[0].path == model_path

    def test_resolve_plain_name_not_found(self, temp_comfyui_dir):
        """Plain model name should raise error if not found."""
        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        with pytest.raises(DependencyError) as exc_info:
            resolver.resolve({"checkpoint": "unknown_model.safetensors"})

        assert "not found" in str(exc_info.value).lower()

    # =========================================================================
    # Test format 2: Model name list
    # =========================================================================
    def test_resolve_name_list_all_existing(self, temp_comfyui_dir):
        """Model name list should resolve all items."""
        # Create existing models
        model1_path = temp_comfyui_dir / "models" / "checkpoints" / "model1.safetensors"
        model1_path.write_bytes(b"fake")
        model2_path = temp_comfyui_dir / "models" / "checkpoints" / "model2.safetensors"
        model2_path.write_bytes(b"fake")

        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": ["model1.safetensors", "model2.safetensors"]
        })

        assert len(deps) == 2
        assert deps[0].name == "model1.safetensors"
        assert deps[0].needs_download is False
        assert deps[1].name == "model2.safetensors"
        assert deps[1].needs_download is False

    # =========================================================================
    # Test format 3: Direct URL (temporary dependency)
    # =========================================================================
    def test_resolve_direct_url(self, temp_comfyui_dir):
        """Direct URL should create download item."""
        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": "https://example.com/custom_model.safetensors"
        })

        assert len(deps) == 1
        assert deps[0].needs_download is True
        assert deps[0].download_item is not None
        assert deps[0].download_item.url == "https://example.com/custom_model.safetensors"

    def test_resolve_direct_url_already_exists(self, temp_comfyui_dir):
        """Direct URL should not download if file already exists."""
        # Create existing file
        model_path = temp_comfyui_dir / "models" / "checkpoints" / "custom_model.safetensors"
        model_path.write_bytes(b"fake")

        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": "https://example.com/custom_model.safetensors"
        })

        assert len(deps) == 1
        assert deps[0].needs_download is False

    # =========================================================================
    # Test format 4: Dict with url/name
    # =========================================================================
    def test_resolve_dict_with_url_name(self, temp_comfyui_dir):
        """Dict with url and name should work."""
        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": {
                "url": "https://civitai.com/models/123456",
                "name": "my_custom_model.safetensors",
            }
        })

        assert len(deps) == 1
        assert deps[0].name == "my_custom_model.safetensors"
        assert deps[0].needs_download is True
        assert deps[0].download_item is not None
        assert "civitai" in deps[0].download_item.url

    def test_resolve_dict_already_exists(self, temp_comfyui_dir):
        """Dict dependency should not download if file exists."""
        model_path = temp_comfyui_dir / "models" / "checkpoints" / "my_model.safetensors"
        model_path.write_bytes(b"fake")

        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": {
                "url": "https://example.com/something.safetensors",
                "name": "my_model.safetensors",
            }
        })

        assert len(deps) == 1
        assert deps[0].needs_download is False

    # =========================================================================
    # Test multiple model types
    # =========================================================================
    def test_resolve_multiple_types(self, temp_comfyui_dir):
        """Should handle multiple model types in one call."""
        # Create existing checkpoint
        (temp_comfyui_dir / "models" / "checkpoints" / "base.safetensors").write_bytes(b"fake")

        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        deps = resolver.resolve({
            "checkpoint": "base.safetensors",
            "lora": "https://example.com/style.safetensors",
            "vae": {"url": "https://example.com/vae.safetensors", "name": "custom_vae.safetensors"},
        })

        assert len(deps) == 3

        checkpoint_dep = next(d for d in deps if d.model_type == "checkpoint")
        lora_dep = next(d for d in deps if d.model_type == "lora")
        vae_dep = next(d for d in deps if d.model_type == "vae")

        assert checkpoint_dep.needs_download is False
        assert lora_dep.needs_download is True
        assert vae_dep.needs_download is True
        assert vae_dep.name == "custom_vae.safetensors"

    # =========================================================================
    # Test validate_only
    # =========================================================================
    def test_validate_only_with_errors(self, temp_comfyui_dir):
        """validate_only should return errors without raising."""
        resolver = DependencyResolver(
            comfyui_models_dir=temp_comfyui_dir / "models",
        )

        resolved, errors = resolver.validate_only({
            "checkpoint": "nonexistent.safetensors",
            "lora": "https://example.com/valid.safetensors",
        })

        assert len(resolved) == 1
        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    # =========================================================================
    # Test without COMFY_UI_DIR
    # =========================================================================
    def test_resolve_without_comfyui_dir_url_error(self):
        """Without ComfyUI dir, URL dependencies should error on download."""
        resolver = DependencyResolver(
            comfyui_models_dir=None,
        )

        with pytest.raises(DependencyError) as exc_info:
            resolver.resolve({"checkpoint": "https://example.com/model.safetensors"})

        assert "COMFY_UI_DIR" in str(exc_info.value)


class TestPresetIntegration:
    """Test integration with Preset class."""

    @pytest.fixture
    def temp_preset_file(self):
        """Create a temporary preset file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / "test_preset.yml"
            preset_path.write_text("""
name: "Test Preset"
base_workflow: "test.json"

dependencies:
  checkpoint: "anikawaxl_v2.safetensors"
  lora:
    - "style_lora.safetensors"
    - url: "https://civitai.com/models/123"
      name: "custom_lora.safetensors"

params:
  positive_prompt: "test"

mapping:
  positive_prompt:
    node_id: "1"
    field_path: "inputs.text"
""")
            yield preset_path

    def test_preset_loads_flexible_dependencies(self, temp_preset_file):
        """Preset should load flexible dependencies format."""
        from comani.core.preset import Preset

        preset = Preset.from_yaml(temp_preset_file)

        assert preset.name == "Test Preset"
        assert "checkpoint" in preset.dependencies
        assert preset.dependencies["checkpoint"] == "anikawaxl_v2.safetensors"

        assert "lora" in preset.dependencies
        loras = preset.dependencies["lora"]
        assert isinstance(loras, list)
        assert len(loras) == 2
        assert loras[0] == "style_lora.safetensors"
        assert isinstance(loras[1], dict)
        assert loras[1]["url"] == "https://civitai.com/models/123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
