"""
Model commands for Comani.
"""

import argparse
import sys
import os
from comani.core.engine import ComaniEngine
from comani.model.model_pack import ModelPackRegistry, ResolvedGroup
from comani.config import get_config

MODELS_ROOT = get_config().model_dir


def _get_registry() -> ModelPackRegistry:
    """Get the model pack registry."""
    return ModelPackRegistry(MODELS_ROOT)


def _print_model_tree(registry: ModelPackRegistry) -> None:
    """Print all available models and groups in tree format."""
    print("\n📦 Available Model Packs:")
    print("=" * 60)

    for module_name in sorted(registry.list_modules()):
        # Determine display format based on module depth
        parts = module_name.split(".")
        if len(parts) == 1:
            print(f"\n📁 {module_name}")
        else:
            indent = "  " * (len(parts) - 1)
            print(f"\n{indent}📁 {module_name}")

        # List models
        models = registry.list_models(module_name)
        if models:
            indent = "  " * len(parts)
            print(f"{indent}Models ({len(models)}):")
            for model in models[:5]:  # Show first 5
                print(f"{indent}  - {model.id}")
            if len(models) > 5:
                print(f"{indent}  ... and {len(models) - 5} more")

        # List groups
        groups = registry.list_groups(module_name)
        if groups:
            indent = "  " * len(parts)
            print(f"{indent}Groups ({len(groups)}):")
            for group in groups:
                print(f"{indent}  📦 {group.id}: {group.description}")


def _print_resolved_group(group: ResolvedGroup) -> None:
    """Print details of a resolved group."""
    print(f"\n📦 {group.id}")
    print(f"   {group.description}")
    print(f"\n   Models ({len(group.models)}):")
    for model in group.models:
        print(f"   - {model.source_module}.{model.id}")


def _print_ref_info(ref: str, ref_type: str, count: int) -> None:
    """Print information about a single reference."""
    type_emoji = {
        "model": "📄",
        "group": "📦",
        "module": "📁",
        "package": "📂",
        "wildcard pattern": "✨",
        "unknown": "❓",
    }
    emoji = type_emoji.get(ref_type, "❓")
    print(f"   {emoji} {ref} is {ref_type} ({count} models)")


def _interactive_select(registry: ModelPackRegistry) -> str | None:
    """Interactive menu to select a model or group."""
    try:
        import questionary
        from questionary import Style
    except ImportError:
        print("Error: questionary not installed. Use --list or specify target directly.")
        return None

    style = Style([
        ("qmark", "fg:cyan bold"),
        ("question", "fg:green bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
    ])

    def _get_package_inners(package: str = "") -> list[str]:
        """Get all inner packages and modules."""
        inners = registry.list_package_inners(package)
        packages = [m[:-1].rsplit(".", 1)[-1]+"." for m in inners if m.endswith(".")]
        modules = [m.rsplit(".", 1)[-1] for m in inners if not m.endswith(".")]
        return [".."] + packages + modules

    def _clear_line():
        sys.stdout.write("\033[F\033[K")
        sys.stdout.flush()

    current_package = "."
    model_dir_name = os.path.basename(get_config().model_dir)

    while True:
        inners = _get_package_inners(current_package)

        inner_choices = [questionary.Choice(title=m, value=m) for m in inners]
        selected_inner = questionary.select(
            "Location: " + model_dir_name + current_package,
            choices=inner_choices,
            style=style,
        ).ask()
        if not selected_inner:
            break
        _clear_line()

        if selected_inner == "..":
            if current_package == ".":
                break
            current_package = current_package[:-1].rsplit(".", 1)[-2]+"."
            continue

        if selected_inner.endswith("."):
            current_package += selected_inner
            continue

        current_module = current_package + selected_inner

        choices = []
        choices.append(questionary.Choice(
            title="..",
            value=".."
        ))

        choices.append(questionary.Choice(
            title=f"[ALL] Download entire {current_module}",
            value=current_module
        ))

        groups = registry.list_groups(current_module)
        for group in groups:
            choices.append(questionary.Choice(
                title=f"[GROUP] {group.id}: {group.description}",
                value=f"{current_module}.{group.id}"
            ))

        models = registry.list_models(current_module)
        for model in models:
            choices.append(questionary.Choice(
                title=f"[MODEL] {model.id}",
                value=f"{current_module}.{model.id}"
            ))

        selection = questionary.select(
            "Location: " + model_dir_name + current_module,
            choices=choices,
            style=style,
        ).ask()
        if not selection:
            break
        _clear_line()

        if selection == "..":
            continue
        return selection


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register model commands."""
    model_parser = subparsers.add_parser("model", help="Model management commands")
    model_subparsers = model_parser.add_subparsers(dest="model_action", help="Model actions")

    # model list
    model_list_parser = model_subparsers.add_parser("list", help="List available models and groups")
    model_list_parser.add_argument(
        "targets",
        nargs="*",
        help="Model/group/module references (e.g., 'wan', 'wan.wan22_animate', 'sdxl.*')"
    )

    # model download
    model_download_parser = model_subparsers.add_parser("download", help="Download models")
    model_download_parser.add_argument(
        "targets",
        nargs="*",
        help="Model/group/module references (e.g., 'wan', 'wan.wan22_animate', 'sdxl.sdxl.anikawaxl_v2')"
    )
    model_download_parser.add_argument("--comfyui-root", help="ComfyUI directory path")
    model_download_parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")
    model_parser.set_defaults(func=cmd_model)


def cmd_model_list(args: argparse.Namespace) -> int:
    """List available models and groups."""
    registry = _get_registry()

    targets = args.targets if args.targets else []

    if targets:
        if len(targets) == 1:
            resolved = registry.resolve_to_group(targets[0])
            if not resolved.models:
                print(f"Error: No models found for '{targets[0]}'")
                return 1
            _print_resolved_group(resolved)
        else:
            combined, ref_info = registry.resolve_multiple(targets)

            print("\n📋 Target Analysis:")
            print("-" * 40)
            for ref, ref_type, count in ref_info:
                _print_ref_info(ref, ref_type, count)

            print("\n" + "=" * 40)
            print(f"📊 Total: {len(combined.models)} unique models")
            print("=" * 40)

            _print_resolved_group(combined)
    else:
        _print_model_tree(registry)

    return 0


def cmd_model_download(args: argparse.Namespace) -> int:
    """Download models using unified downloader (via Engine)."""
    engine = ComaniEngine()
    try:
        targets = args.targets if args.targets else []

        if not targets:
            if not (sys.stdin.isatty() and sys.stdout.isatty()):
                print("Error: Interactive mode requires a terminal.")
                print("Use 'comani model list' to see available models.")
                return 1

            print("🎨 ComfyUI Model Downloader")
            print("=" * 40)
            target = _interactive_select(engine.model_pack_registry)
            if not target:
                return 0
            targets = [target]

        if not targets:
            print("Error: Please specify targets to download.")
            print("Use 'comani model list' to see available models.")
            return 1

        success = engine.download_models(targets, dry_run=args.dry_run)
        return 0 if success else 1
    finally:
        engine.close()


def cmd_model(args: argparse.Namespace) -> int:
    """Model subcommand dispatcher."""
    if args.model_action == "list":
        return cmd_model_list(args)
    elif args.model_action == "download":
        return cmd_model_download(args)
    else:
        print("Error: Unknown action. Use 'list' or 'download'.")
        return 1
