"""
Health check commands for Comani.
"""

import argparse
import json
from typing import Any
from comani.core.engine import ComaniEngine


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register health commands."""
    health_parser = subparsers.add_parser("health", help="Check ComfyUI connection status")
    health_parser.set_defaults(func=cmd_health)


def cmd_health(args: argparse.Namespace) -> int:
    """Check ComfyUI connection status."""
    engine = ComaniEngine()
    result = engine.health_check()
    print_json(result)
    return 0 if result["comfyui"] == "ok" else 1
