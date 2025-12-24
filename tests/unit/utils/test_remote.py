"""
Tests for comani.utils.remote module.

Tests SSH tunnel and connection infrastructure.
"""

import socket
from unittest.mock import Mock, patch

import pytest


class TestSSHTunnel:
    """Test SSHTunnel class."""

    @pytest.fixture
    def mock_ssh_client(self):
        """Create a mock SSH client."""
        mock_client = Mock()
        mock_transport = Mock()
        mock_client.get_transport.return_value = mock_transport
        return mock_client

    @pytest.fixture
    def mock_channel(self):
        """Create a mock SSH channel."""
        mock_ch = Mock()
        mock_ch.recv.return_value = b""  # Return empty to signal closed
        return mock_ch

    def test_tunnel_binds_to_free_port(self, mock_ssh_client):
        """Tunnel should bind to an available local port."""
        from comani.utils.connection.ssh import SSHTunnel

        with patch.object(SSHTunnel, "_start"):
            tunnel = SSHTunnel.__new__(SSHTunnel)
            tunnel._ssh = mock_ssh_client
            tunnel._remote_host = "127.0.0.1"
            tunnel._remote_port = 6800
            tunnel._running = False
            tunnel._thread = None
            tunnel._client_threads = []

            # Create server socket manually to test port binding
            tunnel._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tunnel._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tunnel._server_socket.bind(("127.0.0.1", 0))
            tunnel._local_port = tunnel._server_socket.getsockname()[1]
            tunnel._server_socket.close()

            assert tunnel._local_port > 0
            assert tunnel._local_port < 65536

    def test_tunnel_local_bind_port_property(self, mock_ssh_client):
        """local_bind_port should return the bound port."""
        from comani.utils.connection.ssh import SSHTunnel

        with patch.object(SSHTunnel, "_start"):
            tunnel = SSHTunnel.__new__(SSHTunnel)
            tunnel._local_port = 12345

            assert tunnel.local_bind_port == 12345

    def test_tunnel_is_running_property(self, mock_ssh_client):
        """is_running should return tunnel state."""
        from comani.utils.connection.ssh import SSHTunnel

        with patch.object(SSHTunnel, "_start"):
            tunnel = SSHTunnel.__new__(SSHTunnel)

            tunnel._running = True
            assert tunnel.is_running is True

            tunnel._running = False
            assert tunnel.is_running is False

    def test_tunnel_stop_cleans_up(self, mock_ssh_client):
        """stop() should clean up resources."""
        from comani.utils.connection.ssh import SSHTunnel

        with patch.object(SSHTunnel, "_start"):
            tunnel = SSHTunnel.__new__(SSHTunnel)
            tunnel._running = True
            mock_socket = Mock()
            mock_thread = Mock()
            mock_thread.is_alive.return_value = False
            tunnel._server_socket = mock_socket
            tunnel._thread = mock_thread
            tunnel._client_threads = []

            tunnel.stop()

            assert tunnel._running is False
            mock_socket.close.assert_called_once()
            mock_thread.join.assert_called_once()

    def test_tunnel_context_manager(self, mock_ssh_client):
        """Tunnel should work as context manager."""
        from comani.utils.connection.ssh import SSHTunnel

        with patch.object(SSHTunnel, "_start"):
            with patch.object(SSHTunnel, "stop") as mock_stop:
                tunnel = SSHTunnel.__new__(SSHTunnel)
                tunnel._running = False
                tunnel._server_socket = None
                tunnel._thread = None
                tunnel._client_threads = []

                with tunnel:
                    pass

                mock_stop.assert_called_once()


