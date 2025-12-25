"""
Queue management commands for Comani.
"""

import argparse
import json
from typing import Any
from comani.core.engine import ComaniEngine


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register queue commands."""
    queue_parser = subparsers.add_parser("queue", help="Queue management commands")
    queue_subparsers = queue_parser.add_subparsers(dest="queue_action", help="Queue actions")

    # queue list
    queue_subparsers.add_parser("list", help="Show current ComfyUI queue")

    # queue interrupt
    queue_subparsers.add_parser("interrupt", help="Interrupt current execution")

    # queue clear
    queue_subparsers.add_parser("clear", help="Clear the execution queue")

    queue_parser.set_defaults(func=cmd_queue)


def cmd_queue_list(args: argparse.Namespace) -> int:
    """Show current ComfyUI queue."""
    engine = ComaniEngine()
    queue = engine.get_queue()
    print_json(queue)
    return 0


def cmd_queue(args: argparse.Namespace) -> int:
    """Queue subcommand dispatcher."""
    if args.queue_action == "list" or not args.queue_action:
        return cmd_queue_list(args)
    elif args.queue_action == "interrupt":
        return cmd_interrupt(args)
    elif args.queue_action == "clear":
        return cmd_clear(args)
    else:
        print(f"Error: Unknown action '{args.queue_action}'. Use 'list', 'interrupt', or 'clear'.")
        return 1


def cmd_interrupt(args: argparse.Namespace) -> int:
    """Interrupt current execution."""
    engine = ComaniEngine()
    success = engine.interrupt()
    print("Interrupted" if success else "Failed to interrupt")
    return 0 if success else 1


def cmd_clear(args: argparse.Namespace) -> int:
    """Clear the execution queue."""
    engine = ComaniEngine()
    success = engine.clear_queue()
    print("Queue cleared" if success else "Failed to clear queue")
    return 0 if success else 1
