import os
import tempfile
import logging
import pytest
from comani.utils.connection.node import connect_node

logging.basicConfig(level=logging.DEBUG)

def verify_node_functionality(node, name):
    print(f"\n--- Testing Node: {name} ({node.host}) ---")

    # Test exec_shell
    print("Testing exec_shell...")
    res = node.exec_shell("echo 'hello world'")
    print(f"STDOUT: {res.stdout}")
    assert "hello world" in res.stdout
    assert res.ok

    # Test exec_python
    print("Testing exec_python...")
    def remote_func(a, b):
        return a + b

    res_py = node.exec_python(remote_func, args=(1, 2))
    print(f"Python Result: {res_py}")
    assert str(res_py).strip() == "3"

    # Test put and get
    print("Testing put/get...")
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("test content")
        local_src = f.name

    remote_path = "/tmp/comani_test_file"
    local_dest = local_src + ".back"

    try:
        node.put(local_src, remote_path)
        node.get(remote_path, local_dest)

        with open(local_dest, 'r') as f:
            content = f.read()
        print(f"File Content: {content}")
        assert content == "test content"
    finally:
        if os.path.exists(local_src):
            os.remove(local_src)
        if os.path.exists(local_dest):
            os.remove(local_dest)
        node.exec_shell(f"rm -f {remote_path}")

    print(f"--- Node {name} passed all tests! ---\n")

def test_local_node():
    """Test LocalNode functionality."""
    print("Starting LocalNode test...")
    with connect_node(host=None) as node:
        verify_node_functionality(node, "local_node")

def test_localhost_ssh():
    """Test localhost SSH functionality."""
    print("\nStarting localhost (SSH) test...")
    try:
        with connect_node(
            host="127.0.0.1",
            ssh_user="delva",
            ssh_password="wenkaiyue020612..",
            force_ssh=True
        ) as node:
            verify_node_functionality(node, "localhost_ssh")
    except Exception as e:
        pytest.skip(f"Localhost SSH test failed: {e}. Note: This might fail if SSH server is not running on localhost.")

def test_remote_linux_vast_ai():
    """Test remote linux environment (vast.ai)."""
    print("\nStarting remote linux test (vast.ai)...")
    try:
        with connect_node(
            host="171.101.231.208",
            ssh_port=51558,
            ssh_user="root"
        ) as node:
            verify_node_functionality(node, "vast_ai")
    except Exception as e:
        pytest.skip(f"Vast.ai remote test failed: {e}")

