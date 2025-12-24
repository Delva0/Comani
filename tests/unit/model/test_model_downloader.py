"""
Tests for comani.model.download module.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def clear_config():
    """Clear the cached config singleton before each test."""
    import comani.config
    comani.config._config = None
    yield
    comani.config._config = None


class TestModelDownloaderCore:
    """Test core functionality of ModelDownloader."""

    @pytest.fixture
    def mock_downloader(self):
        downloader = Mock()
        downloader.download_file = Mock(return_value=True)
        downloader.mkdir = Mock()
        downloader.close = Mock()
        return downloader

    def test_model_downloader_init(self, mock_downloader):
        from comani.model.download import ModelDownloader
        dl = ModelDownloader(mock_downloader, "/tmp")
        assert dl._downloader is mock_downloader
        assert str(dl._base_path) == "/tmp"

    def test_model_downloader_create(self):
        from comani.model.download import ModelDownloader
        from comani.utils.download import RequestsDownloader
        from comani.utils.connection.node import ExecResult

        mock_node = Mock()
        mock_node.exec_shell.return_value = ExecResult(stdout="", stderr="", code=1)

        with patch("comani.utils.download.connect_node", return_value=mock_node):
            with patch("comani.utils.download.is_remote_mode", return_value=False):
                from comani.utils.download import get_downloader
                get_downloader.cache_clear()
                dl = ModelDownloader.create(base_path="/tmp")
                assert isinstance(dl._downloader, RequestsDownloader)
                assert str(dl._base_path) == "/tmp"

    def test_model_downloader_close(self, mock_downloader):
        from comani.model.download import ModelDownloader
        dl = ModelDownloader(mock_downloader, "/tmp")
        dl.close()
        mock_downloader.close.assert_called_once()


class TestModelDownloaderIntegration:
    """High-level integration tests for ModelDownloader."""

    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "models").mkdir()
            yield tmp_path

    def test_download_boleromix_illustrious(self, temp_dir, monkeypatch):
        """Test downloading boleromix_illustrious using high-level API."""
        from comani.model.download import ModelDownloader
        from comani.model.model_pack import ModelPackRegistry

        # Mock config and environment
        monkeypatch.setenv("COMANI_HOST", "127.0.0.1")
        monkeypatch.setenv("COMANI_COMFYUI_DIR", str(temp_dir))

        # Create a mock registry with boleromix_illustrious
        config_data = {
            "models": {
                "boleromix_illustrious": {
                    "url": "https://civitai.com/models/869634?modelVersionId=1412789",
                    "path": "models/checkpoints/boleromix_illustrious.safetensors"
                }
            }
        }
        registry = ModelPackRegistry(temp_dir)
        registry.load_from_dict(config_data, ".sdxl")

        mock_downloader = Mock()
        mock_downloader.download_file = Mock(return_value=True)
        mock_downloader.mkdir = Mock()
        mock_downloader.close = Mock()

        # We need to mock resolve_download because it calls external APIs (Civitai)
        from comani.model.download import ResolvedDownloadItem
        resolved_item = ResolvedDownloadItem(
            url="https://civitai.com/api/download/models/1412789",
            filepath="boleromix_illustrious.safetensors",
            headers={"Authorization": "Bearer fake_token"}
        )

        with patch("comani.model.download.resolve_download", return_value=resolved_item):
            dl = ModelDownloader(mock_downloader, temp_dir)
            # Use dot-prefixed module name to match new registry behavior
            result = dl.download_by_ids([".sdxl.boleromix_illustrious"], registry)

            assert result is True
            mock_downloader.mkdir.assert_called()
            mock_downloader.download_file.assert_called_once()

            # Verify call arguments
            args, kwargs = mock_downloader.download_file.call_args
            assert args[0] == resolved_item.url
            assert str(args[1]).endswith("boleromix_illustrious.safetensors")
            assert args[2] == resolved_item.headers

    def test_get_downloader_selection(self, monkeypatch):
        """Test that get_downloader selects the right implementation."""
        from comani.utils.download import get_downloader, Aria2Downloader, RequestsDownloader
        from comani.utils.connection.node import ExecResult

        # Test Local Aria2
        monkeypatch.setenv("COMANI_HOST", "127.0.0.1")
        mock_node_local = Mock()
        mock_node_local.host = "localhost"
        mock_node_local.exec_shell.return_value = ExecResult(stdout="", stderr="", code=0)
        with patch("comani.utils.download.connect_node", return_value=mock_node_local):
            get_downloader.cache_clear()
            dl = get_downloader()
            assert isinstance(dl, Aria2Downloader)
            assert dl.node.host == "localhost"

        # Test Remote Aria2
        monkeypatch.setenv("COMANI_HOST", "remote.host")
        mock_node_remote = Mock()
        mock_node_remote.host = "remote.host"
        mock_node_remote.exec_shell.return_value = ExecResult(stdout="", stderr="", code=0)
        with patch("comani.utils.download.connect_node", return_value=mock_node_remote):
            get_downloader.cache_clear()
            dl = get_downloader()
            assert isinstance(dl, Aria2Downloader)
            assert dl.node.host == "remote.host"

        # Test Fallback
        mock_node_fallback = Mock()
        mock_node_fallback.exec_shell.return_value = ExecResult(stdout="", stderr="", code=1)
        with patch("comani.utils.download.connect_node", return_value=mock_node_fallback):
            with patch("comani.utils.download.is_remote_mode", return_value=False):
                get_downloader.cache_clear()
                dl = get_downloader()
                assert isinstance(dl, RequestsDownloader)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
