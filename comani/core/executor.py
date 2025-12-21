"""
Workflow executor - load workflow, apply preset params, execute via client.
"""

import json
import copy
from pathlib import Path
from typing import Any

from .preset import Preset, PresetManager
from .client import ComfyUIClient, ComfyUIResult


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


class WorkflowLoader:
    """Loader for workflow JSON files."""

    def __init__(self, workflow_dir: Path):
        self.workflow_dir = workflow_dir
        self._cache: dict[str, dict] = {}

    def list_workflows(self) -> list[str]:
        """List all available workflow names."""
        workflows = []
        if self.workflow_dir.exists():
            for f in self.workflow_dir.iterdir():
                if f.suffix == ".json":
                    workflows.append(f.stem)
        return sorted(workflows)

    def load(self, name: str, reload: bool = False) -> dict[str, Any]:
        """Load workflow by name."""
        if name not in self._cache or reload:
            path = self.workflow_dir / f"{name}.json"
            if not path.exists():
                path = self.workflow_dir / name
                if not path.exists():
                    raise FileNotFoundError(f"Workflow not found: {name}")

            with open(path, encoding="utf-8") as f:
                self._cache[name] = json.load(f)

        return copy.deepcopy(self._cache[name])

    def convert_to_api_format(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """
        Convert ComfyUI node-graph format to API format.
        API format uses node_id as key with inputs dict.
        """
        if "nodes" not in workflow:
            return workflow

        api_workflow = {}
        nodes = workflow["nodes"]

        for node in nodes:
            node_id = str(node["id"])
            node_type = node["type"]

            if node_type in ("Note", "Reroute"):
                continue

            inputs = {}
            widget_values = node.get("widgets_values", [])
            node_inputs = node.get("inputs", [])

            if widget_values:
                inputs["_widget_values"] = widget_values

            for inp in node_inputs:
                if inp.get("link") is not None:
                    link_id = inp["link"]
                    for link in workflow.get("links", []):
                        if link[0] == link_id:
                            source_node_id = str(link[1])
                            source_slot = link[2]
                            inputs[inp["name"]] = [source_node_id, source_slot]
                            break

            api_workflow[node_id] = {
                "class_type": node_type,
                "inputs": inputs,
            }

        return api_workflow


class Executor:
    """Execute workflows with preset parameters."""

    def __init__(
        self,
        client: ComfyUIClient,
        workflow_loader: WorkflowLoader,
        preset_manager: PresetManager,
    ):
        self.client = client
        self.workflow_loader = workflow_loader
        self.preset_manager = preset_manager

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

        for dep_type, dep_value in preset.dependencies.items():
            for node_id, node in workflow.items():
                if not isinstance(node, dict):
                    continue
                inputs = node.get("inputs", {})
                if dep_type == "checkpoint" and "ckpt_name" in inputs:
                    inputs["ckpt_name"] = dep_value
                elif dep_type == "lora" and "lora_name" in inputs:
                    inputs["lora_name"] = dep_value
                elif dep_type == "vae" and "vae_name" in inputs:
                    inputs["vae_name"] = dep_value

        return workflow

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
