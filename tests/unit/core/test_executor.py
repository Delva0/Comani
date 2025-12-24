from unittest.mock import MagicMock
from comani.core.executor import Executor, set_nested_value, get_nested_value
from comani.core.preset import Preset, ParamMapping

def test_nested_value_utils():
    """Test set_nested_value and get_nested_value."""
    d = {"a": {"b": [1, 2, {"c": 3}]}}

    assert get_nested_value(d, "a.b.2.c") == 3

    set_nested_value(d, "a.b.2.c", 4)
    assert d["a"]["b"][2]["c"] == 4

    set_nested_value(d, "a.b.0", 10)
    assert d["a"]["b"][0] == 10

class TestExecutor:
    """Tests for Executor."""

    def test_apply_preset(self):
        """Test applying preset parameters to a workflow."""
        mock_client = MagicMock()
        mock_loader = MagicMock()
        mock_presets = MagicMock()
        executor = Executor(mock_client, mock_loader, mock_presets)

        workflow = {
            "10": {
                "inputs": {"text": "original"}
            }
        }

        preset = Preset(
            name="test",
            base_workflow="test_wf",
            params={"prompt": "new text"},
            mapping={
                "prompt": ParamMapping(node_id="10", field_path="inputs.text")
            }
        )

        new_workflow = executor.apply_preset(workflow, preset)
        assert new_workflow["10"]["inputs"]["text"] == "new text"
        assert workflow["10"]["inputs"]["text"] == "original"  # Original should be unchanged
