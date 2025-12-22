"""
Tests for the model CLI commands.

Uses Python-like naming convention:
  - Package: directory (e.g., "sdxl")
  - Module: YAML file (e.g., "sdxl.lora_artist")
  - Model/Group: definitions within a module
"""

import pytest
from unittest.mock import patch, MagicMock
from argparse import Namespace

from comani.cli.commands import (
    cmd_model_list,
    cmd_model_download,
    _get_registry,
    _models_to_download_specs,
)
from comani.core.model_pack import ModelDef


class TestModelListCommand:
    """Tests for the model list command."""

    def test_list_all(self, capsys):
        """Test listing all models."""
        args = Namespace(targets=[])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Available Model Packs" in captured.out
        assert "wan" in captured.out
        assert "sdxl" in captured.out

    def test_list_specific_group(self, capsys):
        """Test listing specific group (Python-like syntax)."""
        args = Namespace(targets=["wan.wan22_animate"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "wan22_animate" in captured.out
        assert "wan2_2_animate_14b" in captured.out.lower() or "animate" in captured.out.lower()

    def test_list_module(self, capsys):
        """Test listing all models in a module."""
        args = Namespace(targets=["detection"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "vitpose" in captured.out.lower()
        assert "yolov10m" in captured.out.lower()

    def test_list_multiple_targets(self, capsys):
        """Test listing multiple targets at once."""
        args = Namespace(targets=["wan.wan22_animate", "detection", "upscale"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        # Should show target analysis
        assert "Target Analysis" in captured.out
        assert "group" in captured.out.lower()
        assert "module" in captured.out.lower()
        assert "Total" in captured.out

    def test_list_wildcard_pattern(self, capsys):
        """Test listing with wildcard pattern."""
        args = Namespace(targets=["sdxl.lora_*"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Models" in captured.out
        # Should include lora models
        assert "lora" in captured.out.lower()

    def test_list_nonexistent(self, capsys):
        """Test listing nonexistent target."""
        args = Namespace(targets=["nonexistent.target"])
        result = cmd_model_list(args)
        assert result == 1

        captured = capsys.readouterr()
        assert "No models found" in captured.out


class TestModelDownloadCommand:
    """Tests for the model download command."""

    def test_download_dry_run_single(self, capsys):
        """Test download with dry-run flag for single target."""
        args = Namespace(
            targets=["wan.wan22_i2v_fp8"],
            comfyui_root=None,
            dry_run=True,
        )
        result = cmd_model_download(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out
        assert "Would download" in captured.out

    def test_download_dry_run_multiple(self, capsys):
        """Test download with dry-run flag for multiple targets."""
        args = Namespace(
            targets=["wan.wan22_animate", "upscale"],
            comfyui_root=None,
            dry_run=True,
        )
        result = cmd_model_download(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "Target Analysis" in captured.out
        assert "DRY-RUN" in captured.out
        assert "Would download" in captured.out

    def test_download_nonexistent(self, capsys):
        """Test downloading nonexistent target."""
        args = Namespace(
            targets=["nonexistent.target"],
            comfyui_root=None,
            dry_run=True,
        )
        result = cmd_model_download(args)
        assert result == 1

        captured = capsys.readouterr()
        assert "No models found" in captured.out


class TestModelsToDownloadSpecs:
    """Tests for the _models_to_download_specs function."""

    def test_basic_conversion(self):
        """Test basic model to spec conversion."""
        models = [
            ModelDef(
                id="test_vae",
                url="https://example.com/vae.safetensors",
                path="models/vae/test_vae.safetensors",
                source_module="test",
            ),
            ModelDef(
                id="test_checkpoint",
                url="https://example.com/checkpoint.safetensors",
                path="models/checkpoints/test_checkpoint.safetensors",
                source_module="test",
            ),
        ]

        specs = _models_to_download_specs(models)

        assert "vae" in specs
        assert "checkpoints" in specs
        assert len(specs["vae"]) == 1
        assert len(specs["checkpoints"]) == 1
        assert specs["vae"][0]["url"] == "https://example.com/vae.safetensors"

    def test_multiple_same_subdir(self):
        """Test multiple models in same subdirectory."""
        models = [
            ModelDef(
                id="lora1",
                url="https://example.com/lora1.safetensors",
                path="models/loras/lora1.safetensors",
                source_module="test",
            ),
            ModelDef(
                id="lora2",
                url="https://example.com/lora2.safetensors",
                path="models/loras/lora2.safetensors",
                source_module="test",
            ),
        ]

        specs = _models_to_download_specs(models)

        assert "loras" in specs
        assert len(specs["loras"]) == 2


class TestGetRegistry:
    """Tests for registry creation."""

    def test_get_registry_returns_registry(self):
        """Test that _get_registry returns a valid registry."""
        registry = _get_registry()
        assert registry is not None
        modules = registry.list_modules()
        assert len(modules) > 0
