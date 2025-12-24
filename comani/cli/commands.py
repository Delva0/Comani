"""
CLI commands for Comani.
"""

import argparse
import json
import sys
import os
from typing import Any

from comani.core.engine import ComaniEngine
from comani.model.model_pack import ModelPackRegistry, ResolvedGroup
from comani.config import get_config

MODELS_ROOT = get_config().model_dir


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def cmd_health(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    result = engine.health_check()
    print_json(result)
    return 0 if result["comfyui"] == "ok" else 1


def cmd_list_presets(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    presets = engine.list_presets()
    for p in presets:
        print(p)
    return 0


def cmd_list_workflows(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    workflows = engine.list_workflows()
    for w in workflows:
        print(w)
    return 0


def cmd_execute(args: argparse.Namespace) -> int:
    engine = ComaniEngine()

    param_overrides: dict[str, Any] = {}
    if args.params:
        for param in args.params:
            key, value = param.split("=", 1)
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
            param_overrides[key] = value

    print(f"Executing preset: {args.preset}")
    if param_overrides:
        print(f"Overrides: {param_overrides}")

    result = engine.execute_preset(args.preset, param_overrides if param_overrides else None)

    print(f"\nPrompt ID: {result.prompt_id}")
    print(f"Status: {result.status}")
    print(f"Execution time: {result.execution_time:.2f}s")

    if result.error:
        print(f"Error: {result.error}")
        return 1

    if result.outputs:
        print("\nOutputs:")
        print_json(result.outputs)

    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    queue = engine.get_queue()
    print_json(queue)
    return 0


def cmd_interrupt(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    success = engine.interrupt()
    print("Interrupted" if success else "Failed to interrupt")
    return 0 if success else 1


def cmd_clear(args: argparse.Namespace) -> int:
    engine = ComaniEngine()
    success = engine.clear_queue()
    print("Queue cleared" if success else "Failed to clear queue")
    return 0 if success else 1


# =========================================================================
# Model Commands (new unified API with Python-like naming)
# =========================================================================

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
        # print(f"     URL: {model.url[:60]}..." if len(model.url) > 60 else f"     URL: {model.url}")
        # print(f"     Path: {model.path}")


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
        # print(f"current package: {current_package}")
        inners = _get_package_inners(current_package)
        # print(f"inners: {inners}")

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
            # Go back to package selection
            current_package = current_package[:-1].rsplit(".", 1)[-2]+"."
            continue

        if selected_inner.endswith("."):
            # Add models
            current_package += selected_inner
            continue

        # Then select model or group
        current_module = current_package + selected_inner

        choices = []
        # Add back option
        choices.append(questionary.Choice(
            title="..",
            value=".."
        ))

        # Add "all" option
        choices.append(questionary.Choice(
            title=f"[ALL] Download entire {current_module}",
            value=current_module
        ))

        # Add groups
        groups = registry.list_groups(current_module)
        for group in groups:
            choices.append(questionary.Choice(
                title=f"[GROUP] {group.id}: {group.description}",
                value=f"{current_module}.{group.id}"
            ))

        # Add models
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
            continue  # Go back to module selection
        return selection


def cmd_model_list(args: argparse.Namespace) -> int:
    """List available models and groups."""
    registry = _get_registry()

    targets = args.targets if args.targets else []

    if targets:
        # Show details for specific targets (supports multiple)
        if len(targets) == 1:
            resolved = registry.resolve_to_group(targets[0])
            if not resolved.models:
                print(f"Error: No models found for '{targets[0]}'")
                return 1
            _print_resolved_group(resolved)
        else:
            # Multiple targets - use resolve_multiple
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

        # Interactive mode
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


# =========================================================================
# Chat Commands (Grok API integration)
# =========================================================================

def cmd_chat(args: argparse.Namespace) -> int:
    """Chat with Grok AI using grok-api."""
    from grok_api.core import Grok

    try:
        client = Grok(model=args.model)
    except Exception as e:
        print(f"Error initializing Grok: {e}")
        return 1

    extra_data = None

    # Handle initial prompt
    if args.prompt:
        prompt = args.prompt
        if args.system:
            prompt = f"System: {args.system}\n\nUser: {prompt}"

        print("🤖 Grok: ", end="", flush=True)
        try:
            for chunk in client.chat_stream(prompt):
                if chunk.get("error"):
                    print(f"\nError: {chunk['error']}")
                    return 1
                if chunk.get("token"):
                    print(chunk["token"], end="", flush=True)
            print() # Newline after response
            return 0
        except Exception as e:
            print(f"\nError during chat: {e}")
            return 1

    # Interactive mode
    print("🤖 Grok Chat (type 'exit' to quit)")
    print("=" * 40)

    while True:
        try:
            user_input = input("\n👤 You: ").strip()
            if user_input.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            if not user_input:
                continue

            prompt = user_input
            if extra_data is None and args.system:
                prompt = f"System: {args.system}\n\nUser: {user_input}"

            print("🤖 Grok: ", end="", flush=True)

            last_meta = None
            for chunk in client.chat_stream(prompt, extra_data=extra_data):
                if chunk.get("error"):
                    print(f"\nError: {chunk['error']}")
                    break
                if chunk.get("token"):
                    print(chunk["token"], end="", flush=True)
                if chunk.get("meta"):
                    last_meta = chunk["meta"]

            print() # Newline after response
            if last_meta:
                extra_data = last_meta.get("extra_data")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except EOFError:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {e}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="comani",
        description="Comani - ComfyUI workflow automation tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # health
    subparsers.add_parser("health", help="Check ComfyUI connection status")

    # list-presets
    subparsers.add_parser("list-presets", help="List available presets")

    # list-workflows
    subparsers.add_parser("list-workflows", help="List available workflows")

    # execute
    exec_parser = subparsers.add_parser("execute", help="Execute a preset")
    exec_parser.add_argument("preset", help="Preset name to execute")
    exec_parser.add_argument(
        "-p", "--param",
        dest="params",
        action="append",
        metavar="KEY=VALUE",
        help="Override preset parameter (can be used multiple times)",
    )

    # queue
    subparsers.add_parser("queue", help="Show current ComfyUI queue")

    # interrupt
    subparsers.add_parser("interrupt", help="Interrupt current execution")

    # clear
    subparsers.add_parser("clear", help="Clear the execution queue")

    # model (new unified command)
    model_parser = subparsers.add_parser("model", help="Model management commands")
    model_subparsers = model_parser.add_subparsers(dest="model_action", help="Model actions")

    # model list - supports multiple targets with Python-like syntax
    model_list_parser = model_subparsers.add_parser("list", help="List available models and groups")
    model_list_parser.add_argument(
        "targets",
        nargs="*",
        help="Model/group/module references (e.g., 'wan', 'wan.wan22_animate', 'sdxl.*')"
    )

    # model download - supports multiple targets with Python-like syntax
    model_download_parser = model_subparsers.add_parser("download", help="Download models")
    model_download_parser.add_argument(
        "targets",
        nargs="*",
        help="Model/group/module references (e.g., 'wan', 'wan.wan22_animate', 'sdxl.sdxl.anikawaxl_v2')"
    )
    model_download_parser.add_argument("--comfyui-root", help="ComfyUI directory path")
    model_download_parser.add_argument("--dry-run", action="store_true", help="Show what would be downloaded without downloading")

    # chat - Grok API integration
    chat_parser = subparsers.add_parser("chat", help="Chat with Grok AI")
    chat_parser.add_argument("prompt", nargs="?", help="Prompt to send (omit for interactive mode)")
    chat_parser.add_argument("-s", "--system", help="System prompt")
    chat_parser.add_argument("-m", "--model", default="grok-3-fast", help="Model to use (default: grok-3-fast)")
    chat_parser.add_argument("--no-thinking", action="store_true", help="Hide thinking/reasoning output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "health": cmd_health,
        "list-presets": cmd_list_presets,
        "list-workflows": cmd_list_workflows,
        "execute": cmd_execute,
        "queue": cmd_queue,
        "interrupt": cmd_interrupt,
        "clear": cmd_clear,
        "model": cmd_model,
        "chat": cmd_chat,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
