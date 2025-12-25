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
        executor = Executor(mock_client)

        workflow = {
            "10": {
                "inputs": {"text": "original"}
            }
        }

        preset = Preset(
            name="test",
            workflow="test_wf",
            params={"prompt": "new text"},
            mapping={
                "prompt": [ParamMapping(node_id="10", field_path="inputs.text")]
            }
        )

        new_workflow = executor.apply_preset(workflow, preset)
        assert new_workflow["10"]["inputs"]["text"] == "new text"
        assert workflow["10"]["inputs"]["text"] == "original"  # Original should be unchanged

    def test_execute_workflow_dict(self):
        """Test execute_workflow with dictionaries."""
        mock_client = MagicMock()
        executor = Executor(mock_client)

        workflow = {"1": {"inputs": {"a": 1}}}
        preset = {"params": {"p": 2}, "mapping": {"p": "1:inputs.a"}}

        executor.execute_workflow(workflow=workflow, preset=preset)

        # Verify client.execute was called with modified workflow
        args, kwargs = mock_client.execute.call_args
        executed_workflow = args[0]
        assert executed_workflow["1"]["inputs"]["a"] == 2

    def test_execute_workflow_by_name_workflow_only(self):
        """Test execute_workflow_by_name with only workflow_name."""
        mock_client = MagicMock()
        executor = Executor(mock_client)

        mock_loader = MagicMock()
        mock_loader.load.return_value = {"1": {"inputs": {"a": 1}}}

        executor.execute_workflow_by_name(
            workflow_name="test_wf",
            workflow_loader=mock_loader
        )

        mock_loader.load.assert_called_with("test_wf")
        args, _ = mock_client.execute.call_args
        assert args[0]["1"]["inputs"]["a"] == 1

    def test_execute_workflow_by_name_preset_only(self):
        """Test execute_workflow_by_name with only preset_name."""
        mock_client = MagicMock()
        executor = Executor(mock_client)

        mock_loader = MagicMock()
        mock_loader.load.return_value = {"1": {"inputs": {"a": 1}}}

        mock_manager = MagicMock()
        mock_preset = Preset(name="p", workflow="w", params={"p": 2}, mapping={"p": [ParamMapping("1", "inputs.a")]})
        mock_manager.get.return_value = mock_preset

        executor.execute_workflow_by_name(
            preset_name="test_preset",
            workflow_loader=mock_loader,
            preset_manager=mock_manager
        )

        mock_loader.load.assert_called_with("w")
        mock_manager.get.assert_called_with("test_preset")

        args, _ = mock_client.execute.call_args
        assert args[0]["1"]["inputs"]["a"] == 2
