import pytest
from unittest.mock import Mock, patch
from comani.utils.connection.node import RemoteNode
from comani.utils.connection.ssh import SSHConnectionManager

class TestRemoteNode:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset the singleton instance and connections before each test."""
        SSHConnectionManager._instance = None
        SSHConnectionManager._connections = {}
        yield

    @pytest.fixture
    def mock_manager(self):
        with patch("comani.utils.connection.node.SSHConnectionManager") as mock:
            instance = mock.return_value
            mock_conn = Mock()
            instance.get_connection.return_value = mock_conn
            yield instance, mock_conn

    def test_remote_node_init_uses_manager(self, mock_manager):
        """RemoteNode should use SSHConnectionManager to get its connection."""
        instance, mock_conn = mock_manager
        
        node = RemoteNode("test.host", "root", 22)
        
        instance.get_connection.assert_called_once_with(
            host="test.host",
            port=22,
            user="root",
            key_path=None,
            password=None
        )
        assert node.conn is mock_conn
        mock_conn.exec.assert_called_once() # mkdir -p /tmp/comani_node_exec

    def test_remote_node_close_does_not_close_connection(self, mock_manager):
        """RemoteNode.close() should not close the underlying SSH connection."""
        instance, mock_conn = mock_manager
        
        node = RemoteNode("test.host", "root", 22)
        node.close()
        
        assert mock_conn.close.call_count == 0
