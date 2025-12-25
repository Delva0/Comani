"""
Workflow executor - load workflow, apply preset params, execute via client.
"""

import copy
import logging
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
        dependency_resolver: DependencyResolver | None = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.client = client
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

            mappings = preset.mapping[param_name]
            for mapping in mappings:
                node_id = mapping.node_id

                if node_id not in workflow:
                    continue

                node = workflow[node_id]
                try:
                    set_nested_value(node, mapping.field_path, value)
                except (KeyError, IndexError, TypeError) as e:
                    print(f"Warning: Failed to set {param_name} on node {node_id}: {e}")

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

    def execute_workflow(
        self,
        workflow: dict[str, Any] | None = None,
        preset: dict[str, Any] | Preset | None = None,
        progress_callback: Any | None = None,
    ) -> ComfyUIResult:
        """
        Execute workflow with optional preset.
        If workflow is provided, it overrides the workflow in the preset.
        """
        # 1. Resolve Preset
        preset_obj = None
        if preset is not None:
            if isinstance(preset, Preset):
                preset_obj = preset
            else:
                preset_data = copy.deepcopy(preset)
                # Ensure workflow key exists for Preset.from_dict if not present
                if "workflow" not in preset_data:
                    preset_data["workflow"] = "provided_workflow"
                preset_obj = Preset.from_dict(preset_data)

        # 2. Resolve Workflow
        final_workflow = None
        if workflow is not None:
            final_workflow = copy.deepcopy(workflow)
        elif preset_obj is not None:
            # We can't load workflow by name here because we don't have a loader
            # So preset_obj.workflow name is useless here unless final_workflow is provided
            raise ValueError("workflow dict must be provided in execute_workflow")
        else:
            raise ValueError("Either workflow or preset must be provided")

        # 4. Apply preset if provided
        if preset_obj:
            self._ensure_dependencies(preset_obj)
            final_workflow = self.apply_preset(final_workflow, preset_obj)

        return self.client.execute(final_workflow, progress_callback=progress_callback)

    def execute_workflow_by_name(
        self,
        workflow_name: str | None = None,
        preset_name: str | None = None,
        param_overrides: dict[str, Any] | None = None,
        workflow_loader: WorkflowLoader | None = None,
        preset_manager: PresetManager | None = None,
        progress_callback: Any | None = None,
    ) -> ComfyUIResult:
        """
        Execute workflow and optional preset by their names.
        If workflow_name is provided, it overrides the workflow in the preset.
        """
        if workflow_loader is None:
            raise ValueError("workflow_loader is required")

        preset_obj = None
        if preset_name:
            if preset_manager is None:
                raise ValueError("preset_manager is required when preset_name is provided")
            preset_obj = preset_manager.get(preset_name)
            if param_overrides:
                preset_obj = copy.deepcopy(preset_obj)
                preset_obj.params.update(param_overrides)

        final_workflow_name = workflow_name
        if final_workflow_name is None:
            if preset_obj is None:
                raise ValueError("Either workflow_name or preset_name must be provided")
            final_workflow_name = preset_obj.workflow

        workflow_dict = workflow_loader.load(final_workflow_name)
        if "nodes" in workflow_dict:
            workflow_dict = workflow_loader.convert_to_api_format(workflow_dict)

        return self.execute_workflow(
            workflow=workflow_dict,
            preset=preset_obj,
            progress_callback=progress_callback,
        )
