#!/usr/bin/env python
"""
CLI tool to download models from package paths, .py scripts, or .yml configs.

Usage:
  comani-download-model                     # Interactive mode
  comani-download-model --list              # List all available models
  comani-download-model sdxl/loras.misc     # Package path (dot notation for subdirs)
  comani-download-model wan/wan22_i2v       # Package path
  comani-download-model /path/to/model.py   # Absolute path
  comani-download-model ./model.yml         # Relative path

Package path format:
  <category>/<path>.<name>  e.g., sdxl/loras.misc -> models/sdxl/loras/misc.{py,yml}
  <category>/<name>         e.g., wan/wan22_i2v -> models/wan/wan22_i2v.{py,yml}
"""
import runpy
import sys
from pathlib import Path

from comani.models.download import download_yml

# Package models root directory
MODELS_ROOT = Path(__file__).parent.parent / "models"

HELP_TEXT = """
🎨 ComfyUI Anime Model Downloader

Usage:
  comani-download-model                          Interactive mode (select model)
  comani-download-model --list                   List all available models
  comani-download-model <path> [args...]         Download specified model

Path formats:
  sdxl/loras.misc                            Package path (dot = subdir)
  wan/wan22_i2v                              Package path
  /absolute/path/to/model.py                 Absolute file path
  ./relative/path/to/model.yml               Relative file path

Extra arguments:
  For .py scripts: passed directly (e.g. --obsession)
  For .yml files: --comfyui-root PATH to specify ComfyUI directory

Examples:
  comani-download-model sdxl/boleromix
  comani-download-model sdxl/loras.artists --comfyui-root /workspace/ComfyUI
  comani-download-model sdxl/dupli_cat_flat --obsession
"""


def resolve_package_path(pkg_path: str) -> Path | None:
    """
    Resolve package path to actual file path.
    Examples:
      sdxl/loras.misc -> models/sdxl/loras/misc.{py,yml}
      wan/wan22_i2v -> models/wan/wan22_i2v.{py,yml}
    """
    # Split by / to get components, then handle dot notation
    parts = pkg_path.replace(".", "/").split("/")
    relative_path = Path(*parts)

    # Try extensions in order
    for ext in (".py", ".yml", ".yaml"):
        full_path = MODELS_ROOT / f"{relative_path}{ext}"
        if full_path.exists():
            return full_path

    return None


def scan_models_tree(base_dir: Path, prefix: str = "") -> list[tuple[str, Path]]:
    """
    Recursively scan directory for model files (.py, .yml, .yaml).
    Returns list of (display_name, path) tuples.
    """
    results = []
    if not base_dir.exists():
        return results

    for item in sorted(base_dir.iterdir()):
        if item.name.startswith(("_", ".")):
            continue

        display = f"{prefix}{item.name}" if prefix else item.name

        if item.is_dir():
            results.extend(scan_models_tree(item, f"{display}/"))
        elif item.suffix.lower() in (".py", ".yml", ".yaml"):
            results.append((display, item))

    return results


def build_category_tree() -> dict[str, list[tuple[str, Path]]]:
    """
    Build a tree of model categories and their files.
    Returns {category: [(display_name, path), ...]}
    """
    tree = {}
    for category_dir in sorted(MODELS_ROOT.iterdir()):
        if category_dir.is_dir() and not category_dir.name.startswith(("_", ".")):
            models = scan_models_tree(category_dir)
            if models:
                tree[category_dir.name] = models
    return tree


def print_model_list() -> None:
    """Print all available models."""
    print("\n📦 Available Models:")
    print("=" * 50)
    tree = build_category_tree()
    for category, models in tree.items():
        print(f"\n{category}/")
        for name, path in models:
            # Convert to package path format for easy copy-paste
            rel = path.relative_to(MODELS_ROOT)
            pkg_path = str(rel.with_suffix("")).replace("/", ".", 1).replace("/", ".")
            pkg_path = pkg_path.replace(".", "/", 1)  # first . back to /
            print(f"  {name:40} -> {pkg_path}")


def interactive_select() -> Path | None:
    """Show interactive menu to select a model."""
    import questionary
    from questionary import Style

    style = Style([
        ("qmark", "fg:cyan bold"),
        ("question", "fg:white bold"),
        ("answer", "fg:green bold"),
        ("pointer", "fg:cyan bold"),
        ("highlighted", "fg:cyan bold"),
        ("selected", "fg:green"),
        ("separator", "fg:gray"),
    ])

    tree = build_category_tree()
    if not tree:
        print("No models found in package.")
        return None

    # Step 1: Select category
    category = questionary.select(
        "Select model category:",
        choices=list(tree.keys()),
        style=style,
    ).ask()

    if not category:
        return None

    # Step 2: Select model file
    models = tree[category]
    choices = [questionary.Choice(title=name, value=path) for name, path in models]

    selected = questionary.select(
        f"Select model from {category}:",
        choices=choices,
        style=style,
    ).ask()

    return selected


def download_py(py_path: Path, extra_args: list[str]) -> None:
    """Execute .py script as __main__."""
    sys.argv = [str(py_path)] + extra_args
    runpy.run_path(str(py_path), run_name="__main__")


def download_file(file_path: Path, extra_args: list[str]) -> None:
    """Download model based on file type."""
    suffix = file_path.suffix.lower()

    if suffix == ".py":
        download_py(file_path, extra_args)
    elif suffix in (".yml", ".yaml"):
        # Parse --comfyui-root from extra args
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("--comfyui-root", type=Path, default=None)
        args, _ = parser.parse_known_args(extra_args)
        download_yml(file_path, args.comfyui_root)
    else:
        print(f"Error: Unsupported file type: {suffix}")
        print("Supported types: .py, .yml, .yaml")
        sys.exit(1)


def is_terminal() -> bool:
    """Check if running in an interactive terminal."""
    return sys.stdin.isatty() and sys.stdout.isatty()


def main():
    # Handle help flags
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(HELP_TEXT)
        return

    # Handle --list flag
    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        print_model_list()
        return

    # No arguments: interactive mode
    if len(sys.argv) < 2:
        print("🎨 ComfyUI Anime Model Downloader")
        print("=" * 40)

        if not is_terminal():
            print("\nError: Interactive mode requires a terminal.")
            print("Use --list to see available models, or specify a model path.")
            print("\nExample: comani-download-model sdxl/boleromix")
            sys.exit(1)

        selected = interactive_select()
        if selected:
            print(f"\n📦 Selected: {selected.relative_to(MODELS_ROOT)}")
            download_file(selected, [])
        return

    # Has argument: parse it
    target = sys.argv[1]
    extra_args = sys.argv[2:]

    # Check if it's an absolute or relative file path
    target_path = Path(target)
    if target_path.is_absolute():
        if not target_path.exists():
            print(f"Error: File not found: {target_path}")
            sys.exit(1)
        download_file(target_path, extra_args)
        return

    # Check if it looks like a relative path (contains extension)
    if target_path.suffix:
        # It's a relative path with extension
        resolved = target_path.resolve()
        if resolved.exists():
            download_file(resolved, extra_args)
            return
        # Try relative to models root
        maybe_in_models = MODELS_ROOT / target_path
        if maybe_in_models.exists():
            download_file(maybe_in_models, extra_args)
            return
        print(f"Error: File not found: {target}")
        sys.exit(1)

    # Treat as package path (e.g., sdxl/loras.misc)
    resolved = resolve_package_path(target)
    if resolved:
        download_file(resolved, extra_args)
    else:
        print(f"Error: Could not resolve package path: {target}")
        print("\nUse --list to see available models, or --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
