"""
ComfyUI WebSocket/HTTP client for remote communication.
"""

import json
import uuid
import time
import socket
import logging
from typing import Any
from dataclasses import dataclass
from urllib.parse import urljoin, urlencode

import requests
import websocket
from comani.config import get_config

logger = logging.getLogger(__name__)


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
        timeout: int = 600,  # Increased default timeout
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

    def _ws_url(self) -> str:
        ws_base = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
        return f"{ws_base}/ws?clientId={self.client_id}"

    def get_file(self, filename: str, subfolder: str = "", folder_type: str = "output") -> bytes:
        """Download a file from ComfyUI."""
        params = {
            "filename": filename,
            "subfolder": subfolder,
            "type": folder_type
        }
        url = f"{self._url('/view')}?{urlencode(params)}"
        resp = requests.get(url, timeout=30, auth=self.auth)
        resp.raise_for_status()
        return resp.content

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
        logger.debug("Queuing prompt to %s", self._url("/prompt"))
        resp = requests.post(
            self._url("/prompt"),
            json=payload,
            timeout=30,
            auth=self.auth,
        )
        if resp.status_code == 400:
            try:
                error_data = resp.json()
                node_errors = error_data.get("node_errors", {})
                if node_errors:
                    logger.error("ComfyUI Prompt Validation Failed (400):")
                    for node_id, node_error in node_errors.items():
                        class_type = node_error.get("class_type", "Unknown")
                        errors = node_error.get("errors", [])
                        for err in errors:
                            message = err.get("message", "No message")
                            details = err.get("details", "")
                            logger.error(f"  - Node {node_id} ({class_type}): {message}. {details}")
                else:
                    logger.error("400 Bad Request: %s", resp.text)
            except Exception:
                logger.error("400 Bad Request (failed to parse error JSON): %s", resp.text)

        resp.raise_for_status()
        data = resp.json()
        prompt_id = data["prompt_id"]
        logger.debug("Prompt queued successfully, prompt_id: %s", prompt_id)
        return prompt_id

    def wait_for_completion(
        self,
        prompt_id: str,
        poll_interval: float = 1.0,
        progress_callback: Any | None = None,
        ws: websocket.WebSocket | None = None,
    ) -> ComfyUIResult:
        """
        Wait for prompt execution to complete using WebSocket for real-time updates.
        """
        start_time = time.time()

        # If ws is not provided, try to connect
        if ws is None:
            ws_url = self._ws_url()

            # Prepare auth headers for WebSocket
            headers = []
            if self.auth:
                import base64
                auth_str = f"{self.auth[0]}:{self.auth[1]}"
                auth_b64 = base64.b64encode(auth_str.encode()).decode()
                headers.append(f"Authorization: Basic {auth_b64}")

            logger.debug("Connecting to WebSocket: %s", ws_url)
            try:
                ws = websocket.create_connection(ws_url, timeout=self.timeout, header=headers)
                logger.debug("WebSocket connected")
            except Exception as e:
                logger.error("Failed to connect to WebSocket: %s. Falling back to polling.", e)
                return self._wait_for_completion_polling(prompt_id, poll_interval)

        try:
            # Check history immediately in case it finished instantly (e.g. cached)
            logger.debug("Checking history for prompt %s (pre-check)", prompt_id)
            history = self.get_history(prompt_id)
            if prompt_id in history:
                logger.debug("Prompt %s found in history immediately (cached)", prompt_id)
                if progress_callback:
                    progress_callback("cached", {"prompt_id": prompt_id})
                return self._get_final_result(prompt_id, start_time)

            logger.debug("Waiting for completion of prompt %s", prompt_id)
            last_check_time = time.time()
            while True:
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    logger.error("Execution timeout after %ds", self.timeout)
                    return ComfyUIResult(
                        prompt_id=prompt_id,
                        status="timeout",
                        error=f"Execution timeout after {self.timeout}s",
                        execution_time=elapsed,
                    )

                # Periodically check history even if no WS messages received
                if time.time() - last_check_time > 5.0:
                    history = self.get_history(prompt_id)
                    if prompt_id in history:
                        logger.debug("Prompt %s found in history during loop", prompt_id)
                        break
                    last_check_time = time.time()

                try:
                    ws.settimeout(1.0)
                    out = ws.recv()
                    if not out:
                        continue
                    if isinstance(out, bytes):
                        # Binary message (e.g. preview image), skip
                        continue
                    message = json.loads(out)
                except (websocket.WebSocketTimeoutException, socket.timeout):
                    continue
                except Exception as e:
                    logger.error("WebSocket error during recv: %s", e)
                    break

                msg_type = message.get("type")
                data = message.get("data", {})
                msg_prompt_id = data.get("prompt_id")

                if msg_type != "status":
                    logger.debug("Received WebSocket message: type=%s, msg_prompt_id=%s, target_prompt_id=%s",
                                 msg_type, msg_prompt_id, prompt_id)

                # If prompt_id is missing from message, we assume it's ours if it came through our clientId-bound WS
                is_our_prompt = (msg_prompt_id == prompt_id) or (msg_prompt_id is None)

                if msg_type == "status":
                    # Status update
                    pass
                elif msg_type == "executing":
                    node_id = data.get("node")
                    if node_id is not None:
                        logger.debug("Node executing: %s", node_id)

                    if is_our_prompt:
                        if progress_callback:
                            progress_callback("executing", data)
                        if node_id is None:
                            logger.debug("Execution finished (received executing with node=None)")
                            break
                elif msg_type == "progress":
                    if is_our_prompt:
                        logger.debug("Progress: %s/%s for node %s", data.get('value'), data.get('max'), data.get('node'))
                        if progress_callback:
                            progress_callback("progress", data)
                elif msg_type == "cached":
                    if is_our_prompt and progress_callback:
                        progress_callback("cached", data)
                elif msg_type == "executed":
                    if is_our_prompt and progress_callback:
                        progress_callback("executed", data)

            logger.debug("Fetching final result for prompt %s", prompt_id)
            # Once WebSocket loop breaks (finished), get the final result from history
            return self._get_final_result(prompt_id, start_time)

        finally:
            ws.close()
            logger.debug("WebSocket closed")

    def _get_final_result(self, prompt_id: str, start_time: float) -> ComfyUIResult:
        """Fetch final result from history after execution completion."""
        elapsed = time.time() - start_time
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

                return ComfyUIResult(
                    prompt_id=prompt_id,
                    status="success",
                    outputs=entry.get("outputs", {}),
                    execution_time=elapsed,
                )
        except Exception as e:
            return ComfyUIResult(
                prompt_id=prompt_id,
                status="error",
                error=f"Failed to fetch history: {e}",
                execution_time=elapsed,
            )

        return ComfyUIResult(
            prompt_id=prompt_id,
            status="error",
            error="Prompt not found in history after completion",
            execution_time=elapsed,
        )

    def _wait_for_completion_polling(self, prompt_id: str, poll_interval: float = 1.0) -> ComfyUIResult:
        """Original polling-based wait_for_completion."""
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
                    return self._get_final_result(prompt_id, start_time)
            except requests.RequestException:
                pass

            time.sleep(poll_interval)

    def execute(self, workflow: dict[str, Any], progress_callback: Any | None = None) -> ComfyUIResult:
        """
        Queue workflow and wait for completion.
        """
        ws = None
        try:
            # 1. Connect WebSocket FIRST to avoid missing initial messages (e.g. cached/executing)
            ws_url = self._ws_url()
            headers = []
            if self.auth:
                import base64
                auth_str = f"{self.auth[0]}:{self.auth[1]}"
                auth_b64 = base64.b64encode(auth_str.encode()).decode()
                headers.append(f"Authorization: Basic {auth_b64}")

            try:
                ws = websocket.create_connection(ws_url, timeout=self.timeout, header=headers)
                logger.debug("WebSocket connected pre-queue")
            except Exception as e:
                logger.warning("Failed to connect to WebSocket pre-queue: %s. Will retry or poll.", e)

            # 2. Queue prompt
            prompt_id = self.queue_prompt(workflow)

            # 3. Wait for completion using the already opened WS
            return self.wait_for_completion(prompt_id, progress_callback=progress_callback, ws=ws)
        except requests.RequestException as e:
            if ws:
                ws.close()
            return ComfyUIResult(
                prompt_id="",
                status="error",
                error=str(e),
            )
        except Exception as e:
            if ws:
                ws.close()
            raise e

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
