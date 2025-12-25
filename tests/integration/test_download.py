import pytest
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file at the module level
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv() # Try default

from comani.utils.download import Aria2Downloader, get_url_size  # noqa: E402
from comani.utils.connection.node import connect_node  # noqa: E402
from comani.config import get_config  # noqa: E402

def test_run_real_civitai_download():
    """
    Functional test for downloading from Civitai to a remote server.
    Requires COMANI_HOST, COMANI_SSH_USER, etc. to be set in .env or environment.
    """
    config = get_config()

    # Skip if no remote host is configured
    if not config.host or config.host in ("localhost", "127.0.0.1"):
        pytest.skip(f"COMANI_HOST ({config.host}) not set to a remote server, skipping real download test")

    # Real Civitai model URL
    url = "https://civitai-delivery-worker-prod.5ac0637cfd0766c97916cefa3764fbdf.r2.cloudflarestorage.com/model/182697/anikawaxlV2.WPaQ.safetensors?X-Amz-Expires=86400&response-content-disposition=attachment%3B%20filename%3D%22anikawaxl_v2.safetensors%22&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=e01358d793ad6966166af8b3064953ad/20251224/us-east-1/s3/aws4_request&X-Amz-Date=20251224T124450Z&X-Amz-SignedHeaders=host&X-Amz-Signature=2b547a16b08049bfefa7a638367897aad6a9bf398bbf38f90748b9967e5f9e5f"

    # Pre-signed URLs should not include Authorization headers as they are self-authenticating
    headers = {}
    if "X-Amz-Algorithm" not in url:
        api_token = os.getenv("CIVITAI_API_TOKEN") or (config.civitai_api_token.get_secret_value() if config.civitai_api_token else None)
        if api_token:
            headers["Authorization"] = f"Bearer {api_token}"

    # Remote path to download to
    remote_path = Path("/tmp/anikawaxl_v2.safetensors")

    with connect_node(
        host=config.host,
        ssh_user=config.user,
        ssh_port=config.port,
        ssh_password=config.password.get_secret_value() if config.password else None
    ) as node:
        # Check for aria2c and install if missing
        if not node.exec_shell("aria2c --version").ok:
            print("aria2c not found, attempting to install...")
            node.exec_shell("apt-get update && apt-get install -y aria2")
            if not node.exec_shell("aria2c --version").ok:
                pytest.fail("Error: Failed to install aria2c on remote node")

        downloader = Aria2Downloader(node)

        # 1. Get URL size first (optional but good for validation)
        print(f"Fetching URL size for {url}...")
        size = get_url_size(url, headers=headers)
        print(f"URL Size: {size} bytes")

        # 2. Perform download
        print(f"Starting download to {remote_path}...")
        success = downloader.download_file(url, remote_path, headers=headers, total_size=size)

        assert success, "Error: Download failed"
        assert downloader.file_exists(remote_path), f"Error: File {remote_path} does not exist after download"

        actual_size = downloader.file_size(remote_path)
        print(f"Downloaded size: {actual_size} bytes")

        if size > 0:
            assert actual_size == size, f"Error: Size mismatch. Expected {size}, got {actual_size}"

        # 3. Verify it's not HTML
        assert not downloader.is_html_file(remote_path), f"Error: Downloaded file {remote_path} is an HTML file"

        # Cleanup
        print(f"Cleaning up {remote_path}...")
        downloader.delete_file(remote_path)
        if downloader.file_exists(remote_path):
            print(f"Warning: Failed to delete {remote_path}")
        else:
            print("Cleanup successful")

    print("Test passed successfully!")
