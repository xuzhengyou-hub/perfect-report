from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Perfect Report Backend"
    data_root: Path = Field(default_factory=lambda: Path("data/workspaces"))
    cleanup_delay_seconds: int = 1800
    qwen_model: str = "qwen-max"
    qwen_vision_model: str = "qwen-vl-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_api_key: str | None = None


settings = Settings()
