"""
Configuration management for Comani engine using Pydantic Settings.
"""

from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ComaniConfig(BaseSettings):
    """Engine configuration loaded from environment variables."""

    # Remote Server Configuration (SSH)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=22, validation_alias=AliasChoices("COMANI_SSH_PORT", "SSH_PORT"))
    user: str = Field(default="root", validation_alias=AliasChoices("COMANI_SSH_USER", "SSH_USER"))
    password: SecretStr | None = Field(default=None, validation_alias=AliasChoices("COMANI_SSH_PASS", "SSH_PASS"))
    ssh_key: str | None = Field(default=None, validation_alias=AliasChoices("COMANI_SSH_KEY", "SSH_KEY"))

    # ComfyUI Configuration
    comfyui_port: int = Field(default=8188)
    comfyui_auth_user: str | None = Field(default=None)
    comfyui_auth_pass: SecretStr | None = Field(default=None)
    comfyui_root: Path = Field(default_factory=Path.cwd, validation_alias=AliasChoices("COMANI_COMFYUI_DIR", "comfyui_root"))

    # Comani Directory Configs
    examples_dir: Path = Path(__file__).parent.parent / "examples"
    model_dir: Path | None = Field(default=examples_dir / "models", validation_alias=AliasChoices("COMANI_MODEL_DIR", "model_dir"))
    workflow_dir: Path | None = Field(default=examples_dir / "workflows", validation_alias=AliasChoices("COMANI_WORKFLOW_DIR", "workflow_dir"))
    preset_dir: Path | None = Field(default=examples_dir / "presets", validation_alias=AliasChoices("COMANI_PRESET_DIR", "preset_dir"))
    output_dir: Path = Field(default=Path.cwd() / "outputs", validation_alias=AliasChoices("COMANI_OUTPUT_DIR", "output_dir"))

    # API Keys (No COMANI_ prefix in env usually, but we support both)
    xai_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("XAI_API_KEY", "COMANI_XAI_API_KEY"))
    civitai_api_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("CIVITAI_API_TOKEN", "COMANI_CIVITAI_API_TOKEN")
    )
    hf_api_token: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("HF_API_TOKEN", "HF_TOKEN", "COMANI_HF_API_TOKEN")
    )

    model_config = SettingsConfigDict(
        env_prefix="COMANI_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("comfyui_root", mode="before")
    @classmethod
    def convert_to_path(cls, v: Any) -> Path:
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v

    @property
    def comfyui_url(self) -> str:
        """Get ComfyUI server URL."""
        return f"http://{self.host}:{self.comfyui_port}"

    @property
    def auth(self) -> tuple[str, str] | None:
        """Get ComfyUI auth credentials if set."""
        if self.comfyui_auth_user and self.comfyui_auth_pass:
            return (self.comfyui_auth_user, self.comfyui_auth_pass.get_secret_value())
        return None

_config: ComaniConfig | None = None


def get_config() -> ComaniConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = ComaniConfig()
    return _config
