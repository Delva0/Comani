"""
Preset commands for Comani.
"""

import argparse
from comani.core.engine import ComaniEngine


def cmd_preset_list(args: argparse.Namespace) -> int:
    """List all available presets."""
    engine = ComaniEngine()
    presets = engine.list_presets()
    for p in presets:
        print(p)
    return 0


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register preset commands."""
    preset_parser = subparsers.add_parser("preset", help="Preset management commands")
    preset_subparsers = preset_parser.add_subparsers(dest="preset_action", help="Preset actions")
    preset_subparsers.add_parser("list", help="List available presets")
    preset_parser.set_defaults(func=cmd_preset)


def cmd_preset(args: argparse.Namespace) -> int:
    """Preset subcommand dispatcher."""
    if args.preset_action == "list":
        return cmd_preset_list(args)
    else:
        print("Error: Unknown action. Use 'list'.")
        return 1
