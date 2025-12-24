import json
from pathlib import Path
from unittest.mock import MagicMock
from comani.core.workflow import WorkflowLoader

class TestWorkflowLoader:
    """Tests for WorkflowLoader."""

    def test_list_workflows(self, tmp_path):
        """Test listing workflows from directory."""
        (tmp_path / "w1.json").write_text("{}")
        (tmp_path / "w2.json").write_text("{}")
        (tmp_path / "not_a_workflow.txt").write_text("ignore")

        loader = WorkflowLoader(tmp_path)
        workflows = loader.list_workflows()
        assert workflows == ["w1", "w2"]

    def test_load_workflow(self, tmp_path):
        """Test loading and caching workflows."""
        path = tmp_path / "test.json"
        data = {"nodes": []}
        path.write_text(json.dumps(data))

        loader = WorkflowLoader(tmp_path)
        wf = loader.load("test")
        assert wf == data
        assert "test" in loader._cache

        # Test cache hit
        wf2 = loader.load("test")
        assert wf2 == data
        # Note: load() returns deepcopy, so they shouldn't be the same object
        assert wf2 is not wf

    def test_convert_to_api_format_simple(self):
        """Test converting node-graph to API format (basic check)."""
        loader = WorkflowLoader(Path("/tmp"))

        # If it's already in API format, it should return as-is
        api_wf = {"1": {"inputs": {}, "class_type": "CLIPTextEncode"}}
        assert loader.convert_to_api_format(api_wf) == api_wf

        # Basic node graph structure
        graph_wf = {
            "nodes": [
                {
                    "id": 1,
                    "type": "CLIPTextEncode",
                    "widgets_values": ["hello"]
                }
            ]
        }

        # Mock object info to help with widget names
        mock_client = MagicMock()
        mock_client.get_object_info.return_value = {
            "CLIPTextEncode": {
                "input_order": {"required": ["text"]},
                "input": {"required": {"text": ["STRING", {"multiline": True}]}}
            }
        }
        loader.client = mock_client

        api_wf = loader.convert_to_api_format(graph_wf)
        assert "1" in api_wf
        assert api_wf["1"]["inputs"]["text"] == "hello"
        assert api_wf["1"]["class_type"] == "CLIPTextEncode"
