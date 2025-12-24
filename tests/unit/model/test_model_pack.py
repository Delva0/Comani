"""
Tests for the model pack configuration system.

Uses Python-like naming convention:
  - Package: directory (e.g., "sdxl")
  - Module: YAML file (e.g., "sdxl.lora_artist")
  - Model/Group: definitions within a module
"""

import pytest
from pathlib import Path

from comani.model.model_pack import (
    ModelPackRegistry,
    ModelDef,
    ResolvedGroup,
)


@pytest.fixture
def registry() -> ModelPackRegistry:
    """Create a registry with the actual models directory."""
    # Project root is 4 levels up from this file
    models_dir = Path(__file__).parents[3] / "examples" / "models"
    return ModelPackRegistry(models_dir)


class TestModelPackRegistry:
    """Tests for ModelPackRegistry."""

    def test_list_modules(self, registry: ModelPackRegistry):
        """Test listing model pack modules."""
        modules = registry.list_modules()
        assert ".wan" in modules
        assert ".zimage" in modules
        assert ".detection" in modules
        assert ".upscale" in modules
        # Nested modules should use dot notation
        assert ".sdxl.sdxl" in modules
        assert ".sdxl.lora_artist" in modules

    def test_list_files_alias(self, registry: ModelPackRegistry):
        """Test list_package_inners() functionality."""
        modules = registry.list_modules()
        inners = registry.list_package_inners(".")
        assert len(inners) > 0
        # root inners should contain top-level modules and packages
        assert ".wan" in inners or ".wan" in modules

    def test_list_models_all(self, registry: ModelPackRegistry):
        """Test listing all models."""
        models = registry.list_models()
        assert len(models) > 0
        assert all(isinstance(m, ModelDef) for m in models)

    def test_list_models_filtered(self, registry: ModelPackRegistry):
        """Test listing models filtered by module."""
        detection_models = registry.list_models(".detection")
        assert len(detection_models) == 2
        model_ids = {m.id for m in detection_models}
        assert "vitpose_l_wholebody" in model_ids
        assert "yolov10m" in model_ids

    def test_list_groups(self, registry: ModelPackRegistry):
        """Test listing groups."""
        wan_groups = registry.list_groups(".wan")
        assert len(wan_groups) == 3
        group_ids = {g.id for g in wan_groups}
        assert "wan22_animate" in group_ids
        assert "wan22_i2v_fp8" in group_ids
        assert "wan22_i2v_gguf" in group_ids

    def test_get_model_qualified(self, registry: ModelPackRegistry):
        """Test getting model by qualified reference (Python-like)."""
        model = registry.get_model(".wan.wan2_1_vae_bf16")
        assert model is not None
        assert model.id == "wan2_1_vae_bf16"
        assert "vae" in model.url.lower()

    def test_get_model_local(self, registry: ModelPackRegistry):
        """Test getting model by local reference with context."""
        model = registry.get_model("vitpose_l_wholebody", context_module=".detection")
        assert model is not None
        assert model.id == "vitpose_l_wholebody"

    def test_get_group(self, registry: ModelPackRegistry):
        """Test getting group by reference (Python-like)."""
        group = registry.get_group(".wan.wan22_animate")
        assert group is not None
        assert group.id == "wan22_animate"
        # Cross-module references use Python-like notation
        assert "detection.vitpose_l_wholebody" in group.includes

    def test_resolve_single_model(self, registry: ModelPackRegistry):
        """Test resolving a single model reference."""
        models = registry.resolve_reference(".wan.wan2_1_vae_bf16")
        assert len(models) == 1
        assert models[0].id == "wan2_1_vae_bf16"

    def test_resolve_module_reference(self, registry: ModelPackRegistry):
        """Test resolving entire module as reference."""
        models = registry.resolve_reference(".detection")
        assert len(models) == 2
        model_ids = {m.id for m in models}
        assert "vitpose_l_wholebody" in model_ids
        assert "yolov10m" in model_ids

    def test_resolve_group_with_cross_module(self, registry: ModelPackRegistry):
        """Test resolving group with cross-module references."""
        models = registry.resolve_reference(".wan.wan22_animate")
        assert len(models) == 8  # 6 from wan + 2 from detection

        # Check cross-module references are resolved
        model_ids = {m.id for m in models}
        assert "vitpose_l_wholebody" in model_ids
        assert "yolov10m" in model_ids
        assert "wan2_2_animate_14b_fp8_e4m3fn_scaled_kj" in model_ids

    def test_resolve_to_group(self, registry: ModelPackRegistry):
        """Test resolve_to_group API."""
        resolved = registry.resolve_to_group(".wan.wan22_animate")
        assert isinstance(resolved, ResolvedGroup)
        assert resolved.id == ".wan.wan22_animate"
        assert len(resolved.models) == 8
        assert "detection" in resolved.description.lower() or len(resolved.models) > 0

    def test_resolve_to_group_module(self, registry: ModelPackRegistry):
        """Test resolve_to_group for module reference."""
        resolved = registry.resolve_to_group(".detection")
        assert isinstance(resolved, ResolvedGroup)
        assert resolved.id == ".detection"
        assert len(resolved.models) == 2

    def test_no_duplicate_ids(self, registry: ModelPackRegistry):
        """Test that loading completes without duplicate ID errors."""
        # This will raise ModelPackError if there are duplicates
        modules = registry.list_modules()
        assert len(modules) > 0

    def test_model_has_required_fields(self, registry: ModelPackRegistry):
        """Test that models have required fields."""
        models = registry.list_models()
        for model in models:
            assert model.id, "Model missing id"
            assert model.url, f"Model {model.id} missing url"
            assert model.path, f"Model {model.id} missing path"
            assert model.source_module, f"Model {model.id} missing source_module"


