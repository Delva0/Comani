"""
CLI commands for Comani.
"""

import argparse
import json
import sys
from typing import Any

from ..core.engine import ComaniEngine


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
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