class TestSSHConnection:
    """Test SSHConnection class."""

    @pytest.fixture
    def mock_paramiko(self):
        """Mock paramiko module."""
        with patch.dict("sys.modules", {"paramiko": Mock()}):
            import sys
            mock = sys.modules["paramiko"]
            mock_client = Mock()
            mock_sftp = Mock()
            mock_client.open_sftp.return_value = mock_sftp
            mock_client.get_transport.return_value = Mock()
            mock.SSHClient.return_value = mock_client
            mock.AutoAddPolicy.return_value = Mock()
            yield mock

    def test_connection_init(self):
        """SSHConnection should initialize with correct defaults."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")

        assert conn.host == "test.host"
        assert conn.port == 22
        assert conn.user == "root"
        assert conn.timeout == 30

    def test_connection_init_custom_params(self):
        """SSHConnection should accept custom parameters."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection(
            host="custom.host",
            port=2222,
            user="testuser",
            timeout=60,
        )

        assert conn.host == "custom.host"
        assert conn.port == 2222
        assert conn.user == "testuser"
        assert conn.timeout == 60

    def test_connection_is_connected_false_initially(self):
        """is_connected should be False before connect()."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")
        assert conn.is_connected is False

    def test_connection_client_raises_if_not_connected(self):
        """client property should raise if not connected."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")

        with pytest.raises(RuntimeError) as exc_info:
            _ = conn.client

        assert "Not connected" in str(exc_info.value)

    def test_connection_sftp_raises_if_not_connected(self):
        """sftp property should raise if not connected."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")

        with pytest.raises(RuntimeError) as exc_info:
            _ = conn.sftp

        assert "Not connected" in str(exc_info.value)

    def test_connection_connect(self, mock_paramiko):
        """connect() should establish SSH connection."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")
        conn.connect()

        mock_paramiko.SSHClient.assert_called_once()
        mock_client = mock_paramiko.SSHClient.return_value
        mock_client.set_missing_host_key_policy.assert_called_once()
        mock_client.connect.assert_called_once()
        mock_client.open_sftp.assert_called_once()

    def test_connection_connect_idempotent(self, mock_paramiko):
        """connect() should be idempotent."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")
        conn.connect()
        conn.connect()  # Second call should do nothing

        # Should only be called once
        assert mock_paramiko.SSHClient.call_count == 1

    def test_connection_close(self, mock_paramiko):
        """close() should clean up resources."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")
        conn.connect()
        conn.close()

        mock_client = mock_paramiko.SSHClient.return_value
        mock_sftp = mock_client.open_sftp.return_value

        mock_sftp.close.assert_called_once()
        mock_client.close.assert_called_once()

    def test_connection_context_manager(self, mock_paramiko):
        """SSHConnection should work as context manager."""
        from comani.utils.connection.ssh import SSHConnection

        with SSHConnection("test.host") as conn:
            assert conn._ssh is not None

        mock_paramiko.SSHClient.return_value.close.assert_called_once()

    def test_connection_exec(self, mock_paramiko):
        """exec() should execute command and return results."""
        from comani.utils.connection.ssh import SSHConnection

        mock_client = mock_paramiko.SSHClient.return_value
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b"output"
        mock_stderr.read.return_value = b""
        mock_stdout.channel.recv_exit_status.return_value = 0
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        conn = SSHConnection("test.host")
        conn.connect()
        out, err, code = conn.exec("ls -la")

        assert out == "output"
        assert err == ""
        assert code == 0

    def test_connection_exec_raises_on_failure(self, mock_paramiko):
        """exec() should raise on non-zero exit code when check=True."""
        from comani.utils.connection.ssh import SSHConnection

        mock_client = mock_paramiko.SSHClient.return_value
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"error message"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        conn = SSHConnection("test.host")
        conn.connect()

        with pytest.raises(RuntimeError) as exc_info:
            conn.exec("failing_command")

        assert "Command failed" in str(exc_info.value)

    def test_connection_exec_no_raise_when_check_false(self, mock_paramiko):
        """exec() should not raise when check=False."""
        from comani.utils.connection.ssh import SSHConnection

        mock_client = mock_paramiko.SSHClient.return_value
        mock_stdout = Mock()
        mock_stderr = Mock()
        mock_stdout.read.return_value = b""
        mock_stderr.read.return_value = b"error message"
        mock_stdout.channel.recv_exit_status.return_value = 1
        mock_client.exec_command.return_value = (None, mock_stdout, mock_stderr)

        conn = SSHConnection("test.host")
        conn.connect()

        out, err, code = conn.exec("failing_command", check=False)

        assert code == 1
        assert err == "error message"

    def test_connection_create_tunnel(self, mock_paramiko):
        """create_tunnel() should create SSHTunnel instance."""
        from comani.utils.connection.ssh import SSHConnection, SSHTunnel

        with patch.object(SSHTunnel, "__init__", return_value=None) as mock_init:
            conn = SSHConnection("test.host")
            conn.connect()

            conn.create_tunnel("127.0.0.1", 6800)

            mock_init.assert_called_once()

    def test_connection_create_tunnel_raises_if_not_connected(self):
        """create_tunnel() should raise if not connected."""
        from comani.utils.connection.ssh import SSHConnection

        conn = SSHConnection("test.host")

        with pytest.raises(RuntimeError) as exc_info:
            conn.create_tunnel("127.0.0.1", 6800)

        assert "Not connected" in str(exc_info.value)


