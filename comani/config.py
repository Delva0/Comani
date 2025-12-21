"""
Configuration management for Comani engine.
"""

import os
import shutil
from pathlib import Path
from dataclasses import dataclass, field


def get_default_dir(name: str) -> Path:
    """Get default directory path under comani package."""
    return Path(__file__).parent / name


@dataclass
class ComaniConfig:
    """Engine configuration loaded from environment variables."""

    server_ip: str = field(default_factory=lambda: os.getenv("COMANI_SERVER_IP", "127.0.0.1"))
    server_port: int = field(default_factory=lambda: int(os.getenv("COMANI_SERVER_PORT", "8188")))

    model_config_dir: Path = field(default_factory=lambda: Path(
        os.getenv("COMANI_MODEL_CONFIG_DIR", str(get_default_dir("models")))
    ))
    workflow_dir: Path = field(default_factory=lambda: Path(
        os.getenv("COMANI_WORKFLOW_DIR", str(get_default_dir("workflows")))
    ))
    preset_dir: Path = field(default_factory=lambda: Path(
        os.getenv("COMANI_PRESET_DIR", str(get_default_dir("presets")))
    ))

    def __post_init__(self):
        self.model_config_dir = Path(self.model_config_dir)
        self.workflow_dir = Path(self.workflow_dir)
        self.preset_dir = Path(self.preset_dir)

    @property
    def comfyui_url(self) -> str:
        return f"http://{self.server_ip}:{self.server_port}"

    def ensure_directories(self) -> None:
        """Ensure all directories exist, copy defaults if needed."""
        default_dirs = {
            "models": get_default_dir("models"),
            "workflows": get_default_dir("workflows"),
            "presets": get_default_dir("presets"),
        }

        for name, (target, default) in [
            ("models", (self.model_config_dir, default_dirs["models"])),
            ("workflows", (self.workflow_dir, default_dirs["workflows"])),
            ("presets", (self.preset_dir, default_dirs["presets"])),
        ]:
            if target != default and not target.exists():
                target.mkdir(parents=True, exist_ok=True)
                if default.exists():
                    for item in default.iterdir():
                        dest = target / item.name
                        if item.is_file():
                            shutil.copy2(item, dest)
                        elif item.is_dir():
                            shutil.copytree(item, dest)
                print(f"Copied default {name} to {target}")
            elif not target.exists():
                target.mkdir(parents=True, exist_ok=True)


_config: ComaniConfig | None = None


def get_config() -> ComaniConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = ComaniConfig()
    return _config


def init_config() -> ComaniConfig:
    """Initialize config and ensure directories exist."""
    config = get_config()
    config.ensure_directories()
    return config
