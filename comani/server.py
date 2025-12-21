"""
HTTP server for Comani engine.
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Any

from .config import init_config, get_config
from .core.client import ComfyUIClient
from .core.preset import PresetManager
from .core.executor import WorkflowLoader, Executor


class ComaniEngine:
    """Main engine that orchestrates all components."""

    def __init__(self):
        self.config = init_config()
        self.client = ComfyUIClient(self.config.comfyui_url)
        self.preset_manager = PresetManager(self.config.preset_dir)
        self.workflow_loader = WorkflowLoader(self.config.workflow_dir)
        self.executor = Executor(
            self.client,
            self.workflow_loader,
            self.preset_manager,
        )

    def health_check(self) -> dict[str, Any]:
        """Check engine and ComfyUI status."""
        comfyui_ok = self.client.health_check()
        return {
            "engine": "ok",
            "comfyui": "ok" if comfyui_ok else "unreachable",
            "comfyui_url": self.config.comfyui_url,
        }


engine: ComaniEngine | None = None


def get_engine() -> ComaniEngine:
    global engine
    if engine is None:
        engine = ComaniEngine()
    return engine


class RequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Comani API."""

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def _send_error(self, message: str, status: int = 400) -> None:
        self._send_json({"error": message}, status)

    def _read_json_body(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        eng = get_engine()

        if path == "/health":
            self._send_json(eng.health_check())

        elif path == "/presets":
            presets = eng.preset_manager.list_presets()
            self._send_json({"presets": presets})

        elif path == "/workflows":
            workflows = eng.workflow_loader.list_workflows()
            self._send_json({"workflows": workflows})

        elif path.startswith("/preset/"):
            name = path.split("/preset/")[1]
            try:
                preset = eng.preset_manager.get(name)
                self._send_json({
                    "name": preset.name,
                    "base_workflow": preset.base_workflow,
                    "params": preset.params,
                    "mapping": {k: {"node_id": v.node_id, "field_path": v.field_path}
                               for k, v in preset.mapping.items()},
                    "dependencies": preset.dependencies,
                })
            except FileNotFoundError:
                self._send_error(f"Preset not found: {name}", 404)

        elif path == "/queue":
            try:
                queue = eng.client.get_queue()
                self._send_json(queue)
            except Exception as e:
                self._send_error(str(e), 500)

        elif path.startswith("/history"):
            prompt_id = path.split("/history/")[1] if "/history/" in path else None
            try:
                history = eng.client.get_history(prompt_id)
                self._send_json(history)
            except Exception as e:
                self._send_error(str(e), 500)

        else:
            self._send_error("Not found", 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        eng = get_engine()

        try:
            body = self._read_json_body() or {}
        except json.JSONDecodeError:
            self._send_error("Invalid JSON")
            return

        if path == "/execute/preset":
            preset_name = body.get("preset")
            if not preset_name:
                self._send_error("Missing 'preset' field")
                return

            param_overrides = body.get("params", {})
            try:
                result = eng.executor.execute_preset(preset_name, param_overrides)
                self._send_json({
                    "prompt_id": result.prompt_id,
                    "status": result.status,
                    "outputs": result.outputs,
                    "error": result.error,
                    "execution_time": result.execution_time,
                })
            except FileNotFoundError as e:
                self._send_error(str(e), 404)
            except Exception as e:
                self._send_error(str(e), 500)

        elif path == "/execute/workflow":
            workflow_name = body.get("workflow")
            if not workflow_name:
                self._send_error("Missing 'workflow' field")
                return

            preset_data = body.get("preset_data")
            try:
                result = eng.executor.execute_workflow(workflow_name, preset_data)
                self._send_json({
                    "prompt_id": result.prompt_id,
                    "status": result.status,
                    "outputs": result.outputs,
                    "error": result.error,
                    "execution_time": result.execution_time,
                })
            except FileNotFoundError as e:
                self._send_error(str(e), 404)
            except Exception as e:
                self._send_error(str(e), 500)

        elif path == "/execute/raw":
            workflow = body.get("workflow")
            if not workflow:
                self._send_error("Missing 'workflow' field")
                return

            try:
                result = eng.executor.execute_raw(workflow)
                self._send_json({
                    "prompt_id": result.prompt_id,
                    "status": result.status,
                    "outputs": result.outputs,
                    "error": result.error,
                    "execution_time": result.execution_time,
                })
            except Exception as e:
                self._send_error(str(e), 500)

        elif path == "/queue/prompt":
            workflow = body.get("workflow")
            if not workflow:
                self._send_error("Missing 'workflow' field")
                return

            try:
                prompt_id = eng.client.queue_prompt(workflow)
                self._send_json({"prompt_id": prompt_id})
            except Exception as e:
                self._send_error(str(e), 500)

        elif path == "/interrupt":
            success = eng.client.interrupt()
            self._send_json({"success": success})

        elif path == "/clear":
            success = eng.client.clear_queue()
            self._send_json({"success": success})

        else:
            self._send_error("Not found", 404)

    def log_message(self, format: str, *args) -> None:
        print(f"[Comani] {args[0]}")


def run_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the Comani HTTP server."""
    get_engine()
    server = HTTPServer((host, port), RequestHandler)
    print(f"Comani engine running at http://{host}:{port}")
    print(f"ComfyUI target: {get_config().comfyui_url}")
    print("Endpoints:")
    print("  GET  /health          - Health check")
    print("  GET  /presets         - List available presets")
    print("  GET  /workflows       - List available workflows")
    print("  GET  /preset/<name>   - Get preset details")
    print("  GET  /queue           - Get ComfyUI queue")
    print("  GET  /history[/<id>]  - Get execution history")
    print("  POST /execute/preset  - Execute preset")
    print("  POST /execute/workflow- Execute workflow")
    print("  POST /execute/raw     - Execute raw workflow")
    print("  POST /interrupt       - Interrupt execution")
    print("  POST /clear           - Clear queue")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()


def main():
    host = os.getenv("COMANI_HOST", "0.0.0.0")
    port = int(os.getenv("COMANI_PORT", "8080"))
    run_server(host, port)


if __name__ == "__main__":
    main()
