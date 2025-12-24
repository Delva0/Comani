"""
Model Pack configuration system.

Python-like naming convention:
  - Package: models/sdxl/ directory
  - Module: models/sdxl/sdxl.yml file
  - Model: model definition in a module
  - Group: group definition in a module

Reference format (Python-like dot notation):
  - "model_id" - local reference within same module
  - "module.model_id" - reference model in another module (same package)
  - "package.module.model_id" - fully qualified reference
  - "package.module" - all models in a module
  - "package.*" - all models in all modules of a package
  - "package.module.group_id" - reference a group
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ModelDef:
    """Single model definition."""
    id: str
    url: str
    path: str  # ComfyUI relative path like "models/vae/xxx.safetensors"
    description: str = ""
    source_module: str = ""  # fully qualified module name (e.g., "sdxl.lora_artist")


@dataclass
class GroupDef:
    """Group definition that combines multiple models."""
    id: str
    description: str
    includes: list[str]  # list of model/group references (supports wildcards)
    source_module: str = ""


@dataclass
class ResolvedGroup:
    """A fully resolved group with all model references expanded."""
    id: str
    description: str
    models: list[ModelDef] = field(default_factory=list)


class ModelPackError(Exception):
    """Raised when model pack parsing or resolution fails."""
    pass


class ModelPackRegistry:
    """
    Registry that loads and indexes all model packs from a directory.

    Uses Python-like naming:
      - Package: directory under models_dir (e.g., "sdxl")
      - Module: YAML file (e.g., "sdxl.lora_artist" for sdxl/lora_artist.yml)
      - Model/Group: definitions within a module
    """

    def __init__(self, models_dir: Path | str):
        self.models_dir = Path(models_dir)
        self._models: dict[str, ModelDef] = {}  # {qualified_id: ModelDef}
        self._groups: dict[str, GroupDef] = {}  # {qualified_id: GroupDef}
        self._module_models: dict[str, list[str]] = {}  # {module_name: [model_ids]}
        self._packages: dict[str, list[str]] = {}  # {package_name: [package_name/module_name...]}
        self._loaded = False

    def _track_module_package(self, module_name: str) -> None:  # Right logic. Don't modify.
        """Track a module in its package hierarchy. Collect all packages that include the module."""
        # Track package (package always ends with ".", "." is root)
        parent_package = module_name.rsplit(".", 1)[-2] + "."
        child_item = module_name
        while parent_package not in self._packages:
            self._packages[parent_package] = []
            self._packages[parent_package].append(child_item)
            if parent_package == ".":
                break
            child_item = parent_package
            parent_package = parent_package[:-1].rsplit(".", 1)[-2] + "."
        else:
            self._packages[parent_package].append(child_item)
        # print(self._packages)
        # print(self._module_models.keys())

    def load_from_dict(self, data: dict, module_name: str) -> None:
        """
        Load model pack data from a dictionary.

        Args:
            data: Model pack data
            module_name: Name of the module (e.g., ".sdxl")
        """
        # Ensure module name starts with "."
        if not module_name.startswith("."):
            module_name = "." + module_name

        self._module_models[module_name] = []

        # Track package
        self._track_module_package(module_name)

        # Parse models
        models_data = data.get("models", {})
        if isinstance(models_data, dict):
            for model_id, entry in models_data.items():
                qualified_id = f"{module_name}.{model_id}"
                model_def = self._parse_model_entry(entry, model_id, module_name)
                self._models[qualified_id] = model_def
                self._module_models[module_name].append(model_id)

        # Parse groups
        groups_data = data.get("groups", {})
        if isinstance(groups_data, dict):
            for group_id, entry in groups_data.items():
                qualified_id = f"{module_name}.{group_id}"
                group_def = GroupDef(
                    id=group_id,
                    description=entry.get("description", ""),
                    includes=entry.get("includes", []),
                    source_module=module_name,
                )
                self._groups[qualified_id] = group_def

    def _path_to_module(self, yml_path: Path) -> str:
        """Convert a YAML file path to module name (Python-like)."""
        rel_path = yml_path.relative_to(self.models_dir)
        # Remove .yml/.yaml suffix and convert / to .
        stem = rel_path.with_suffix("")
        return "." + str(stem).replace("/", ".").replace("\\", ".")

    def _parse_model_entry(self, entry: dict | list, model_id: str, module_name: str) -> ModelDef:
        """Parse a single model entry from YAML."""
        # Handle list format (legacy compatibility or explicit list of properties)
        if isinstance(entry, list):
            # Convert list of dicts to single dict
            merged = {}
            for item in entry:
                if isinstance(item, dict):
                    merged.update(item)
            entry = merged

        url = entry.get("url", "")
        path = entry.get("path", "")
        description = entry.get("description", "")

        # Auto-generate path from url if not specified
        if not path and url:
            filename = url.split("/")[-1]
            path = self._infer_path_from_url(url, filename)

        return ModelDef(
            id=model_id,
            url=url,
            path=path,
            description=description,
            source_module=module_name,
        )

    def _infer_path_from_url(self, url: str, filename: str) -> str:
        """Infer ComfyUI path from URL patterns."""
        url_lower = url.lower()

        # Detect model type from URL path
        if "/vae/" in url_lower or "_vae" in url_lower.replace("-", "_"):
            return f"models/vae/{filename}"
        if "/text_encoder" in url_lower or "text_enc" in url_lower:
            return f"models/text_encoders/{filename}"
        if "/diffusion_model" in url_lower:
            return f"models/diffusion_models/{filename}"
        if "/lora" in url_lower:
            return f"models/loras/{filename}"
        if "/upscale" in url_lower or "esrgan" in url_lower:
            return f"models/upscale_models/{filename}"
        if "/checkpoint" in url_lower:
            return f"models/checkpoints/{filename}"
        if "onnx" in url_lower or "/det/" in url_lower:
            return f"models/onnx/{filename}"
        if "/controlnet" in url_lower:
            return f"models/controlnet/{filename}"
        if "/model_patches" in url_lower:
            return f"models/model_patches/{filename}"

        # Default: use checkpoints for unknown
        return f"models/checkpoints/{filename}"

    def _load_pack_file(self, yml_path: Path) -> None:
        """Load a single model pack YAML file."""
        with open(yml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            return

        module_name = self._path_to_module(yml_path)
        self._module_models[module_name] = []

        # Track package
        self._track_module_package(module_name)

        # Parse models section
        models_data = data.get("models", {})
        if isinstance(models_data, dict):
            for model_id, entry in models_data.items():
                qualified_id = f"{module_name}.{model_id}"
                model_def = self._parse_model_entry(entry, model_id, module_name)
                self._models[qualified_id] = model_def
                self._module_models[module_name].append(model_id)
        elif isinstance(models_data, list):
            # List format: [{id: ..., url: ...}, ...]
            for entry in models_data:
                if isinstance(entry, dict) and "id" in entry:
                    model_id = entry["id"]
                    qualified_id = f"{module_name}.{model_id}"
                    model_def = self._parse_model_entry(entry, model_id, module_name)
                    self._models[qualified_id] = model_def
                    self._module_models[module_name].append(model_id)

        # Parse groups section
        groups_data = data.get("groups", {})
        if isinstance(groups_data, dict):
            for group_id, entry in groups_data.items():
                qualified_id = f"{module_name}.{group_id}"
                if qualified_id in self._models:
                    raise ModelPackError(
                        f"Duplicate ID '{group_id}' in {module_name}: "
                        "model and group cannot have the same ID"
                    )
                group_def = GroupDef(
                    id=group_id,
                    description=entry.get("description", ""),
                    includes=entry.get("includes", []),
                    source_module=module_name,
                )
                self._groups[qualified_id] = group_def

    def _load_all(self) -> None:
        """Load all model pack files from the directory (including subdirectories)."""
        if self._loaded:
            return

        if not self.models_dir.exists():
            self._loaded = True
            return

        def scan_dir(dir_path: Path) -> None:
            for item in dir_path.iterdir():
                if item.name.startswith(("_", ".")):
                    continue
                if item.is_dir():
                    scan_dir(item)
                elif item.suffix.lower() in (".yml", ".yaml"):
                    self._load_pack_file(item)

        scan_dir(self.models_dir)
        self._validate_unique_ids()
        self._loaded = True

    def _validate_unique_ids(self) -> None:
        """Validate that all model and group IDs are unique across files."""
        # Collect all simple IDs (without file prefix)
        all_ids: dict[str, list[str]] = {}  # {simple_id: [qualified_ids]}

        for qid in list(self._models.keys()) + list(self._groups.keys()):
            simple_id = qid.split(".")[-1]
            if simple_id not in all_ids:
                all_ids[simple_id] = []
            all_ids[simple_id].append(qid)

        # Duplicates are allowed - we use qualified references

    def _ensure_loaded(self) -> None:
        """Ensure registry is loaded."""
        if not self._loaded:
            self._load_all()

    def list_package_inners(self, package: str) -> list[str]:
        """List all modules and packages under specified package."""
        self._ensure_loaded()
        return self._packages.get(package, [])

    def list_modules(self) -> list[str]:
        """List all loaded module names (Python-like)."""
        self._ensure_loaded()
        return list(self._module_models.keys())

    def list_packages(self) -> list[str]:
        """List all packages (directories with modules)."""
        self._ensure_loaded()
        return list(self._packages.keys())

    def list_models(self, module_name: str | None = None) -> list[ModelDef]:
        """List all models, optionally filtered by module."""
        self._ensure_loaded()
        if module_name:
            model_ids = self._module_models.get(module_name, [])
            return [self._models[f"{module_name}.{mid}"] for mid in model_ids]
        return list(self._models.values())

    def list_groups(self, module_name: str | None = None) -> list[GroupDef]:
        """List all groups, optionally filtered by module."""
        self._ensure_loaded()
        if module_name:
            return [g for g in self._groups.values() if g.source_module == module_name]
        return list(self._groups.values())

    def get_model(self, ref: str, context_module: str | None = None) -> ModelDef | None:
        """
        Get a model by reference.
        Reference formats:
          - "model_id" - local reference (requires context_module)
          - "module.model_id" - qualified reference
          - "package.module.model_id" - fully qualified reference
        """
        self._ensure_loaded()

        # If it's a fully qualified reference
        if ref in self._models:
            return self._models[ref]

        # Try with context module
        if context_module and "." not in ref:
            qualified = f"{context_module}.{ref}"
            if qualified in self._models:
                return self._models[qualified]

        # Try to find unique match by simple ID
        simple_id = ref.split(".")[-1]
        matches = [m for qid, m in self._models.items() if qid.endswith(f".{simple_id}")]
        if len(matches) == 1:
            return matches[0]

        return None

    def get_group(self, ref: str, context_module: str | None = None) -> GroupDef | None:
        """Get a group by reference."""
        self._ensure_loaded()

        if ref in self._groups:
            return self._groups[ref]

        if context_module and "." not in ref:
            qualified = f"{context_module}.{ref}"
            if qualified in self._groups:
                return self._groups[qualified]

        simple_id = ref.split(".")[-1]
        matches = [g for qid, g in self._groups.items() if qid.endswith(f".{simple_id}")]
        if len(matches) == 1:
            return matches[0]

        return None

    def _match_wildcard(self, pattern: str) -> list[str]:
        """
        Match wildcard patterns against module/model names.

        Supports:
          - "package.*" - all modules in a package
          - "package.module.*" - all models in a module
          - "package.prefix_*" - modules matching prefix (e.g., sdxl.lora_*)
          - "*.model_id" - model_id in any module
          - "*" - everything
        """
        self._ensure_loaded()

        matches: list[str] = []

        if "*" not in pattern:
            return [pattern]

        # Check if it's a package.* pattern (all modules in a package)
        if pattern.endswith(".*"):
            prefix = pattern[:-2]  # Remove .*

            # First, check if prefix is a package (e.g., "sdxl.*")
            if prefix in self._packages:
                # Return all modules in this package
                for module_name in self._module_models:
                    if module_name.startswith(f"{prefix}."):
                        matches.append(module_name)
                return matches

            # Check if prefix is a module (return all models in it, e.g., "wan.*")
            if prefix in self._module_models:
                return [f"{prefix}.{mid}" for mid in self._module_models[prefix]]

        # Check for module-level wildcards like "sdxl.lora_*"
        # This matches modules within a package that start with a prefix
        if ".*" not in pattern and "*" in pattern:
            parts = pattern.rsplit(".", 1)
            if len(parts) == 2:
                package, module_pattern = parts
                if package in self._packages and "*" in module_pattern:
                    # Convert module pattern to regex (e.g., "lora_*" -> "lora_.*")
                    module_regex = module_pattern.replace("*", ".*")
                    compiled = re.compile(f"^{module_regex}$")
                    for module_name in self._module_models:
                        if module_name.startswith(f"{package}."):
                            # Get the module part after package
                            module_part = module_name[len(package) + 1:]
                            # Handle nested modules (e.g., sdxl.lora_artist vs sdxl.sdxl)
                            if "." not in module_part and compiled.match(module_part):
                                matches.append(module_name)
                    if matches:
                        return matches

        # General wildcard matching using fnmatch/regex
        # Convert pattern: . -> \. and * -> [^.]*
        regex_pattern = pattern.replace(".", r"\.").replace("*", r"[^.]*")
        compiled = re.compile(f"^{regex_pattern}$")

        # Match against all qualified IDs (models, groups, and modules)
        all_ids = list(self._models.keys()) + list(self._groups.keys()) + list(self._module_models.keys())
        for qid in all_ids:
            if compiled.match(qid):
                matches.append(qid)

        return matches

    def resolve_reference(
        self,
        ref: str,
        context_module: str | None = None,
        visited: set[str] | None = None,
    ) -> list[ModelDef]:
        """
        Resolve a reference to a list of models.
        Handles:
          - "model_id" - single model (with context)
          - "module.model_id" - qualified model reference
          - "module" - all models in a module
          - "package.*" - all models in all modules of a package
          - "module.group_id" - a group
          - Wildcard patterns with *
        """
        self._ensure_loaded()

        if visited is None:
            visited = set()

        # Prevent infinite loops
        ref_key = f"{context_module or ''}:{ref}"
        if ref_key in visited:
            return []
        visited.add(ref_key)

        # Handle wildcard patterns
        if "*" in ref:
            matches = self._match_wildcard(ref)
            all_models: list[ModelDef] = []
            seen_ids: set[str] = set()
            for match in matches:
                for model in self.resolve_reference(match, context_module, visited):
                    qid = f"{model.source_module}.{model.id}"
                    if qid not in seen_ids:
                        seen_ids.add(qid)
                        all_models.append(model)
            return all_models

        # Check if it's a module reference (return all models in module)
        if ref in self._module_models:
            return self.list_models(ref)

        # Try as model reference
        model = self.get_model(ref, context_module)
        if model:
            return [model]

        # Try as group reference
        group = self.get_group(ref, context_module)
        if group:
            return self.resolve_group(group, visited)

        # Try resolving with context if provided
        if context_module and "." not in ref:
            # Maybe it's a relative reference to another module in same package
            parts = context_module.split(".")
            if len(parts) >= 1:
                # Try package.ref as module
                package = parts[0]
                possible_module = f"{package}.{ref}"
                if possible_module in self._module_models:
                    return self.list_models(possible_module)

        return []

    def resolve_group(
        self,
        group: GroupDef,
        visited: set[str] | None = None,
    ) -> list[ModelDef]:
        """Resolve a group to its constituent models."""
        if visited is None:
            visited = set()

        models: list[ModelDef] = []
        seen_ids: set[str] = set()

        for include_ref in group.includes:
            resolved = self.resolve_reference(include_ref, group.source_module, visited)
            for model in resolved:
                qualified_id = f"{model.source_module}.{model.id}"
                if qualified_id not in seen_ids:
                    seen_ids.add(qualified_id)
                    models.append(model)

        return models

    def resolve_to_group(self, ref: str) -> ResolvedGroup:
        """
        Resolve any reference to a ResolvedGroup.
        This is the main API for downloading.
        """
        self._ensure_loaded()

        models = self.resolve_reference(ref)

        # Determine description
        group = self.get_group(ref)
        if group:
            description = group.description
            group_id = f"{group.source_module}.{group.id}"
        else:
            model = self.get_model(ref)
            if model:
                description = model.description + f"url: {model.url}\n   path: {model.path}"
                group_id = f"{model.source_module}.{model.id}"
            elif ref in self._module_models:
                description = f"All models from module: {ref}"
                group_id = ref
            elif "*" in ref:
                description = f"Wildcard pattern: {ref}"
                group_id = ref
            else:
                description = f"Resolved reference: {ref}"
                group_id = ref

        return ResolvedGroup(
            id=group_id,
            description=description,
            models=models,
        )

    def resolve_multiple(self, refs: list[str]) -> tuple[ResolvedGroup, list[tuple[str, str, int]]]:
        """
        Resolve multiple references and combine into a single group.

        Returns:
            - Combined ResolvedGroup
            - List of (ref, ref_type, model_count) for each input reference
        """
        self._ensure_loaded()

        all_models: list[ModelDef] = []
        seen_ids: set[str] = set()
        ref_info: list[tuple[str, str, int]] = []

        for ref in refs:
            resolved = self.resolve_to_group(ref)
            ref_type = self._identify_ref_type(ref)
            count = len(resolved.models)
            ref_info.append((ref, ref_type, count))

            for model in resolved.models:
                qid = f"{model.source_module}.{model.id}"
                if qid not in seen_ids:
                    seen_ids.add(qid)
                    all_models.append(model)

        combined_id = " + ".join(refs) if len(refs) > 1 else refs[0] if refs else "empty"
        combined_description = f"Combined group: {', '.join(refs)}" if len(refs) > 1 else (
            ref_info[0][1] if ref_info else "No targets"
        )

        return ResolvedGroup(
            id=combined_id,
            description=combined_description,
            models=all_models,
        ), ref_info

    def _identify_ref_type(self, ref: str) -> str:
        """Identify what type of reference this is."""
        self._ensure_loaded()

        if "*" in ref:
            return "wildcard pattern"

        if ref in self._module_models:
            return "module"

        if self.get_group(ref):
            return "group"

        if self.get_model(ref):
            return "model"

        # Check if it looks like a package
        if ref in self._packages:
            return "package"

        return "unknown"

    # Legacy compatibility aliases
    def list_packainner(self) -> list[str]:
        """Alias for list_modules() for backwards compatibility."""
        return self.list_modules()
