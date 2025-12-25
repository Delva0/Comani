import pytest
from unittest.mock import Mock, patch
from comani.utils.connection.ssh import SSHConnection, SSHConnectionManager

class TestSSHConnectionManager:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton instance and connections before each test."""
        SSHConnectionManager._instance = None
        SSHConnectionManager._connections = {}
        yield

    @pytest.fixture
    def mock_paramiko(self):
        """Mock paramiko module."""
        with patch.dict("sys.modules", {"paramiko": Mock()}):
            import sys
            mock = sys.modules["paramiko"]
            mock_client = Mock()
            mock_sftp = Mock()
            mock_transport = Mock()

            mock_client.open_sftp.return_value = mock_sftp
            mock_client.get_transport.return_value = mock_transport
            mock_transport.is_active.return_value = True

            mock.SSHClient.return_value = mock_client
            mock.AutoAddPolicy.return_value = Mock()
            yield mock

    def test_singleton(self):
        """SSHConnectionManager should be a singleton."""
        manager1 = SSHConnectionManager()
        manager2 = SSHConnectionManager()
        assert manager1 is manager2

    def test_get_connection_reuse(self, mock_paramiko):
        """Manager should reuse active connections."""
        manager = SSHConnectionManager()

        conn1 = manager.get_connection("test.host", user="root")
        conn2 = manager.get_connection("test.host", user="root")

        assert conn1 is conn2
        assert mock_paramiko.SSHClient.call_count == 1

    def test_get_connection_different_keys(self, mock_paramiko):
        """Manager should create different connections for different hosts/users."""
        manager = SSHConnectionManager()

        conn1 = manager.get_connection("host1", user="root")
        conn2 = manager.get_connection("host2", user="root")
        conn3 = manager.get_connection("host1", user="other")

        assert conn1 is not conn2
        assert conn1 is not conn3
        assert conn2 is not conn3
        assert mock_paramiko.SSHClient.call_count == 3

    def test_reconnect_if_dead(self, mock_paramiko):
        """Manager should reconnect if the cached connection is dead."""
        manager = SSHConnectionManager()

        # 1. Create first connection
        conn1 = manager.get_connection("test.host")
        assert conn1.is_connected is True

        # 2. Simulate connection death
        mock_client = mock_paramiko.SSHClient.return_value
        mock_client.get_transport.return_value.is_active.return_value = False
        assert conn1.is_connected is False

        # 3. Get connection again - should trigger reconnect
        # Reset call count to see new calls
        mock_paramiko.SSHClient.reset_mock()

        conn2 = manager.get_connection("test.host")

        assert conn1 is conn2
        # connect() should have been called again on the same object
        assert mock_paramiko.SSHClient.call_count == 1

    def test_close_all(self, mock_paramiko):
        """close_all should close all managed connections."""
        manager = SSHConnectionManager()
        conn1 = manager.get_connection("host1")
        conn2 = manager.get_connection("host2")

        manager.close_all()

        assert len(manager._connections) == 0
        assert conn1._ssh is None
        assert conn2._ssh is None

class TestSSHConnectionIsConnected:
    def test_is_connected_checks_transport_active(self):
        """is_connected should check if transport is active."""
        conn = SSHConnection("test.host")
        mock_ssh = Mock()
        conn._ssh = mock_ssh

        mock_transport = Mock()
        mock_ssh.get_transport.return_value = mock_transport

        mock_transport.is_active.return_value = True
        assert conn.is_connected is True

        mock_transport.is_active.return_value = False
        assert conn.is_connected is False

        mock_ssh.get_transport.return_value = None
        assert conn.is_connected is False