class TestRemoteFileOperations:
    """Test remote file operation utility functions."""

    @pytest.fixture
    def mock_sftp(self):
        """Create a mock SFTP client."""
        return Mock()

    def test_remote_file_exists_true(self, mock_sftp):
        """remote_file_exists should return True for existing files."""
        from comani.utils.connection.ssh import remote_file_exists

        mock_sftp.stat.return_value = Mock()

        assert remote_file_exists(mock_sftp, "/path/to/file") is True

    def test_remote_file_exists_false(self, mock_sftp):
        """remote_file_exists should return False for non-existing files."""
        from comani.utils.connection.ssh import remote_file_exists

        mock_sftp.stat.side_effect = FileNotFoundError()

        assert remote_file_exists(mock_sftp, "/path/to/nonexistent") is False

    def test_remote_file_size(self, mock_sftp):
        """remote_file_size should return file size."""
        from comani.utils.connection.ssh import remote_file_size

        mock_stat = Mock()
        mock_stat.st_size = 12345
        mock_sftp.stat.return_value = mock_stat

        assert remote_file_size(mock_sftp, "/path/to/file") == 12345

    def test_remote_file_size_not_exists(self, mock_sftp):
        """remote_file_size should return 0 for non-existing files."""
        from comani.utils.connection.ssh import remote_file_size

        mock_sftp.stat.side_effect = FileNotFoundError()

        assert remote_file_size(mock_sftp, "/path/to/nonexistent") == 0

    def test_remote_read_header(self, mock_sftp):
        """remote_read_header should read first N bytes."""
        from comani.utils.connection.ssh import remote_read_header

        mock_file = Mock()
        mock_file.read.return_value = b"<!DOCTYPE html>"
        mock_sftp.open.return_value.__enter__ = Mock(return_value=mock_file)
        mock_sftp.open.return_value.__exit__ = Mock(return_value=False)

        result = remote_read_header(mock_sftp, "/path/to/file", 50)

        assert result == b"<!DOCTYPE html>"
        mock_file.read.assert_called_once_with(50)

    def test_remote_delete_file(self, mock_sftp):
        """remote_delete_file should delete file."""
        from comani.utils.connection.ssh import remote_delete_file

        remote_delete_file(mock_sftp, "/path/to/file")

        mock_sftp.remove.assert_called_once_with("/path/to/file")

    def test_remote_delete_file_not_exists(self, mock_sftp):
        """remote_delete_file should not raise for non-existing files."""
        from comani.utils.connection.ssh import remote_delete_file

        mock_sftp.remove.side_effect = FileNotFoundError()

        # Should not raise
        remote_delete_file(mock_sftp, "/path/to/nonexistent")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
