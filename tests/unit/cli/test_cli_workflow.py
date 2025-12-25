"""
Tests for the workflow CLI commands.
"""

from unittest.mock import patch
from argparse import Namespace
from comani.cli.cmd_workflow import cmd_workflow_list


class TestWorkflowListCommand:
    """Tests for the workflow list command."""

    def test_list_workflows(self, capsys):
        """Test listing all workflows."""
        mock_workflows = ["workflow1", "workflow2"]
        with patch("comani.cli.cmd_workflow.ComaniEngine") as mock_engine_class:
            mock_engine = mock_engine_class.return_value
            mock_engine.list_workflows.return_value = mock_workflows

            args = Namespace(workflow_action="list")
            result = cmd_workflow_list(args)

            assert result == 0
            captured = capsys.readouterr()
            assert "workflow1" in captured.out
            assert "workflow2" in captured.out
            mock_engine.list_workflows.assert_called_once()
