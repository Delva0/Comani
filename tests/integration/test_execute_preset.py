import pytest
import logging
from dotenv import load_dotenv
from comani.core.engine import ComaniEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()

def test_execute_anikawa_preset():
    """
    Integration test for executing the anikawa/anikawaxl_girl_2.yml preset.
    This corresponds to: source .env && comani execute anikawa/anikawaxl_girl_2.yml
    """
    # Initialize engine
    # ComaniEngine will use the global config which loads from .env
    engine = ComaniEngine()

    # 1. Check health to ensure ComfyUI is reachable
    health = engine.health_check()
    logger.info(f"Health check: {health}")
    assert health["comfyui"] == "ok", f"ComfyUI is not reachable at {health['comfyui_url']}"

    # 2. Execute preset
    # The preset name is relative to the preset_dir (examples/presets)
    preset_name = "anikawa/anikawaxl_girl_2.yml"
    logger.info(f"Executing preset: {preset_name}")

    try:
        result = engine.execute_workflow_by_name(preset_name=preset_name)

        # 3. Verify results
        logger.info(f"Prompt ID: {result.prompt_id}")
        logger.info(f"Status: {result.status}")
        logger.info(f"Execution time: {result.execution_time:.2f}s")

        assert result.error is None, f"Execution failed with error: {result.error}"
        assert result.prompt_id is not None
        assert result.status == "success"

        if result.outputs:
            logger.info("Outputs found:")
            for node_id, node_output in result.outputs.items():
                logger.info(f"  Node {node_id}: {node_output}")
        else:
            logger.info("No outputs found (this might be expected depending on the workflow)")

    except Exception as e:
        pytest.fail(f"Integration test failed with exception: {e}")

if __name__ == "__main__":
    # If run as a script, execute the test
    test_execute_anikawa_preset()
