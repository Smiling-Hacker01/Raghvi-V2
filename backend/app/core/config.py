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

    # Stripe configuration
    stripe_api_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    
    # Voice provider configuration
    elevenlabs_api_key: str = ""
    elevenlabs_model_id: str = "eleven_monolingual_v1"

    cartesia_api_key: str = ""
    cartesia_model_id: str = "sonic-english"

    deepgram_api_key: str = ""
    deepgram_model: str = "aura-asteria-en"

    nvidia_api_key: str = ""
    nvidia_model: str = "fastpitch"

    # Voice provider priority (comma-separated, will try in order)
    voice_provider_priority: str = "elevenlabs,cartesia,deepgram,coqui_xtts"
    
    # Voice synthesis settings
    voice_sample_rate: int = 44100
    voice_bit_depth: int = 16
    voice_channels: int = 1
    voice_format: str = "wav"
    
    # Voice limits
    voice_clone_min_duration: int = 45
    voice_clone_max_duration: int = 120
    voice_clone_max_file_size: int = 20 * 1024 * 1024
    
    # S3/AWS configuration (for voice samples)
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_voice_prefix: str = "voices/"
    
    # Redis cache
    redis_voice_cache_ttl: int = 30 * 60  # 30 minutes


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance.

    Cache is created once per app startup.
    To reload settings (e.g., in tests), call get_settings.cache_clear()
    """
    return Settings()
