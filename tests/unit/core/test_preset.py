import yaml
import pytest
from comani.core.preset import Preset, PresetManager, ParamMapping

class TestPreset:
    """Tests for Preset dataclass and factory methods."""

    def test_from_dict(self):
        """Test creating preset from dictionary."""
        data = {
            "name": "test-preset",
            "workflow": "test-wf",
            "params": {"p1": "v1"},
            "mapping": {
                "p1": {"node_id": "10", "field_path": "inputs.text"}
            }
        }
        preset = Preset.from_dict(data)
        assert preset.name == "test-preset"
        assert preset.workflow == "test-wf"
        assert preset.params == {"p1": "v1"}
        assert preset.mapping["p1"][0].node_id == "10"
        assert preset.mapping["p1"][0].field_path == "inputs.text"

    def test_from_dict_with_objects(self):
        """Test from_dict with already instantiated ParamMapping objects."""
        mapping = {"p1": [ParamMapping(node_id="1", field_path="path")]}
        data = {
            "name": "test",
            "workflow": "wf",
            "mapping": mapping
        }
        preset = Preset.from_dict(data)
        assert preset.mapping["p1"] == mapping["p1"]

    def test_from_dict_string_mapping(self):
        """Test from_dict with string mapping format 'node:field'."""
        data = {
            "name": "test",
            "workflow": "wf",
            "mapping": {
                "p1": "10:inputs.text",
                "p2": ["20:field1", "30:field2"]
            }
        }
        preset = Preset.from_dict(data)
        assert preset.mapping["p1"][0].node_id == "10"
        assert preset.mapping["p1"][0].field_path == "inputs.text"
        assert preset.mapping["p2"][0].node_id == "20"
        assert preset.mapping["p2"][0].field_path == "field1"
        assert preset.mapping["p2"][1].node_id == "30"
        assert preset.mapping["p2"][1].field_path == "field2"

    def test_from_dict_missing_workflow(self):
        """Test that from_dict raises error if workflow is missing."""
        with pytest.raises(ValueError, match="workflow is required"):
            Preset.from_dict({"name": "test"})

