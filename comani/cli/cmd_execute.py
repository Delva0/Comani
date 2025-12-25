"""
Execution commands for Comani.
"""

import argparse
import json
import logging
import os
from typing import Any
from tqdm import tqdm
from comani.core.engine import ComaniEngine


def register_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register execute commands."""
    exec_parser = subparsers.add_parser("execute", help="Execute a preset")
    exec_parser.add_argument("preset", help="Preset name to execute")
    exec_parser.add_argument(
        "-p", "--param",
        dest="params",
        action="append",
        metavar="KEY=VALUE",
        help="Override preset parameter (can be used multiple times)",
    )
    exec_parser.set_defaults(func=cmd_execute)


def cmd_execute(args: argparse.Namespace) -> int:
    """Execute a preset."""
    # Set logging level to DEBUG if requested or by default for now
    logging.basicConfig(level=logging.DEBUG if os.getenv("DEBUG") else logging.ERROR, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

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

    is_workflow = args.preset.lower().endswith(".json")

    if is_workflow:
        print(f"Executing workflow: {args.preset}")
        # Workflows don't support overrides for now
        param_overrides = {}
    else:
        print(f"Executing preset: {args.preset}")
        # Filter overrides based on preset mapping
        try:
            preset = engine.preset_manager.get(args.preset)
            valid_overrides = {}
            for k, v in param_overrides.items():
                if k in preset.mapping:
                    valid_overrides[k] = v
            param_overrides = valid_overrides
        except Exception:
            # If preset fails to load, let engine handle it later
            pass

        if param_overrides:
            print(f"Overrides: {param_overrides}")
    print()

    # Progress bar setup
    pbar = None
    progress_node = None

    def progress_callback(msg_type, data):
        nonlocal pbar, progress_node
        if msg_type == "progress":
            node_id = data.get("node")
            value = data.get("value", 0)
            max_val = data.get("max", 100)

            # If node changed, close old pbar and start new one
            if pbar is not None and node_id != progress_node:
                pbar.close()
                pbar = None

            if pbar is None:
                pbar = tqdm(total=max_val, unit="step", leave=True)
                progress_node = node_id
                pbar.set_description(f"Node {node_id}")

            pbar.n = value
            pbar.total = max_val
            pbar.refresh()
        elif msg_type == "executing":
            node_id = data.get("node")
            # If a node starts executing, and it's not the one we are tracking progress for,
            # it might mean the previous KSampler finished.
            if node_id is not None and node_id != progress_node and pbar is not None:
                pbar.close()
                pbar = None
                progress_node = None

            if node_id is not None:
                # Provide some feedback for nodes without progress steps
                if pbar is None:
                    # We can't use tqdm here easily without knowing max_val,
                    # but we can print a status line
                    print(f"Node {node_id} is executing...", end="\n")  # \r ?
                else:
                    pbar.set_description(f"Node {node_id}")

            # If everything is finished
            if node_id is None:
                if pbar is not None:
                    pbar.close()
                    pbar = None
                    progress_node = None
                print("\nExecution finished.")
        elif msg_type == "cached":
            nodes = data.get("nodes", [])
            if nodes:
                print(f"Nodes {', '.join(map(str, nodes))} are cached.")
            else:
                print("Using cached result from ComfyUI.")
        elif msg_type == "executed":
            # Optional: handle executed message if needed
            pass

    try:
        if is_workflow:
            result = engine.execute_workflow_by_name(workflow_name=args.preset, progress_callback=progress_callback)
        else:
            result = engine.execute_workflow_by_name(preset_name=args.preset, param_overrides=param_overrides if param_overrides else None, progress_callback=progress_callback)
    finally:
        if pbar:
            pbar.close()

    print(f"\nPrompt ID: {result.prompt_id}")
    print(f"Status: {result.status}")
    print(f"Execution time: {result.execution_time:.2f}s")

    if result.error:
        logger.error("Execution failed: %s", result.error)
        print(f"Error: {result.error}")
        return 1

    if result.outputs:
        output_dir = engine.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"\nSaving outputs to: {output_dir}")

        import datetime
        now = datetime.datetime.now()

        def resolve_placeholders(path_str: str) -> str:
            """Resolve ComfyUI-style date/time placeholders."""
            res = path_str
            res = res.replace("%date:yyyy-MM-dd%", now.strftime("%Y-%m-%d"))
            res = res.replace("%date:HH-mm-ss%", now.strftime("%H-%M-%S"))
            # Add more as needed or use a regex
            return res

        for node_id, node_output in result.outputs.items():
            for output_type in ["images", "gifs", "videos"]:
                if output_type in node_output:
                    for item in node_output[output_type]:
                        filename = item["filename"]
                        subfolder = item.get("subfolder", "")
                        folder_type = item.get("type", "output")

                        try:
                            data = engine.client.get_file(filename, subfolder, folder_type)

                            # Resolve placeholders for local storage
                            local_subfolder = resolve_placeholders(subfolder)
                            local_filename = resolve_placeholders(filename)

                            target_path = output_dir / local_subfolder / local_filename
                            target_path.parent.mkdir(parents=True, exist_ok=True)

                            with open(target_path, "wb") as f:
                                f.write(data)
                            print(f"  - Saved: {target_path}")
                        except Exception as e:
                            print(f"  - Failed to download {filename}: {e}")

    return 0
