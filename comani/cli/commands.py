"""
CLI entry point for Comani.
"""

import argparse
import sys
from comani.cli import (
    cmd_health,
    cmd_preset,
    cmd_workflow,
    cmd_execute,
    cmd_queue,
    cmd_model,
    cmd_chat,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="comani",
        description="Comani - ComfyUI workflow automation tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Register all command modules
    cmd_model.register_parser(subparsers)
    cmd_workflow.register_parser(subparsers)
    cmd_preset.register_parser(subparsers)
    cmd_health.register_parser(subparsers)
    cmd_execute.register_parser(subparsers)
    cmd_queue.register_parser(subparsers)
    cmd_chat.register_parser(subparsers)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
