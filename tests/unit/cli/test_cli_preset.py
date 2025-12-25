"""
Tests for the preset CLI commands.
"""

from unittest.mock import patch
from argparse import Namespace
from comani.cli.cmd_preset import cmd_preset_list


class TestPresetListCommand:
    """Tests for the preset list command."""

    def test_list_presets(self, capsys):
        """Test listing all presets."""
        mock_presets = ["preset1", "preset2"]
        with patch("comani.cli.cmd_preset.ComaniEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.list_presets.return_value = mock_presets

            args = Namespace(preset_action="list")
            result = cmd_preset_list(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "preset1" in captured.out
            assert "preset2" in captured.out
            mock_engine.list_presets.assert_called_once()
