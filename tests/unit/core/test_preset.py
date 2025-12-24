import yaml
from comani.core.preset import Preset, PresetManager

class TestPreset:
    """Tests for Preset dataclass and factory methods."""

    def test_from_dict(self):
        """Test creating preset from dictionary."""
        data = {
            "name": "test-preset",
            "base_workflow": "test-wf",
            "params": {"p1": "v1"},
            "mapping": {
                "p1": {"node_id": "10", "field_path": "inputs.text"}
            }
        }
        preset = Preset.from_dict(data)
        assert preset.name == "test-preset"
        assert preset.base_workflow == "test-wf"
        assert preset.params == {"p1": "v1"}
        assert preset.mapping["p1"].node_id == "10"
        assert preset.mapping["p1"].field_path == "inputs.text"

class TestPresetManager:
    """Tests for PresetManager."""

    def test_list_presets(self, tmp_path):
        """Test listing presets from directory."""
        # Create dummy preset files
        (tmp_path / "p1.yml").write_text("base_workflow: wf1")
        (tmp_path / "p2.yaml").write_text("base_workflow: wf2")
        (tmp_path / "not_a_preset.txt").write_text("ignore me")
        
        manager = PresetManager(tmp_path)
        presets = manager.list_presets()
        assert presets == ["p1", "p2"]

    def test_get_preset(self, tmp_path):
        """Test getting and caching presets."""
        path = tmp_path / "test.yml"
        data = {
            "name": "test",
            "base_workflow": "wf",
            "params": {"a": 1},
            "mapping": {"a": {"node_id": 1, "field_path": "x"}}
        }
        path.write_text(yaml.dump(data))
        
        manager = PresetManager(tmp_path)
        preset = manager.get("test")
        assert preset.name == "test"
        assert "test" in manager._cache
        
        # Test cache hit
        preset2 = manager.get("test")
        assert preset is preset2
