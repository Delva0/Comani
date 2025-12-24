"""
Tests for DependencyResolver.

Tests dependency resolution using ModelPackRegistry with Python-like naming:
  - "sdxl.sdxl.anikawaxl_v2" - fully qualified model reference
  - "sdxl.lora_*" - wildcard pattern
  - ["ref1", "ref2"] - multiple references
"""

import tempfile
from pathlib import Path

import pytest

from comani.model.model_dependency import DependencyResolver, DependencyError


class TestDependencyResolver:
    """Test DependencyResolver with ModelPackRegistry."""

    @pytest.fixture
    def temp_models_dir(self):
        """Create a temporary models directory with test model packs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            models_dir = Path(tmpdir)

            # Create sdxl directory
            sdxl_dir = models_dir / "sdxl"
            sdxl_dir.mkdir(parents=True)

            # Create sdxl.yml with test models
            sdxl_yml = sdxl_dir / "sdxl.yml"
            sdxl_yml.write_text("""
models:
  anikawaxl_v2:
    url: "https://huggingface.co/test/anikawaxl_v2.safetensors"
    path: "models/checkpoints/anikawaxl_v2.safetensors"
    description: "AniKawaXL v2 model"

  base_model:
    url: "https://huggingface.co/test/base.safetensors"
    path: "models/checkpoints/base.safetensors"

groups:
  all_sdxl:
    description: "All SDXL models"
    includes:
      - "anikawaxl_v2"
      - "base_model"
""")

            # Create lora_artist.yml
            lora_yml = sdxl_dir / "lora_artist.yml"
            lora_yml.write_text("""
models:
  style_lora:
    url: "https://huggingface.co/test/style.safetensors"
    path: "models/loras/style.safetensors"
    description: "Style LoRA"

  anime_lora:
    url: "https://huggingface.co/test/anime.safetensors"
    path: "models/loras/anime.safetensors"
""")

            yield models_dir

    def test_resolve_single_model(self, temp_models_dir):
        """Resolving a single model reference should work."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.resolve([".sdxl.sdxl.anikawaxl_v2"])

        assert len(deps) == 1
        assert deps[0].model_type == "checkpoints"
        assert deps[0].name == "anikawaxl_v2.safetensors"
        assert deps[0].needs_download is True
        assert deps[0].model_def is not None
        assert deps[0].model_def.id == "anikawaxl_v2"

    def test_resolve_multiple_models(self, temp_models_dir):
        """Resolving multiple model references should work."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.resolve([
            ".sdxl.sdxl.anikawaxl_v2",
            ".sdxl.lora_artist.style_lora"
        ])

        assert len(deps) == 2

        checkpoint_dep = next(d for d in deps if d.model_type == "checkpoints")
        lora_dep = next(d for d in deps if d.model_type == "loras")

        assert checkpoint_dep.name == "anikawaxl_v2.safetensors"
        assert lora_dep.name == "style.safetensors"

    def test_resolve_group(self, temp_models_dir):
        """Resolving a group should expand to all included models."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.resolve([".sdxl.sdxl.all_sdxl"])

        assert len(deps) == 2
        model_names = {d.name for d in deps}
        assert "anikawaxl_v2.safetensors" in model_names
        assert "base.safetensors" in model_names

    def test_resolve_module(self, temp_models_dir):
        """Resolving a module should expand to all models in it."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.resolve([".sdxl.lora_artist"])

        assert len(deps) == 2
        model_names = {d.name for d in deps}
        assert "style.safetensors" in model_names
        assert "anime.safetensors" in model_names

    def test_resolve_wildcard(self, temp_models_dir):
        """Resolving a wildcard should match multiple modules/models."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.resolve([".sdxl.*"])

        assert len(deps) == 4
        model_names = {d.name for d in deps}
        assert "anikawaxl_v2.safetensors" in model_names
        assert "base.safetensors" in model_names
        assert "style.safetensors" in model_names
        assert "anime.safetensors" in model_names

    def test_resolve_nonexistent(self, temp_models_dir):
        """Resolving a nonexistent reference should raise error."""
        resolver = DependencyResolver(temp_models_dir)

        with pytest.raises(DependencyError) as exc_info:
            resolver.resolve(["nonexistent.model"])

        assert "No models found" in str(exc_info.value)

    def test_validate_only_with_errors(self, temp_models_dir):
        """validate_only should return errors without raising."""
        resolver = DependencyResolver(temp_models_dir)

        resolved, errors = resolver.validate_only([
            ".sdxl.sdxl.anikawaxl_v2",
            "nonexistent.model"
        ])

        assert len(resolved) == 1
        assert len(errors) == 1
        assert "No models found" in errors[0]

    def test_ensure_dependencies_dry_run(self, temp_models_dir, capsys):
        """ensure_dependencies with dry_run should print what would be downloaded."""
        resolver = DependencyResolver(temp_models_dir)

        deps = resolver.ensure_dependencies([".sdxl.sdxl.anikawaxl_v2"], dry_run=True)

        assert len(deps) == 1
        captured = capsys.readouterr()
        assert "[DRY-RUN]" in captured.out
        assert "anikawaxl_v2.safetensors" in captured.out


class TestPresetIntegration:
    """Test integration with Preset class."""

    @pytest.fixture
    def temp_preset_file(self):
        """Create a temporary preset file with new format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            preset_path = Path(tmpdir) / "test_preset.yml"
            preset_path.write_text("""
name: "Test Preset"
base_workflow: "test.json"

dependencies:
  - "sdxl.sdxl.anikawaxl_v2"
  - "sdxl.lora_artist.style_lora"

params:
  positive_prompt: "test"

mapping:
  positive_prompt:
    node_id: "1"
    field_path: "inputs.text"
""")
            yield preset_path

    def test_preset_loads_list_dependencies(self, temp_preset_file):
        """Preset should load dependencies as a list."""
        from comani.core.preset import Preset

        preset = Preset.from_yaml(temp_preset_file)

        assert preset.name == "Test Preset"
        assert isinstance(preset.dependencies, list)
        assert len(preset.dependencies) == 2
        assert "sdxl.sdxl.anikawaxl_v2" in preset.dependencies
        assert "sdxl.lora_artist.style_lora" in preset.dependencies


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
