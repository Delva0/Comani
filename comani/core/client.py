"""
ComfyUI WebSocket/HTTP client for remote communication.
"""

import json
import uuid
import time
from typing import Any
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from comani.config import get_config


@dataclass
class ComfyUIResult:
    """Result from ComfyUI execution."""
    prompt_id: str
    status: str  # "success", "error", "timeout"
    outputs: dict[str, Any] | None = None
    error: str | None = None
    execution_time: float = 0.0


class ComfyUIClient:
    """Client for communicating with ComfyUI server."""

    def __init__(
        self,
        base_url: str,
        timeout: int = 300,
        auth: tuple[str, str] | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

        # Support HTTP Basic Auth from config or parameter
        if auth:
            self.auth = auth
        else:
            self.auth = get_config().auth

    def _url(self, path: str) -> str:
        return urljoin(self.base_url + "/", path.lstrip("/"))

    def health_check(self) -> bool:
        """Check if ComfyUI server is reachable."""
        try:
            resp = requests.get(self._url("/system_stats"), timeout=5, auth=self.auth)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_queue(self) -> dict[str, Any]:
        """Get current queue status."""
        resp = requests.get(self._url("/queue"), timeout=10, auth=self.auth)
        resp.raise_for_status()
        return resp.json()

    def get_history(self, prompt_id: str | None = None) -> dict[str, Any]:
        """Get execution history."""
        path = f"/history/{prompt_id}" if prompt_id else "/history"
        resp = requests.get(self._url(path), timeout=10, auth=self.auth)
        resp.raise_for_status()
        return resp.json()

    def queue_prompt(self, workflow: dict[str, Any]) -> str:
        """
        Queue a workflow for execution.
        Example: client.queue_prompt(workflow_dict) to submit workflow
        """
        payload = {
            "prompt": workflow,
            "client_id": self.client_id,
        }
        resp = requests.post(
            self._url("/prompt"),
            json=payload,
            timeout=30,
            auth=self.auth,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["prompt_id"]

    def wait_for_completion(self, prompt_id: str, poll_interval: float = 1.0) -> ComfyUIResult:
        """
        Wait for prompt execution to complete.
        Example: result = client.wait_for_completion(prompt_id) to poll until done
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > self.timeout:
                return ComfyUIResult(
                    prompt_id=prompt_id,
                    status="timeout",
                    error=f"Execution timeout after {self.timeout}s",
                    execution_time=elapsed,
                )

            try:
                history = self.get_history(prompt_id)
                if prompt_id in history:
                    entry = history[prompt_id]
                    status = entry.get("status", {})

                    if status.get("status_str") == "error":
                        return ComfyUIResult(
                            prompt_id=prompt_id,
                            status="error",
                            error=json.dumps(status.get("messages", [])),
                            execution_time=elapsed,
                        )

                    if status.get("completed", False) or "outputs" in entry:
                        return ComfyUIResult(
                            prompt_id=prompt_id,
                            status="success",
                            outputs=entry.get("outputs", {}),
                            execution_time=elapsed,
                        )
            except requests.RequestException as e:
                return ComfyUIResult(
                    prompt_id=prompt_id,
                    status="error",
                    error=str(e),
                    execution_time=elapsed,
                )

            time.sleep(poll_interval)

    def execute(self, workflow: dict[str, Any]) -> ComfyUIResult:
        """
        Queue workflow and wait for completion.
        Example: result = client.execute(workflow_dict) to run workflow synchronously
        """
        try:
            prompt_id = self.queue_prompt(workflow)
            return self.wait_for_completion(prompt_id)
        except requests.RequestException as e:
            return ComfyUIResult(
                prompt_id="",
                status="error",
                error=str(e),
            )

    def interrupt(self) -> bool:
        """Interrupt current execution."""
        try:
            resp = requests.post(self._url("/interrupt"), timeout=10, auth=self.auth)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def clear_queue(self) -> bool:
        """Clear the execution queue."""
        try:
            resp = requests.post(
                self._url("/queue"),
                json={"clear": True},
                timeout=10,
                auth=self.auth,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_object_info(self, node_type: str | None = None) -> dict[str, Any]:
        """Get node type information."""
        path = f"/object_info/{node_type}" if node_type else "/object_info"
        resp = requests.get(self._url(path), timeout=30, auth=self.auth)
        resp.raise_for_status()
        return resp.json()
