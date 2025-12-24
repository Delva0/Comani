"""
Preset model for workflow parameter configuration.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    def from_yaml(cls, path: Path) -> "Preset":
        """Load preset from YAML file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        mapping = {}
        for param_name, mapping_data in data.get("mapping", {}).items():
            mapping[param_name] = ParamMapping(
                node_id=str(mapping_data["node_id"]),
                field_path=mapping_data["field_path"],
            )

        return cls(
            name=data.get("name", path.stem),
            base_workflow=data["base_workflow"],
            params=data.get("params", {}),
            mapping=mapping,
            dependencies=data.get("dependencies", {}),
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Preset":
        """Load preset from dictionary (for API requests)."""
        mapping = {}
        for param_name, mapping_data in data.get("mapping", {}).items():
            mapping[param_name] = ParamMapping(
                node_id=str(mapping_data["node_id"]),
                field_path=mapping_data["field_path"],
            )

        return cls(
            name=data.get("name", "anonymous"),
            base_workflow=data["base_workflow"],
            params=data.get("params", {}),
            mapping=mapping,
            dependencies=data.get("dependencies", {}),
        )


class PresetManager:
    """Manager for loading and caching presets."""

    def __init__(self, preset_dir: Path):
        self.preset_dir = preset_dir
        self._cache: dict[str, Preset] = {}

    def list_presets(self) -> list[str]:
        """List all available preset names."""
        presets = []
        if self.preset_dir.exists():
            for f in self.preset_dir.iterdir():
                if f.suffix in (".yml", ".yaml"):
                    presets.append(f.stem)
        return sorted(presets)

    def get(self, name: str, reload: bool = False) -> Preset:
        """Get preset by name, load from file if not cached."""
        if name not in self._cache or reload:
            for suffix in (".yml", ".yaml"):
                path = self.preset_dir / f"{name}{suffix}"
                if path.exists():
                    self._cache[name] = Preset.from_yaml(path)
                    break
            else:
                raise FileNotFoundError(f"Preset not found: {name}")
        return self._cache[name]

    def reload_all(self) -> None:
        """Reload all presets from disk."""
        self._cache.clear()
        for name in self.list_presets():
            self.get(name)
