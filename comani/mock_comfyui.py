"""
Mock ComfyUI server for testing.
Simulates ComfyUI API responses on port 8188.
"""

import json
import uuid
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any


class MockComfyUIState:
    """Shared state for the mock server."""

    def __init__(self):
        self.queue_running: list[dict] = []
        self.queue_pending: list[dict] = []
        self.history: dict[str, dict] = {}
        self.lock = threading.Lock()

    def add_prompt(self, prompt: dict, client_id: str) -> str:
        prompt_id = str(uuid.uuid4())
        with self.lock:
            self.queue_pending.append({
                "prompt_id": prompt_id,
                "prompt": prompt,
                "client_id": client_id,
            })

        threading.Thread(
            target=self._process_prompt,
            args=(prompt_id, prompt),
            daemon=True,
        ).start()

        return prompt_id

    def _process_prompt(self, prompt_id: str, prompt: dict) -> None:
        with self.lock:
            for i, item in enumerate(self.queue_pending):
                if item["prompt_id"] == prompt_id:
                    self.queue_running.append(self.queue_pending.pop(i))
                    break

        time.sleep(1.0)

        outputs = {}
        for node_id, node in prompt.items():
            if isinstance(node, dict):
                class_type = node.get("class_type", "")
                if class_type == "SaveImage":
                    outputs[node_id] = {
                        "images": [{
                            "filename": f"ComfyUI_{prompt_id[:8]}.png",
                            "subfolder": "",
                            "type": "output",
                        }]
                    }

        with self.lock:
            self.queue_running = [
                item for item in self.queue_running
                if item["prompt_id"] != prompt_id
            ]

            self.history[prompt_id] = {
                "prompt": prompt,
                "outputs": outputs,
                "status": {
                    "status_str": "success",
                    "completed": True,
                    "messages": [],
                },
            }

    def get_queue(self) -> dict:
        with self.lock:
            return {
                "queue_running": self.queue_running,
                "queue_pending": self.queue_pending,
            }

    def get_history(self, prompt_id: str | None = None) -> dict:
        with self.lock:
            if prompt_id:
                if prompt_id in self.history:
                    return {prompt_id: self.history[prompt_id]}
                return {}
            return dict(self.history)

    def clear_queue(self) -> None:
        with self.lock:
            self.queue_pending.clear()

    def interrupt(self) -> None:
        with self.lock:
            self.queue_running.clear()


state = MockComfyUIState()


class MockComfyUIHandler(BaseHTTPRequestHandler):
    """HTTP handler for mock ComfyUI server."""

    def _send_json(self, data: Any, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def _read_json_body(self) -> dict | None:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return None
        body = self.rfile.read(content_length)
        return json.loads(body.decode("utf-8"))

    def do_GET(self):
        if self.path == "/system_stats":
            self._send_json({
                "system": {
                    "os": "linux",
                    "python_version": "3.11.0",
                    "embedded_python": False,
                },
                "devices": [{
                    "name": "mock_gpu",
                    "type": "cuda",
                    "vram_total": 24000000000,
                    "vram_free": 20000000000,
                }],
            })

        elif self.path == "/queue":
            self._send_json(state.get_queue())

        elif self.path.startswith("/history"):
            if "/history/" in self.path:
                prompt_id = self.path.split("/history/")[1]
                self._send_json(state.get_history(prompt_id))
            else:
                self._send_json(state.get_history())

        elif self.path == "/object_info" or self.path.startswith("/object_info/"):
            self._send_json({
                "CLIPTextEncode": {
                    "input": {"required": {"text": ["STRING", {"multiline": True}]}},
                    "output": ["CONDITIONING"],
                },
                "KSampler": {
                    "input": {"required": {"seed": ["INT"], "steps": ["INT"]}},
                    "output": ["LATENT"],
                },
                "SaveImage": {
                    "input": {"required": {"images": ["IMAGE"]}},
                    "output": [],
                },
            })

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/prompt":
            body = self._read_json_body()
            if not body or "prompt" not in body:
                self._send_json({"error": "Missing prompt"}, 400)
                return

            prompt = body["prompt"]
            client_id = body.get("client_id", "unknown")
            prompt_id = state.add_prompt(prompt, client_id)

            self._send_json({
                "prompt_id": prompt_id,
                "number": len(state.queue_pending) + len(state.queue_running),
            })

        elif self.path == "/interrupt":
            state.interrupt()
            self._send_json({"success": True})

        elif self.path == "/queue":
            body = self._read_json_body()
            if body and body.get("clear"):
                state.clear_queue()
            self._send_json({"success": True})

        else:
            self._send_json({"error": "Not found"}, 404)

    def log_message(self, format: str, *args) -> None:
        print(f"[MockComfyUI] {args[0]}")


def run_mock_server(host: str = "127.0.0.1", port: int = 8188) -> None:
    """Start the mock ComfyUI server."""
    server = HTTPServer((host, port), MockComfyUIHandler)
    print(f"Mock ComfyUI server running at http://{host}:{port}")
    print("Endpoints:")
    print("  GET  /system_stats    - System stats")
    print("  GET  /queue           - Queue status")
    print("  GET  /history[/<id>]  - Execution history")
    print("  GET  /object_info     - Node info")
    print("  POST /prompt          - Queue prompt")
    print("  POST /interrupt       - Interrupt")
    print("  POST /queue           - Clear queue")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down mock server...")
        server.shutdown()


def main():
    run_mock_server()


if __name__ == "__main__":
    main()
