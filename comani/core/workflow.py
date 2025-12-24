import copy
import json
from pathlib import Path
from typing import Any

from comani.core.client import ComfyUIClient


class WorkflowLoader:
    """Loader for workflow JSON files."""

    def __init__(self, workflow_dir: Path, client: ComfyUIClient | None = None):
        self.workflow_dir = workflow_dir
        self._cache: dict[str, dict] = {}
        self._object_info_cache: dict[str, dict] | None = None
        self.client = client

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

    def _get_object_info(self) -> dict[str, Any]:
        """Get node type definitions from ComfyUI."""
        if self._object_info_cache is None and self.client:
            self._object_info_cache = self.client.get_object_info()
        return self._object_info_cache or {}

    def _get_widget_inputs_for_node(self, node_type: str) -> list[str]:
        """Get ordered list of widget input names for a node type."""
        object_info = self._get_object_info()
        if node_type not in object_info:
            return []

        node_info = object_info[node_type]
        input_order = node_info.get("input_order", {})
        node_input_def = node_info.get("input", {})

        widget_names = []
        for category in ["required", "optional"]:
            for input_name in input_order.get(category, []):
                input_def = node_input_def.get(category, {}).get(input_name)
                if input_def is None:
                    continue

                input_type = input_def[0] if isinstance(input_def, list) else input_def
                if isinstance(input_type, list):
                    widget_names.append(input_name)
                elif input_type in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"):
                    widget_names.append(input_name)

        return widget_names

    def convert_to_api_format(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """
        Convert ComfyUI node-graph format to API format.
        API format uses node_id as key with inputs dict.
        """
        if "nodes" not in workflow:
            return workflow

        api_workflow = {}
        nodes = workflow["nodes"]
        links_by_id = {link[0]: link for link in workflow.get("links", [])}

        for node in nodes:
            node_id = str(node["id"])
            node_type = node["type"]

            if node_type in ("Note", "Reroute", "PrimitiveNode"):
                continue

            inputs = {}
            widget_values = node.get("widgets_values", [])
            node_inputs = node.get("inputs", [])

            linked_inputs = set()
            for inp in node_inputs:
                link_id = inp.get("link")
                if link_id is not None:
                    link = links_by_id.get(link_id)
                    if link:
                        source_node_id = str(link[1])
                        source_slot = link[2]

                        src_node = next((n for n in nodes if str(n["id"]) == source_node_id), None)
                        if src_node and src_node["type"] == "PrimitiveNode":
                            prim_values = src_node.get("widgets_values", [])
                            if prim_values:
                                inputs[inp["name"]] = prim_values[0]
                        else:
                            inputs[inp["name"]] = [source_node_id, source_slot]
                        linked_inputs.add(inp["name"])

            all_widget_inputs = [
                inp for inp in node_inputs
                if inp.get("widget") is not None
            ]
            widget_names_from_node = [inp["name"] for inp in all_widget_inputs]

            object_info = self._get_object_info()
            all_widget_names = self._get_widget_inputs_for_node(node_type) if node_type in object_info else []

            combined_widget_order = list(widget_names_from_node)
            for name in all_widget_names:
                if name not in combined_widget_order:
                    combined_widget_order.append(name)

            if combined_widget_order and widget_values:
                widget_idx = 0
                for name in combined_widget_order:
                    is_linked = name in linked_inputs

                    while widget_idx < len(widget_values):
                        val = widget_values[widget_idx]
                        widget_idx += 1
                        if isinstance(val, str) and val in ("fixed", "increment", "decrement", "randomize"):
                            continue
                        if not is_linked:
                            inputs[name] = val
                        break
            elif widget_values:
                inputs["_widget_values"] = widget_values

            api_workflow[node_id] = {
                "class_type": node_type,
                "inputs": inputs,
            }

        return api_workflow
