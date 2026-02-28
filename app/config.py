"""Runtime configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings.

    Attributes
    ----------
    app_name : str
        Human-readable application name.
    database_url : str
        SQLAlchemy database URL.
    master_key_path : Path
        Local file containing the envelope master key.
    default_checkout_ttl_seconds : int
        Default checkout TTL when a client omits the field.
    bootstrap_enabled : bool
        Whether one-time unauthenticated bootstrap is allowed.
    """

    model_config = SettingsConfigDict(env_prefix="AGENT_KEY_", extra="ignore")

    app_name: str = "Agent Key"
    database_url: str = "sqlite+aiosqlite:///./agent_key.db"
    master_key_path: Path = Field(default=Path(".agent_key_master.key"))
    default_checkout_ttl_seconds: int = 3600
    bootstrap_enabled: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings.

    Returns
    -------
    Settings
        Cached settings instance.
    """
    return Settings()
