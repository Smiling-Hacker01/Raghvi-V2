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

    # JWT / Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # AI Provider
    ai_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    openai_timeout_seconds: int = 15
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: int = 15
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_timeout_seconds: int = 15
    open_router_api_key: str = ""
    open_router_model: str = "openai/gpt-4o-mini"
    open_router_timeout_seconds: int = 15
    hugging_face_api_key: str = ""
    hugging_face_model: str = "microsoft/Phi-3-mini-4k-instruct"
    hugging_face_timeout_seconds: int = 30
    github_token: str = ""
    github_model: str = "gpt-4o"
    github_timeout_seconds: int = 15


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Cache is created once per app startup.
    To reload settings (e.g., in tests), call get_settings.cache_clear()
    """
    return Settings()