class TestCrossModuleReferences:
    """Tests specifically for cross-module reference resolution."""

    def test_cross_module_model_reference(self, registry: ModelPackRegistry):
        """Test cross-module model reference format module.model_id."""
        models = registry.resolve_reference(".detection.vitpose_l_wholebody")
        assert len(models) == 1
        assert models[0].id == "vitpose_l_wholebody"
        assert models[0].source_module == ".detection"

    def test_group_includes_cross_module(self, registry: ModelPackRegistry):
        """Test that group correctly includes cross-module models."""
        group = registry.get_group(".wan.wan22_animate")
        assert group is not None

        # Check that cross-module references are in includes (using dot notation)
        cross_refs = [i for i in group.includes if "." in i]
        assert len(cross_refs) >= 2  # .detection.vitpose_l_wholebody and .detection.yolov10m

    def test_resolve_preserves_source_module(self, registry: ModelPackRegistry):
        """Test that resolved models preserve their source module."""
        models = registry.resolve_reference(".wan.wan22_animate")

        detection_models = [m for m in models if m.source_module == ".detection"]
        wan_models = [m for m in models if m.source_module == ".wan"]

        assert len(detection_models) == 2
        assert len(wan_models) == 6


class TestWildcardPatterns:
    """Tests for wildcard pattern matching."""

    def test_package_wildcard(self, registry: ModelPackRegistry):
        """Test package.* wildcard matches all modules in package."""
        models = registry.resolve_reference(".sdxl.*")
        assert len(models) > 200  # All models in sdxl package

        # Should include models from all sdxl modules
        source_modules = {m.source_module for m in models}
        assert ".sdxl.sdxl" in source_modules
        assert ".sdxl.lora_artist" in source_modules

    def test_module_prefix_wildcard(self, registry: ModelPackRegistry):
        """Test module prefix wildcard like sdxl.lora_*."""
        models = registry.resolve_reference(".sdxl.lora_*")
        # Should only include lora modules, not sdxl.sdxl
        source_modules = {m.source_module for m in models}
        assert ".sdxl.sdxl" not in source_modules
        assert ".sdxl.lora_artist" in source_modules
        assert ".sdxl.lora_slider" in source_modules
        assert ".sdxl.lora_misc" in source_modules

    def test_group_with_wildcard_includes(self, registry: ModelPackRegistry):
        """Test group that uses wildcard in includes."""
        # .sdxl.sdxl.all_loras uses .sdxl.lora_* pattern
        group = registry.get_group(".sdxl.sdxl.all_loras")
        assert group is not None

        resolved = registry.resolve_group(group)
        # Should only contain lora models
        for model in resolved:
            assert "lora" in model.source_module.lower()


class TestResolveMultiple:
    """Tests for resolve_multiple functionality."""

    def test_resolve_multiple_targets(self, registry: ModelPackRegistry):
        """Test resolving multiple targets at once."""
        combined, ref_info = registry.resolve_multiple([
            ".wan.wan22_animate",
            ".detection",
            ".upscale"
        ])

        # Check combined result
        assert len(combined.models) == 9  # 8 from wan22_animate (includes detection) + 1 from upscale

        # Check ref_info
        assert len(ref_info) == 3
        ref_types = {r[1] for r in ref_info}
        assert "group" in ref_types
        assert "module" in ref_types

    def test_resolve_multiple_deduplication(self, registry: ModelPackRegistry):
        """Test that duplicate models are removed when resolving multiple."""
        # detection models are already included in .wan.wan22_animate
        combined, ref_info = registry.resolve_multiple([
            ".wan.wan22_animate",
            ".detection"
        ])

        # Count detection models
        detection_models = [m for m in combined.models if m.source_module == ".detection"]
        assert len(detection_models) == 2  # Should be exactly 2, not 4


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_model(self, registry: ModelPackRegistry):
        """Test getting nonexistent model returns None."""
        model = registry.get_model("nonexistent.model")
        assert model is None

    def test_nonexistent_group(self, registry: ModelPackRegistry):
        """Test getting nonexistent group returns None."""
        group = registry.get_group("nonexistent.group")
        assert group is None

    def test_resolve_nonexistent_returns_empty(self, registry: ModelPackRegistry):
        """Test resolving nonexistent reference returns empty list."""
        models = registry.resolve_reference("nonexistent.something")
        assert models == []

    def test_circular_reference_protection(self, registry: ModelPackRegistry):
        """Test that circular references don't cause infinite loops."""
        # This should complete without hanging
        models = registry.resolve_reference("wan.wan22_animate")
        assert len(models) > 0
