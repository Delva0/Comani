"""
Preset model for workflow parameter configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import copy

import yaml


@dataclass
class ParamMapping:
    """Mapping from preset param to workflow node field."""
    node_id: str
    field_path: str  # e.g., "inputs.text" or "widgets_values.0"


@dataclass
class Preset:
    """Workflow preset configuration."""
    name: str
    base_workflow: str
    params: dict[str, Any] = field(default_factory=dict)
    mapping: dict[str, ParamMapping] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preset":
        """Load preset from dictionary."""
        mapping = {}
        for param_name, mapping_data in data.get("mapping", {}).items():
            if isinstance(mapping_data, ParamMapping):
                mapping[param_name] = mapping_data
            else:
                mapping[param_name] = ParamMapping(
                    node_id=str(mapping_data["node_id"]),
                    field_path=mapping_data["field_path"],
                )

        if "base_workflow" not in data:
            raise ValueError("base_workflow is required in preset")

        return cls(
            name=data.get("name", "anonymous"),
            base_workflow=data["base_workflow"],
            params=data.get("params", {}),
            mapping=mapping,
            dependencies=data.get("dependencies", []),
        )


class PresetManager:
    """Manager for loading and caching presets with inheritance support."""

    def __init__(self, preset_dir: Path):
        self.preset_dir = preset_dir
        self._cache: dict[str, Preset] = {}

    def list_presets(self) -> list[str]:
        """List all available preset names (relative paths with extension)."""
        presets = []
        if self.preset_dir.exists():
            for f in self.preset_dir.rglob("*"):
                if f.suffix in (".yml", ".yaml"):
                    # Use relative path as the name, normalized to forward slashes
                    rel_path = f.relative_to(self.preset_dir)
                    presets.append(str(rel_path).replace("\\", "/"))
        return sorted(presets)

    def get(self, name: str, reload: bool = False) -> Preset:
        """Get preset by name, resolving inheritance if necessary."""
        # Normalize name to use forward slashes if it's a path
        name = name.replace("\\", "/")
        if reload or name not in self._cache:
            # 1. Recursive resolution to get merged dict
            # Start with preset_dir as the initial context
            resolved_data = self._resolve_recursive(name, visited=set(), context_dir=self.preset_dir)

            # 2. Default Name Handling
            if "name" not in resolved_data:
                resolved_data["name"] = name

            # 3. Instantiate
            self._cache[name] = Preset.from_dict(resolved_data)
        return self._cache[name]

    def _resolve_recursive(self, name: str, visited: set[str], context_dir: Path | None = None) -> dict[str, Any]:
        """Recursively resolve inheritance bases."""
        if name in visited:
            raise RecursionError(f"Circular dependency detected: {visited} -> {name}")
        visited.add(name)

        # Load raw data for current level
        current, current_path = self._load_raw_yaml(name, context_dir)

        # Handle bases
        bases = current.pop("bases", [])
        if isinstance(bases, str):
            bases = [bases]

        # Merge bases
        merged_base = {}
        for base_name in bases:
            # Use current file's directory as context for bases
            parent_data = self._resolve_recursive(base_name, visited, context_dir=current_path.parent)
            merged_base = self._merge_dicts(merged_base, parent_data)

        # Current level overrides bases
        final = self._merge_dicts(merged_base, current)
        visited.remove(name)
        return final

    def _merge_dicts(self, base: dict, override: dict) -> dict:
        """Merge two preset dicts with inheritance logic."""
        result = copy.deepcopy(base)
        for k, v in override.items():
            if k in ("params", "mapping") and isinstance(v, dict):
                result.setdefault(k, {}).update(v)
            elif k == "dependencies" and isinstance(v, list):
                # Append and deduplicate list while maintaining order
                existing = result.get(k, [])
                result[k] = list(dict.fromkeys(existing + v))
            else:
                # Scalar overwrite
                result[k] = v
        return result

    def _load_raw_yaml(self, name: str, context_dir: Path | None = None) -> tuple[dict, Path]:
        """Load raw YAML content from disk."""
        # 1. Try absolute path
        p = Path(name)
        if p.is_absolute():
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}, p
            raise FileNotFoundError(f"Preset absolute path '{name}' not found")

        # 2. Try relative path from context_dir (priority 1)
        if context_dir:
            p = (context_dir / name).resolve()
            if p.exists():
                with open(p, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}, p

        # 3. Try relative path from preset_dir (priority 2)
        p = self.preset_dir / name
        if p.exists():
            with open(p, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}, p

        search_dirs = []
        if context_dir:
            search_dirs.append(str(context_dir))
        search_dirs.append(str(self.preset_dir))
        raise FileNotFoundError(f"Preset '{name}' not found (searched in: {', '.join(search_dirs)})")

    def reload_all(self) -> None:
        """Reload all presets from disk."""
        self._cache.clear()
        for name in self.list_presets():
            self.get(name)
