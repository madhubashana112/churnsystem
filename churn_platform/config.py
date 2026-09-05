"""
Runtime settings, read from the environment.

Values that were previously module-level constants scattered across the API
layer live here, so a deployment can tune them without a code change.
"""
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="api_key.env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Entities scored per model call batch. Sequential, to respect rate limits.
    batch_size: int = 10

    # Cap on entities scored in one run. The model path costs a call per batch,
    # so it is capped far lower than the local engine, which is free.
    max_entities: int = 20
    max_entities_local: int = 200

    # auto  — try Qwen, fall back to the local engine when it is unavailable
    # qwen  — Qwen only; surface errors rather than falling back
    # local — never call the model
    churn_engine: Literal["auto", "qwen", "local"] = "auto"

    # Seconds to stop retrying Qwen after a failure.
    qwen_cooldown_seconds: int = 120

    @property
    def qwen_mode(self) -> str:
        """Legacy alias used by the plan's naming."""
        return self.churn_engine


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached accessor, so the environment is read once per process."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
