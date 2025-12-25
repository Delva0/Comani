"""
Dependency resolver for preset model dependencies.

Resolves dependencies using ModelPackRegistry with Python-like naming:
  - "sdxl.sdxl.anikawaxl_v2" - fully qualified model reference
  - "sdxl.lora_*" - wildcard pattern
  - ["ref1", "ref2"] - multiple references
"""

from dataclasses import dataclass
from pathlib import Path

from comani.model.model_downloader import ModelDownloader
from comani.model.model_pack import ModelPackRegistry, ModelDef
from comani.utils.download import get_downloader


@dataclass
class ResolvedDependency:
    """A resolved dependency with model path info."""
    model_type: str
    name: str
    path: Path
    needs_download: bool = False
    model_def: ModelDef | None = None


class DependencyError(Exception):
    """Raised when dependency cannot be resolved."""
    pass


class DependencyResolver:
    """
    Resolves and downloads preset dependencies using ModelPackRegistry.
    Example: resolver = DependencyResolver(model_config_dir)
    """

    def __init__(
        self,
        model_config_dir: Path | str | None,
        registry: ModelPackRegistry | None = None,
        downloader: ModelDownloader | None = None,
    ):
        if not model_config_dir and not registry:
            raise ValueError("Either model_config_dir or registry must be provided")

        # Use injected registry or create new one
        if model_config_dir:
            self.model_config_dir = Path(model_config_dir).resolve()
        self.registry = registry or ModelPackRegistry(self.model_config_dir)

        self._downloader: ModelDownloader | None = downloader

    def set_downloader(self, downloader: ModelDownloader) -> None:
        """Set the ModelDownloader instance."""
        self._downloader = downloader

    def _get_downloader(self) -> ModelDownloader:
        """Get or create ModelDownloader instance."""
        if self._downloader is None:
            from comani.config import get_config
            config = get_config()
            self._downloader = ModelDownloader(get_downloader(), config.comfyui_root)
        return self._downloader

    def _resolve_single_ref(
        self,
        ref: str,
    ) -> list[ResolvedDependency]:
        """Resolve a single dependency reference to list of dependencies."""
        resolved_group = self.registry.resolve_to_group(ref)

        if not resolved_group.models:
            raise DependencyError(f"No models found for reference: {ref}")

        dependencies = []
        for model in resolved_group.models:
            path_parts = model.path.split("/")
            model_type = path_parts[1] if len(path_parts) > 1 else "checkpoints"
            model_name = path_parts[-1] if path_parts else model.id

            dependencies.append(ResolvedDependency(
                model_type=model_type,
                name=model_name,
                path=Path(model.path),
                needs_download=True,
                model_def=model,
            ))

        return dependencies

    def resolve(
        self,
        dependencies: list[str],
    ) -> list[ResolvedDependency]:
        """
        Resolve all dependencies from preset.
        Example: deps = resolver.resolve(["sdxl.sdxl.anikawaxl_v2"])
        """
        results = []

        for ref in dependencies:
            results.extend(self._resolve_single_ref(ref))

        return results

    def ensure_dependencies(
        self,
        dependencies: list[str],
        dry_run: bool = False,
    ) -> list[ResolvedDependency]:
        """
        Resolve and download all missing dependencies.
        Example: deps = resolver.ensure_dependencies(preset.dependencies)
        """
        resolved = self.resolve(dependencies)

        if not resolved:
            return resolved

        if dry_run:
            print(f"[DRY-RUN] Would download {len(resolved)} model(s)")
            for dep in resolved:
                print(f"  - {dep.name} -> {dep.path}")
            return resolved

        # Pre-check: if all files already exist, skip downloader initialization
        from comani.utils.connection.node import get_node
        from comani.config import get_config
        node = get_node()
        comfyui_root = get_config().comfyui_root

        missing_models = []
        for dep in resolved:
            if not dep.model_def:
                continue
            full_path = comfyui_root / dep.model_def.path
            if not node.exists(str(full_path)):
                missing_models.append(dep.model_def.id)

        if not missing_models:
            # All models exist, no need to initialize downloader
            return resolved

        downloader = self._get_downloader()
        downloader.download_by_ids(
            missing_models,
            model_pack_registry=self.registry
        )

        return resolved

    def validate_only(
        self,
        dependencies: list[str],
    ) -> tuple[list[ResolvedDependency], list[str]]:
        """
        Validate dependencies without downloading.
        Returns (resolved_deps, error_messages)
        """
        resolved = []
        errors = []

        for ref in dependencies:
            try:
                resolved.extend(self._resolve_single_ref(ref))
            except DependencyError as e:
                errors.append(str(e))

        return resolved, errors
