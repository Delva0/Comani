"""
Comani engine - main orchestrator for workflow execution.
"""

from typing import Any

from comani.config import get_config, ComaniConfig
from comani.core.client import ComfyUIClient, ComfyUIResult
from comani.core.preset import PresetManager
from comani.core.executor import WorkflowLoader, Executor
from comani.model.model_dependency import DependencyResolver
from comani.model.model_pack import ModelPackRegistry
from comani.model.download import ModelDownloader
from comani.utils.download import get_downloader


class ComaniEngine:
    """
    Main engine that orchestrates all components.
    Example: engine = ComaniEngine() to create with default config
    """

    def __init__(self, config: ComaniConfig | None = None):
        self.config = config or get_config()
        self.client = ComfyUIClient(self.config.comfyui_url, auth=self.config.auth)
        self.preset_manager = PresetManager(self.config.preset_dir)
        self.workflow_loader = WorkflowLoader(self.config.workflow_dir)

        # Initialize registry and dependency resolver
        self._downloader = None
        self.model_pack_registry = ModelPackRegistry(self.config.model_dir)
        self.dependency_resolver = DependencyResolver(
            self.config.model_dir,
            registry=self.model_pack_registry,
        )
        self.executor = Executor(
            self.client,
            self.workflow_loader,
            self.preset_manager,
            self.dependency_resolver,
        )

    def _create_downloader(self) -> ModelDownloader:
        """Create a new ModelDownloader instance."""
        inner_downloader = get_downloader()
        # Model paths in YAML are relative to comfyui_root (e.g., "models/checkpoints/...")
        downloader = ModelDownloader(inner_downloader, self.config.comfyui_root)
        self.dependency_resolver.set_downloader(downloader)
        return downloader

    @property
    def downloader(self) -> ModelDownloader:
        """Get the singleton model downloader instance."""
        if self._downloader is None:
            self._downloader = self._create_downloader()
            # Active downloader (connect if needed)
            if hasattr(self._downloader, "__enter__"):
                self._downloader.__enter__()
        return self._downloader

    def download_models(self, targets: list[str], dry_run: bool = False) -> bool:
        """Download models specified by targets."""
        return self.downloader.download_by_ids(targets, model_pack_registry=self.model_pack_registry, dry_run=dry_run)

    def close(self) -> None:
        """Cleanup resources including downloader."""
        if self._downloader:
            if hasattr(self._downloader, "__exit__"):
                self._downloader.__exit__(None, None, None)
            self._downloader = None

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