class TestPresetManager:
    """Tests for PresetManager."""

    def test_list_presets(self, tmp_path):
        """Test listing presets from directory."""
        # Create dummy preset files
        (tmp_path / "p1.yml").write_text("workflow: wf1")
        (tmp_path / "p2.yaml").write_text("workflow: wf2")
        (tmp_path / "not_a_preset.txt").write_text("ignore me")

        manager = PresetManager(tmp_path)
        presets = manager.list_presets()
        assert presets == ["p1.yml", "p2.yaml"]

    def test_get_preset(self, tmp_path):
        """Test getting and caching presets."""
        path = tmp_path / "test.yml"
        data = {
            "name": "test",
            "workflow": "wf",
            "params": {"a": 1},
            "mapping": {"a": {"node_id": 1, "field_path": "x"}}
        }
        path.write_text(yaml.dump(data))

        manager = PresetManager(tmp_path)
        preset = manager.get("test.yml")
        assert preset.name == "test"
        assert "test.yml" in manager._cache

        # Test cache hit
        preset2 = manager.get("test.yml")
        assert preset is preset2

    def test_inheritance_single(self, tmp_path):
        """Test single inheritance level."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "base_wf",
            "params": {"a": 1, "b": 2},
            "dependencies": ["d1"]
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"],
            "params": {"b": 3, "c": 4},
            "dependencies": ["d2"]
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("child.yml")

        assert child.workflow == "base_wf"
        assert child.params == {"a": 1, "b": 3, "c": 4}
        assert child.dependencies == ["d1", "d2"]

    def test_inheritance_multiple(self, tmp_path):
        """Test multiple inheritance (bases: [A, B])."""
        (tmp_path / "base_a.yml").write_text(yaml.dump({
            "workflow": "wf_a",
            "params": {"a": 1, "shared": "a"},
            "dependencies": ["dep_a"]
        }))
        (tmp_path / "base_b.yml").write_text(yaml.dump({
            "workflow": "wf_b",
            "params": {"b": 2, "shared": "b"},
            "dependencies": ["dep_b"]
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["base_a.yml", "base_b.yml"],
            "params": {"c": 3}
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("child.yml")

        # Last base (base_b) should override previous (base_a)
        assert child.workflow == "wf_b"
        assert child.params == {"a": 1, "b": 2, "shared": "b", "c": 3}
        assert child.dependencies == ["dep_a", "dep_b"]

    def test_inheritance_nested(self, tmp_path):
        """Test deep inheritance (A -> B -> C)."""
        (tmp_path / "grandparent.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"p": "gp"}
        }))
        (tmp_path / "parent.yml").write_text(yaml.dump({
            "bases": ["grandparent.yml"],
            "params": {"p": "p"}
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["parent.yml"],
            "params": {"p": "c"}
        }))

        manager = PresetManager(tmp_path)
        assert manager.get("child.yml").params["p"] == "c"
        assert manager.get("parent.yml").params["p"] == "p"
        assert manager.get("grandparent.yml").params["p"] == "gp"

    def test_circular_dependency(self, tmp_path):
        """Test that circular dependencies raise RecursionError."""
        (tmp_path / "a.yml").write_text("bases: [b.yml]\nworkflow: wf")
        (tmp_path / "b.yml").write_text("bases: [a.yml]\nworkflow: wf")

        manager = PresetManager(tmp_path)
        with pytest.raises(RecursionError, match="Circular dependency detected"):
            manager.get("a.yml")

    def test_list_deduplication(self, tmp_path):
        """Test that list fields (dependencies) are deduplicated while keeping order."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "dependencies": ["a", "b", "c"]
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"],
            "dependencies": ["b", "d", "a"]
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("child.yml")
        # a, b, c from base; then b, d, a from child.
        # deduplicated: a, b, c, d
        assert child.dependencies == ["a", "b", "c", "d"]

    def test_mapping_override(self, tmp_path):
        """Test that mapping dictionaries are merged correctly."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "mapping": {
                "p1": {"node_id": "1", "field_path": "f1"},
                "p2": {"node_id": "2", "field_path": "f2"}
            }
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"],
            "mapping": {
                "p2": {"node_id": "22", "field_path": "f22"},
                "p3": {"node_id": "3", "field_path": "f3"}
            }
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("child.yml")
        assert child.mapping["p1"][0].node_id == "1"
        assert child.mapping["p2"][0].node_id == "22"
        assert child.mapping["p3"][0].node_id == "3"

    def test_inheritance_with_extension(self, tmp_path):
        """Test inheritance when base name includes .yml extension."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "base_wf",
            "params": {"a": 1}
        }))
        (tmp_path / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"],
            "params": {"b": 2}
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("child.yml")
        assert child.params == {"a": 1, "b": 2}
        assert child.workflow == "base_wf"

    def test_missing_base_raises_error(self, tmp_path):
        """Test that missing parent preset raises FileNotFoundError."""
        (tmp_path / "child.yml").write_text("bases: [nonexistent.yml]\nworkflow: wf")
        manager = PresetManager(tmp_path)
        with pytest.raises(FileNotFoundError, match="Preset 'nonexistent.yml' not found"):
            manager.get("child.yml")

    def test_default_name_from_filename(self, tmp_path):
        """Test that name defaults to filename if not provided in YAML."""
        (tmp_path / "no_name.yml").write_text("workflow: wf")
        manager = PresetManager(tmp_path)
        preset = manager.get("no_name.yml")
        assert preset.name == "no_name.yml"

    def test_inheritance_across_directories(self, tmp_path):
        """Test inheritance across subdirectories (3 -> 2 -> 1)."""
        dir1 = tmp_path / "folder1"
        dir2 = tmp_path / "folder2"
        dir1.mkdir()
        dir2.mkdir()

        # 1. folder1/anikawaxl_girl_2.yml inherits anikawaxl_girl.yml
        (tmp_path / "anikawaxl_girl.yml").write_text(yaml.dump({
            "workflow": "base_wf",
            "params": {"v1": 1, "v2": 1, "v3": 1}
        }))

        (dir1 / "anikawaxl_girl_2.yml").write_text(yaml.dump({
            "bases": ["anikawaxl_girl.yml"],
            "params": {"v2": 2}
        }))

        # 2. folder2/anikawaxl_girl_3.yml inherits folder1/anikawaxl_girl_2.yml
        (dir2 / "anikawaxl_girl_3.yml").write_text(yaml.dump({
            "bases": ["folder1/anikawaxl_girl_2.yml"],
            "params": {"v3": 3}
        }))

        manager = PresetManager(tmp_path)

        # Load the deepest one
        p3 = manager.get("folder2/anikawaxl_girl_3.yml")

        assert p3.params["v1"] == 1  # From root
        assert p3.params["v2"] == 2  # Overwritten by 2
        assert p3.params["v3"] == 3  # Overwritten by 3
        assert p3.workflow == "base_wf"
        assert p3.name == "folder2/anikawaxl_girl_3.yml"

    def test_inheritance_relative_no_prefix(self, tmp_path):
        """Test inheritance using relative path without ./ prefix."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"a": 1}
        }))
        (sub / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"],
            "params": {"b": 2}
        }))

        manager = PresetManager(tmp_path)
        # Should find base.yml in sub/ even without ./ prefix because it's in context_dir
        child = manager.get("sub/child.yml")
        assert child.params == {"a": 1, "b": 2}

    def test_inheritance_priority(self, tmp_path):
        """Test that context_dir has priority over preset_dir."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"location": "global"}
        }))
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"location": "local"}
        }))
        (sub / "child.yml").write_text(yaml.dump({
            "bases": ["base.yml"]
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("sub/child.yml")
        # Should pick 'local' from sub/base.yml
        assert child.params["location"] == "local"

    def test_inheritance_relative_dot_slash(self, tmp_path):
        """Test inheritance using ./ relative path."""
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"a": 1}
        }))
        (sub / "child.yml").write_text(yaml.dump({
            "bases": ["./base.yml"],
            "params": {"b": 2}
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("sub/child.yml")
        assert child.params == {"a": 1, "b": 2}

    def test_inheritance_relative_dot_dot_slash(self, tmp_path):
        """Test inheritance using ../ relative path."""
        (tmp_path / "base.yml").write_text(yaml.dump({
            "workflow": "wf",
            "params": {"a": 1}
        }))
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "child.yml").write_text(yaml.dump({
            "bases": ["../base.yml"],
            "params": {"b": 2}
        }))

        manager = PresetManager(tmp_path)
        child = manager.get("sub/child.yml")
        assert child.params == {"a": 1, "b": 2}
