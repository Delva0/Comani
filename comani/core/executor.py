"""
Workflow executor - load workflow, apply preset params, execute via client.
"""

import copy
from typing import Any

from comani.core.client import ComfyUIClient, ComfyUIResult
from comani.core.preset import Preset, PresetManager
from comani.core.workflow import WorkflowLoader
from comani.model.model_dependency import DependencyError, DependencyResolver


def set_nested_value(obj: dict, path: str, value: Any) -> None:
    """
    Set value at nested path in dictionary.
    Example: set_nested_value(d, "inputs.text", "hello") sets d["inputs"]["text"] = "hello"
    """
    keys = path.split(".")
    for key in keys[:-1]:
        if key.isdigit():
            key = int(key)
        obj = obj[key]

    final_key = keys[-1]
    if final_key.isdigit():
        obj[int(final_key)] = value
    else:
        obj[final_key] = value


def get_nested_value(obj: dict, path: str) -> Any:
    """Get value at nested path in dictionary."""
    keys = path.split(".")
    for key in keys:
        if key.isdigit():
            key = int(key)
        obj = obj[key]
    return obj


class Executor:
    """Execute workflows with preset parameters."""

    def __init__(
        self,
        client: ComfyUIClient,
        workflow_loader: WorkflowLoader,
        preset_manager: PresetManager,
        dependency_resolver: DependencyResolver | None = None,
    ):
        self.client = client
        self.workflow_loader = workflow_loader
        self.workflow_loader.client = client
        self.preset_manager = preset_manager
        self.dependency_resolver = dependency_resolver

    def apply_preset(self, workflow: dict[str, Any], preset: Preset) -> dict[str, Any]:
        """
        Apply preset parameters to workflow.
        Example: executor.apply_preset(workflow, preset) to substitute all params
        """
        workflow = copy.deepcopy(workflow)

        for param_name, value in preset.params.items():
            if param_name not in preset.mapping:
                continue

            mapping = preset.mapping[param_name]
            node_id = mapping.node_id

            if node_id not in workflow:
                continue

            node = workflow[node_id]
            try:
                set_nested_value(node, mapping.field_path, value)
            except (KeyError, IndexError, TypeError) as e:
                print(f"Warning: Failed to set {param_name}: {e}")

        return workflow

    def _ensure_dependencies(self, preset: Preset) -> None:
        """Ensure all preset dependencies are available, download if needed."""
        if not preset.dependencies:
            return

        if not self.dependency_resolver:
            print("Warning: No dependency resolver configured, skipping dependency check")
            return

        try:
            self.dependency_resolver.ensure_dependencies(preset.dependencies)
        except DependencyError as e:
            raise RuntimeError(f"Dependency error for preset '{preset.name}': {e}")

    def execute_preset(
        self,
        preset_name: str,
        param_overrides: dict[str, Any] | None = None,
    ) -> ComfyUIResult:
        """
        Load preset, apply to workflow, and execute.
        Example: result = executor.execute_preset("cyberpunk_city", {"seed": 42})
        """
        preset = self.preset_manager.get(preset_name)

        if param_overrides:
            preset.params.update(param_overrides)

        # Ensure dependencies are available
        self._ensure_dependencies(preset)

        workflow = self.workflow_loader.load(preset.base_workflow)

        if "nodes" in workflow:
            workflow = self.workflow_loader.convert_to_api_format(workflow)

        workflow = self.apply_preset(workflow, preset)

        return self.client.execute(workflow)

    def execute_workflow(
        self,
        workflow_name: str,
        preset_data: dict[str, Any] | None = None,
    ) -> ComfyUIResult:
        """
        Execute workflow directly with optional inline preset data.
        Example: result = executor.execute_workflow("flux_dev", {"params": {...}, "mapping": {...}})
        """
        workflow = self.workflow_loader.load(workflow_name)

        if "nodes" in workflow:
            workflow = self.workflow_loader.convert_to_api_format(workflow)

        if preset_data:
            preset_data["base_workflow"] = workflow_name
            preset = Preset.from_dict(preset_data)
            workflow = self.apply_preset(workflow, preset)

        return self.client.execute(workflow)

    def execute_raw(self, workflow: dict[str, Any]) -> ComfyUIResult:
        """Execute raw workflow directly."""
        return self.client.execute(workflow)
