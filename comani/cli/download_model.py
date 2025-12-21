#!/usr/bin/env python
"""
CLI tool to download models from .yml configs.

Usage:
  comani-download-model                     # Interactive mode
  comani-download-model --list              # List all available models
  comani-download-model sdxl/boleromix      # Package path
  comani-download-model sdxl/loras/artists  # Package path with subdirs
  comani-download-model /path/to/model.yml  # Absolute path
  comani-download-model ./model.yml         # Relative path
"""
import sys
from pathlib import Path

from comani.utils.model_downloader import download_yml

MODELS_ROOT = Path(__file__).parent.parent / "models"

HELP_TEXT = """
🎨 ComfyUI Anime Model Downloader

Usage:
  comani-download-model                          Interactive mode (select model)
  comani-download-model --list                   List all available models
  comani-download-model <path> [--comfyui-root]  Download specified model

Path formats:
  sdxl/boleromix                             Package path
  sdxl/loras/artists                         Package path with subdirs
  /absolute/path/to/model.yml                Absolute file path
  ./relative/path/to/model.yml               Relative file path

Options:
  --comfyui-root PATH  Specify ComfyUI directory

Examples:
  comani-download-model sdxl/boleromix
  comani-download-model wan/wan22_i2v_fp8 --comfyui-root /workspace/ComfyUI
"""


def resolve_package_path(pkg_path: str) -> Path | None:
    """Resolve package path to .yml file."""
    parts = pkg_path.split("/")
    relative_path = Path(*parts)

    for ext in (".yml", ".yaml"):
        full_path = MODELS_ROOT / f"{relative_path}{ext}"
        if full_path.exists():
            return full_path
    return None


def scan_models_tree(base_dir: Path, prefix: str = "") -> list[tuple[str, Path]]:
    """Recursively scan directory for .yml files."""
    results = []
    if not base_dir.exists():
        return results

    for item in sorted(base_dir.iterdir()):
        if item.name.startswith(("_", ".")):
            continue

        display = f"{prefix}{item.name}" if prefix else item.name

        if item.is_dir():
            results.extend(scan_models_tree(item, f"{display}/"))
        elif item.suffix.lower() in (".yml", ".yaml"):
            results.append((display, item))

    return results


def build_category_tree(base_dir: Path | None = None) -> dict[str, Path | dict]:
    """
    Build a nested tree of model categories and files.
    Returns dict where keys are names, values are either Path (for files) or nested dict (for dirs).
    """
    if base_dir is None:
        base_dir = MODELS_ROOT

    tree = {}
    if not base_dir.exists():
        return tree

    for item in sorted(base_dir.iterdir()):
        if item.name.startswith(("_", ".")):
            continue

        if item.is_dir():
            subtree = build_category_tree(item)
            if subtree:
                tree[item.name] = subtree
        elif item.suffix.lower() in (".yml", ".yaml"):
            tree[item.stem] = item

    return tree


def print_model_list(tree: dict | None = None, indent: int = 0) -> None:
    """Print all available models recursively."""
    if tree is None:
        print("\n📦 Available Models:")
        print("=" * 50)
        tree = build_category_tree()

    prefix = "  " * indent
    for name, value in tree.items():
        if isinstance(value, Path):
            pkg_path = str(value.relative_to(MODELS_ROOT).with_suffix(""))
            print(f"{prefix}📄 {name:40} -> {pkg_path}")
        else:
            print(f"{prefix}📁 {name}/")
            print_model_list(value, indent + 1)


def interactive_select() -> Path | None:
    """Show interactive menu to select a model with hierarchical navigation."""
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

    path_stack = []
    current = tree

    while True:
        # Build choices: directories first, then files
        dirs = [(k, v) for k, v in current.items() if isinstance(v, dict)]
        files = [(k, v) for k, v in current.items() if isinstance(v, Path)]

        choices = []
        if path_stack:
            choices.append(questionary.Choice(title="⬅️  ..", value="__back__"))

        for name, _ in dirs:
            choices.append(questionary.Choice(title=f"📁 {name}/", value=("dir", name)))
        for name, path in files:
            choices.append(questionary.Choice(title=f"📄 {name}", value=("file", path)))

        current_path = "/".join(path_stack) if path_stack else "models"
        selection = questionary.select(current_path, choices=choices, style=style).ask()

        if selection is None:
            return None

        if selection == "__back__":
            path_stack.pop()
            # Navigate back up
            current = tree
            for p in path_stack:
                current = current[p]
        elif selection[0] == "dir":
            path_stack.append(selection[1])
            current = current[selection[1]]
        else:
            return selection[1]


def is_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def main():
    if len(sys.argv) >= 2 and sys.argv[1] in ("-h", "--help"):
        print(HELP_TEXT)
        return

    if len(sys.argv) >= 2 and sys.argv[1] == "--list":
        print_model_list()
        return

    # Parse --comfyui-root from args
    comfyui_root = None
    args = sys.argv[1:]
    if "--comfyui-root" in args:
        idx = args.index("--comfyui-root")
        if idx + 1 < len(args):
            comfyui_root = Path(args[idx + 1])
            args = args[:idx] + args[idx + 2:]

    # No target: interactive mode
    if not args:
        print("🎨 ComfyUI Anime Model Downloader")
        print("=" * 40)

        if not is_terminal():
            print("\nError: Interactive mode requires a terminal.")
            print("Use --list to see available models, or specify a model path.")
            sys.exit(1)

        selected = interactive_select()
        if selected:
            print(f"\n📦 Selected: {selected.relative_to(MODELS_ROOT)}")
            download_yml(selected, comfyui_root)
        return

    target = args[0]
    target_path = Path(target)

    # Absolute path
    if target_path.is_absolute():
        if not target_path.exists():
            print(f"Error: File not found: {target_path}")
            sys.exit(1)
        download_yml(target_path, comfyui_root)
        return

    # Relative path with extension
    if target_path.suffix:
        resolved = target_path.resolve()
        if resolved.exists():
            download_yml(resolved, comfyui_root)
            return
        maybe_in_models = MODELS_ROOT / target_path
        if maybe_in_models.exists():
            download_yml(maybe_in_models, comfyui_root)
            return
        print(f"Error: File not found: {target}")
        sys.exit(1)

    # Package path
    resolved = resolve_package_path(target)
    if resolved:
        download_yml(resolved, comfyui_root)
    else:
        print(f"Error: Could not resolve package path: {target}")
        print("\nUse --list to see available models, or --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
