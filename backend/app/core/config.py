from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Database
    database_url: str

    # AI Provider
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: int = 15
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 15


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Cache is created once per app startup.
    To reload settings (e.g., in tests), call get_settings.cache_clear()
    """
    return Settings()
