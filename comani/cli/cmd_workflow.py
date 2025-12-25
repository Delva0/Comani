"""
Workflow commands for Comani.
"""

import argparse
from comani.core.engine import ComaniEngine


def cmd_workflow_list(args: argparse.Namespace) -> int:
    """List all available workflows."""
    engine = ComaniEngine()
    workflows = engine.list_workflows()
    for w in workflows:
        print(w)
    return 0


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register workflow commands."""
    workflow_parser = subparsers.add_parser("workflow", help="Workflow management commands")
    workflow_subparsers = workflow_parser.add_subparsers(dest="workflow_action", help="Workflow actions")
    workflow_subparsers.add_parser("list", help="List available workflows")
    workflow_parser.set_defaults(func=cmd_workflow)


def cmd_workflow(args: argparse.Namespace) -> int:
    """Workflow subcommand dispatcher."""
    if args.workflow_action == "list":
        return cmd_workflow_list(args)
    else:
        print("Error: Unknown action. Use 'list'.")
        return 1
