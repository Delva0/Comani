"""
Comani engine - main orchestrator for workflow execution.
"""

from typing import Any

from ..config import init_config, get_config, ComaniConfig
from .client import ComfyUIClient, ComfyUIResult
from .preset import PresetManager
from .executor import WorkflowLoader, Executor


class ComaniEngine:
    """
    Main engine that orchestrates all components.
    Example: engine = ComaniEngine() to create with default config
    """

    def __init__(self, config: ComaniConfig | None = None):
        self.config = config or init_config()
        self.client = ComfyUIClient(self.config.comfyui_url)
        self.preset_manager = PresetManager(self.config.preset_dir)
        self.workflow_loader = WorkflowLoader(self.config.workflow_dir)
        self.executor = Executor(
            self.client,
            self.workflow_loader,
            self.preset_manager,
        )

    def health_check(self) -> dict[str, Any]:
        """Check engine and ComfyUI status."""
        comfyui_ok = self.client.health_check()
        return {
            "engine": "ok",
            "comfyui": "ok" if comfyui_ok else "unreachable",
            "comfyui_url": self.config.comfyui_url,
        }

    def list_presets(self) -> list[str]:
        """List all available presets."""
        return self.preset_manager.list_presets()

    def list_workflows(self) -> list[str]:
        """List all available workflows."""
        return self.workflow_loader.list_workflows()

    def execute_preset(
        self,
        preset_name: str,
        param_overrides: dict[str, Any] | None = None,
    ) -> ComfyUIResult:
        """
        Execute a preset with optional parameter overrides.
        Example: result = engine.execute_preset("cyberpunk_city", {"seed": 42})
        """
        return self.executor.execute_preset(preset_name, param_overrides)

    def execute_workflow(
        self,
        workflow_name: str,
        preset_data: dict[str, Any] | None = None,
    ) -> ComfyUIResult:
        """Execute a workflow with optional inline preset data."""
        return self.executor.execute_workflow(workflow_name, preset_data)

    def execute_raw(self, workflow: dict[str, Any]) -> ComfyUIResult:
        """Execute raw workflow directly."""
        return self.executor.execute_raw(workflow)

    def interrupt(self) -> bool:
        """Interrupt current execution."""
        return self.client.interrupt()

    def clear_queue(self) -> bool:
        """Clear the execution queue."""
        return self.client.clear_queue()

    def get_queue(self) -> dict[str, Any]:
        """Get current queue status."""
        return self.client.get_queue()

    def get_history(self, prompt_id: str | None = None) -> dict[str, Any]:
        """Get execution history."""
        return self.client.get_history(prompt_id)
