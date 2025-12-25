from unittest.mock import MagicMock, patch
from comani.core.engine import ComaniEngine
from comani.config import ComaniConfig

class TestComaniEngine:
    """Tests for ComaniEngine."""

    @patch("comani.core.engine.ComfyUIClient")
    @patch("comani.core.engine.PresetManager")
    @patch("comani.core.engine.WorkflowLoader")
    @patch("comani.core.engine.ModelPackRegistry")
    @patch("comani.core.engine.DependencyResolver")
    @patch("comani.core.engine.Executor")
    def test_engine_init(self, mock_exec, mock_dep, mock_reg, mock_load, mock_pres, mock_client):
        """Test engine initialization and components."""
        config = ComaniConfig(host="test-host")
        engine = ComaniEngine(config)

        assert engine.config == config
        mock_client.assert_called_once()
        mock_pres.assert_called_once()
        mock_load.assert_called_once()
        mock_reg.assert_called_once()
        mock_dep.assert_called_once()
        mock_exec.assert_called_once()

    @patch("comani.core.engine.ComfyUIClient")
    def test_health_check(self, mock_client_cls):
        """Test engine health check."""
        mock_client = mock_client_cls.return_value
        mock_client.health_check.return_value = True

        engine = ComaniEngine()
        status = engine.health_check()

        assert status["comfyui"] == "ok"
        mock_client.health_check.assert_called_once()

    def test_close(self):
        """Test engine cleanup."""
        engine = ComaniEngine()
        engine.close()
        # No error should occur

    def test_execute_workflow_by_name(self):
        """Test execute_workflow_by_name in Engine."""
        engine = ComaniEngine()
        engine.executor = MagicMock()
        
        engine.execute_workflow_by_name(
            workflow_name="test_wf",
            preset_name="test_preset",
            param_overrides={"p": 1}
        )
        
        engine.executor.execute_workflow_by_name.assert_called_once_with(
            workflow_name="test_wf",
            preset_name="test_preset",
            param_overrides={"p": 1},
            workflow_loader=engine.workflow_loader,
            preset_manager=engine.preset_manager,
            progress_callback=None
        )
