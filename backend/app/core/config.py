from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables.

    database_url has no default on purpose: if it's missing, the app
    should fail loudly at startup rather than run in a half-configured
    state.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str = "dev-only-change-me-please-use-a-real-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 10
    refresh_token_expire_days: int = 14


@lru_cache
def get_settings() -> Settings:
    return Settings()
