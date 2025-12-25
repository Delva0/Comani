"""
Comani engine - main orchestrator for workflow execution.
"""

import logging
from typing import Any

from comani.config import get_config, ComaniConfig
from comani.core.client import ComfyUIClient, ComfyUIResult
from comani.core.preset import PresetManager
from comani.core.executor import WorkflowLoader, Executor
from comani.model.model_dependency import DependencyResolver
from comani.model.model_pack import ModelPackRegistry
from comani.utils.download import get_downloader


class ComaniEngine:
    """
    Main engine that orchestrates all components.
    Example: engine = ComaniEngine() to create with default config
    """

    def __init__(self, config: ComaniConfig | None = None):
        self.logger = logging.getLogger(__name__)
        self.config = config or get_config()
        self.client = ComfyUIClient(self.config.comfyui_url, auth=self.config.auth)
        self.preset_manager = PresetManager(self.config.preset_dir)
        self.workflow_loader = WorkflowLoader(self.config.workflow_dir)

        # Initialize registry and dependency resolver
        self.model_pack_registry = ModelPackRegistry(self.config.model_dir)
        self.dependency_resolver = DependencyResolver(
            self.config.model_dir,
            registry=self.model_pack_registry,
        )
        self.executor = Executor(
            self.client,
            self.dependency_resolver,
        )

    def download_models(self, targets: list[str], dry_run: bool = False) -> bool:
        """Download models specified by targets."""
        from comani.model.model_downloader import ModelDownloader
        dl = ModelDownloader(get_downloader(), self.config.comfyui_root)
        return dl.download_by_ids(targets, model_pack_registry=self.model_pack_registry, dry_run=dry_run)

    def close(self) -> None:
        """Cleanup resources."""
        pass

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def health_check(self) -> dict[str, Any]:
        """Check engine and ComfyUI status."""
        comfyui_ok = self.client.health_check()
        return {
            "comfyui": "ok" if comfyui_ok else "unreachable",
            "comfyui_url": self.config.comfyui_url,
        }

    def list_presets(self) -> list[str]:
        """List all available presets."""
        return self.preset_manager.list_presets()

    def list_workflows(self) -> list[str]:
        """List all available workflows."""
        return self.workflow_loader.list_workflows()

    def execute_workflow(
        self,
        workflow: dict[str, Any] | None = None,
        preset: dict[str, Any] | None = None,
        progress_callback: Any | None = None,
    ) -> ComfyUIResult:
        """
        Execute workflow with optional preset using raw dictionaries.
        """
        return self.executor.execute_workflow(workflow, preset, progress_callback=progress_callback)

    def execute_workflow_by_name(
        self,
        workflow_name: str | None = None,
        preset_name: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        progress_callback: Any | None = None,
    ) -> ComfyUIResult:
        """
        Execute workflow and optional preset by their names.
        """
        return self.executor.execute_workflow_by_name(
            workflow_name=workflow_name,
            preset_name=preset_name,
            param_overrides=param_overrides,
            workflow_loader=self.workflow_loader,
            preset_manager=self.preset_manager,
            progress_callback=progress_callback,
        )

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
