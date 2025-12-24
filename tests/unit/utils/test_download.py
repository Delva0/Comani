"""
Tests for comani.utils.download module.

Tests download utilities and downloader implementations.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import pytest
import requests


class TestBaseDownloader:
    """Test BaseDownloader abstract class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_base_downloader_validate_and_prepare_new_file(self, temp_dir):
        """validate_and_prepare should allow download for new files."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "new_file.bin"

        with patch("comani.utils.download.get_url_size") as mock_size:
            mock_size.return_value = 1000

            existing, total, should_download = downloader.validate_and_prepare(
                out_path, "https://example.com/file.bin", None, 0
            )

            assert existing == 0
            assert total == 1000
            assert should_download is True

    def test_base_downloader_validate_and_prepare_complete_file(self, temp_dir):
        """validate_and_prepare should skip complete files."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "complete.bin"
        out_path.write_bytes(b"x" * 1000)

        existing, total, should_download = downloader.validate_and_prepare(
            out_path, "https://example.com/file.bin", None, 1000
        )

        assert existing == 1000
        assert total == 1000
        assert should_download is False

    def test_base_downloader_validate_and_prepare_corrupted_html(self, temp_dir):
        """validate_and_prepare should delete corrupted HTML files."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "corrupted.bin"
        out_path.write_bytes(b"<!DOCTYPE html>error page")

        with patch("comani.utils.download.get_url_size") as mock_size:
            mock_size.return_value = 1000

            existing, total, should_download = downloader.validate_and_prepare(
                out_path, "https://example.com/file.bin", None, 0
            )

            assert existing == 0
            # should_download is True because we deleted the HTML file and need to re-download
            assert should_download is True
            assert not out_path.exists()

    def test_base_downloader_validate_and_prepare_oversized(self, temp_dir):
        """validate_and_prepare should delete oversized files."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "oversized.bin"
        out_path.write_bytes(b"x" * 2000)

        existing, total, should_download = downloader.validate_and_prepare(
            out_path, "https://example.com/file.bin", None, 1000
        )

        assert existing == 0
        assert should_download is True
        assert not out_path.exists()


class TestRequestsDownloader:
    """Test RequestsDownloader implementation."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_requests_downloader_download_file_success(self, temp_dir):
        """download_file should download file successfully."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "downloaded.bin"

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "10"}
        mock_response.iter_content.return_value = [b"0123456789"]
        mock_response.raise_for_status = Mock()
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch("requests.get") as mock_get:
            mock_get.return_value = mock_response

            with patch("comani.utils.download.get_url_size") as mock_size:
                mock_size.return_value = 10

                result = downloader.download_file(
                    "https://example.com/file.bin",
                    out_path,
                )

                assert result is True
                assert out_path.exists()
                assert out_path.stat().st_size == 10

    def test_requests_downloader_download_file_skip_complete(self, temp_dir):
        """download_file should skip already complete files."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "complete.bin"
        out_path.write_bytes(b"content123")

        result = downloader.download_file(
            "https://example.com/file.bin",
            out_path,
            total_size=10,
        )

        assert result is True

    def test_requests_downloader_download_file_failure(self, temp_dir):
        """download_file should return False on failure."""
        from comani.utils.download import RequestsDownloader

        downloader = RequestsDownloader()
        out_path = temp_dir / "failed.bin"

        with patch("requests.get") as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")

            with patch("comani.utils.download.get_url_size") as mock_size:
                mock_size.return_value = 100

                result = downloader.download_file(
                    "https://example.com/file.bin",
                    out_path,
                )

                assert result is False


class TestAria2Downloader:
    """Test Aria2Downloader implementation."""

    @pytest.fixture
    def mock_node(self):
        return MagicMock()

    @pytest.fixture
    def downloader(self, mock_node):
        from comani.utils.download import Aria2Downloader
        return Aria2Downloader(mock_node)

    def test_aria2_downloader_file_exists(self, downloader, mock_node):
        from comani.utils.connection.node import ExecResult
        mock_node.exec_shell.return_value = ExecResult("", "", 0)
        assert downloader.file_exists(Path("/test/file")) is True
        mock_node.exec_shell.assert_called_with('test -f "/test/file"')

    def test_aria2_downloader_file_size(self, downloader, mock_node):
        # Implementation currently returns 0 with a TODO
        assert downloader.file_size(Path("/test/file")) == 0

    def test_aria2_downloader_delete_file(self, downloader, mock_node):
        downloader.delete_file(Path("/test/file"))
        mock_node.exec_shell.assert_called_with('rm -f "/test/file" ＆& rm -f "/test/file.aria2"')

    def test_aria2_downloader_mkdir(self, downloader, mock_node):
        downloader.mkdir(Path("/test/dir"))
        mock_node.exec_shell.assert_called_with('mkdir -p "/test/dir"')

    def test_aria2_downloader_download_file_success(self, downloader, mock_node):
        from comani.utils.connection.node import ExecResult

        # Mock validate_and_prepare to return should_download=True
        with patch.object(downloader, 'validate_and_prepare', return_value=(0, 1000, True)):
            # Mock file_size to return 1000 for the final check
            with patch.object(downloader, 'file_size', return_value=1000):
                # Mock initial aria2c start
                mock_node.exec_shell.side_effect = [
                    ExecResult("", "", 0),  # mkdir
                    ExecResult("12345\n", "", 0),  # nohup aria2c ... echo $! (PID)
                    ExecResult("", "", 1),  # ps -p 12345 (not running after first poll to end loop)
                    ExecResult("[#123456 1000B/1000B(100%)]\n", "", 0),  # tail -n 1 log
                    ExecResult(b"\x00", "", 0), # read_file_header (not HTML)
                    ExecResult("", "", 0),  # rm -f log
                ]

                # We need to mock base64.b64decode for read_file_header if we don't mock the whole method
                with patch("base64.b64decode", return_value=b"not html"):
                    with patch("time.sleep", return_value=None):
                        result = downloader.download_file(
                            "https://example.com/file.bin",
                            Path("/tmp/file.bin"),
                            total_size=1000
                        )

                assert result is True
            # Check if aria2c was started
            start_cmd = mock_node.exec_shell.call_args_list[1][0][0]
            assert "aria2c" in start_cmd
            assert "--dir=\"/tmp\"" in start_cmd
            assert "--out=\"file.bin\"" in start_cmd


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
