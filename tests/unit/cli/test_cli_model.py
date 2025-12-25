"""
Tests for the model CLI commands.

Uses Python-like naming convention:
  - Package: directory (e.g., "sdxl")
  - Module: YAML file (e.g., "sdxl.lora_artist")
  - Model/Group: definitions within a module
"""

from unittest.mock import patch, MagicMock
from argparse import Namespace

import pytest

from comani.cli.cmd_model import (
    cmd_model_list,
    cmd_model_download,
    _get_registry,
)

@pytest.fixture(autouse=True)
def clear_config():
    """Clear the cached config singleton before each test."""
    import comani.config
    comani.config._config = None
    yield
    comani.config._config = None

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
        args = Namespace(targets=[".wan.wan22_animate"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "wan22_animate" in captured.out
        assert "wan2_2_animate_14b" in captured.out.lower() or "animate" in captured.out.lower()

    def test_list_module(self, capsys):
        """Test listing all models in a module."""
        args = Namespace(targets=[".detection"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        assert "vitpose" in captured.out.lower()
        assert "yolov10m" in captured.out.lower()

    def test_list_multiple_targets(self, capsys):
        """Test listing multiple targets at once."""
        args = Namespace(targets=[".wan.wan22_animate", ".detection", ".upscale"])
        result = cmd_model_list(args)
        assert result == 0

        captured = capsys.readouterr()
        # Should show target analysis
        assert "target analysis" in captured.out.lower()
        assert "group" in captured.out.lower()
        assert "module" in captured.out.lower()
        assert "Total" in captured.out

    def test_list_wildcard_pattern(self, capsys):
        """Test listing with wildcard pattern."""
        args = Namespace(targets=[".sdxl.lora_*"])
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
            targets=[".wan.wan22_i2v_fp8"],
            comfyui_root=None,
            dry_run=True,
        )
        with patch("comani.core.engine.get_downloader"):
            result = cmd_model_download(args)
            assert result == 0

        captured = capsys.readouterr()
        assert "DRY-RUN" in captured.out
        assert "Would download" in captured.out

    def test_download_dry_run_multiple(self, capsys):
        """Test download with dry-run flag for multiple targets."""
        args = Namespace(
            targets=[".wan.wan22_i2v_fp8", ".detection"],
            comfyui_root=None,
            dry_run=True,
        )
        with patch("comani.core.engine.get_downloader"):
            result = cmd_model_download(args)
            assert result == 0

        captured = capsys.readouterr()
        # assert "Target Analysis" in captured.out  # Removed in Engine implementation
        assert "DRY-RUN" in captured.out
        assert "Would download" in captured.out

    def test_download_nonexistent(self, capsys):
        """Test download with nonexistent target."""
        args = Namespace(
            targets=["nonexistent.target"],
            comfyui_root=None,
            dry_run=True,
        )
        with patch("comani.core.engine.get_downloader"):
            result = cmd_model_download(args)
            assert result == 1

        captured = capsys.readouterr()
        assert "No models found" in captured.out

    def test_download_uses_model_downloader(self, capsys, monkeypatch, tmp_path):
        """Test that download command uses ModelDownloader class."""
        from comani.model.model_downloader import ModelDownloader

        mock_downloader = MagicMock()
        mock_downloader.download_by_ids.return_value = True

        # Mock ModelDownloader in its home module
        with patch("comani.model.model_downloader.ModelDownloader", return_value=mock_downloader):
            # Also mock get_downloader to avoid connection attempts
            with patch("comani.core.engine.get_downloader"):
                monkeypatch.setenv("COMANI_COMFYUI_DIR", str(tmp_path))

                args = Namespace(
                    targets=[".detection"],
                    comfyui_root=str(tmp_path),
                    dry_run=False,
                )
                cmd_model_download(args)

                # Should have called download_by_ids
                mock_downloader.download_by_ids.assert_called_once()


class TestGetRegistry:
    """Tests for registry creation."""

    def test_get_registry_returns_registry(self):
        """Test that _get_registry returns a valid registry."""
        registry = _get_registry()
        assert registry is not None
        modules = registry.list_modules()
        assert len(modules) > 0
