import pytest
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from comani.model.model_pack import ModelPackRegistry  # noqa: E402
from comani.model.model_downloader import ModelDownloader  # noqa: E402
from comani.config import get_config  # noqa: E402

def test_download_anikawaxl_v2_with_cleanup():
    """
    Functional test to download a specific model and then clean up.
    """
    config = get_config()

    # Skip if no remote host is configured
    if not config.host or config.host in ("localhost", "127.0.0.1"):
        pytest.skip(f"COMANI_HOST ({config.host}) not set to a remote server, skipping real download model test")

    base_dir = Path(__file__).parent.parent.parent
    models_dir = base_dir / "examples/models"
    registry = ModelPackRegistry(models_dir)

    downloader = ModelDownloader.create(base_path=config.comfyui_root)

    model_id = "anikawaxl_v2"

    print(f"\n🚀 Starting download for model: {model_id}")
    success = downloader.download_by_ids([model_id], registry)

    assert success is True, f"❌ Failed to download model: {model_id}"

    model_def = registry.get_model(model_id)
    assert model_def is not None, f"❌ Model definition for {model_id} not found"

    target_path = Path(model_def.path)
    if not target_path.is_absolute():
        target_path = config.comfyui_root / target_path

    print(f"✅ Download verified at: {target_path}")

    if hasattr(downloader, "_downloader"):
        exists = downloader._downloader.file_exists(target_path)
        assert exists, f"❌ Downloaded file not found at {target_path}"

        print(f"🧹 Cleaning up: deleting {target_path}")
        downloader._downloader.delete_file(target_path)

        still_exists = downloader._downloader.file_exists(target_path)
        assert not still_exists, f"❌ Cleanup failed: file still exists at {target_path}"
        print("✅ Cleanup successful")
