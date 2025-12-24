import requests
from unittest.mock import patch
from comani.core.client import ComfyUIClient

class TestComfyUIClient:
    """Tests for ComfyUIClient."""

    @patch("requests.get")
    def test_health_check(self, mock_get):
        """Test health check logic."""
        client = ComfyUIClient("http://localhost:8188")

        # Success case
        mock_get.return_value.status_code = 200
        assert client.health_check() is True

        # Failure case
        mock_get.return_value.status_code = 404
        assert client.health_check() is False

        # Exception case
        mock_get.side_effect = requests.RequestException("Connection error")
        assert client.health_check() is False

    @patch("requests.post")
    def test_queue_prompt(self, mock_post):
        """Test queuing a prompt."""
        client = ComfyUIClient("http://localhost:8188")
        mock_post.return_value.json.return_value = {"prompt_id": "test-id"}
        mock_post.return_value.status_code = 200

        prompt_id = client.queue_prompt({"test": "workflow"})
        assert prompt_id == "test-id"

        # Verify call arguments
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["prompt"] == {"test": "workflow"}
        assert "client_id" in kwargs["json"]

    @patch("requests.get")
    def test_get_history(self, mock_get):
        """Test getting history."""
        client = ComfyUIClient("http://localhost:8188")
        mock_get.return_value.json.return_value = {"test-id": {"status": "done"}}

        history = client.get_history("test-id")
        assert history == {"test-id": {"status": "done"}}
        assert "/history/test-id" in mock_get.call_args[0][0]
