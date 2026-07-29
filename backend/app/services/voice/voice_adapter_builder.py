"""Build voice adapter from application settings."""

import logging

from app.core.config import get_settings
from app.services.voice.fallback_adapter import VoiceProviderFallbackAdapter

logger = logging.getLogger(__name__)


def build_voice_adapter() -> VoiceProviderFallbackAdapter:
    """
    Build voice adapter from application settings.

    Reads provider priority from config and creates fallback adapter.
    """
    settings = get_settings()

    # Parse provider priority from config
    provider_names = [
        name.strip() for name in settings.voice_provider_priority.split(",") if name.strip()
    ]

    if not provider_names:
        provider_names = ["elevenlabs", "cartesia", "deepgram", "coqui_xtts"]
        logger.warning(f"No provider priority configured, using default: {provider_names}")

    # Build provider configs
    provider_configs = []

    for name in provider_names:
        if name == "elevenlabs":
            if settings.elevenlabs_api_key:
                provider_configs.append(
                    {
                        "name": "elevenlabs",
                        "config": {
                            "api_key": settings.elevenlabs_api_key,
                            "model_id": settings.elevenlabs_model_id,
                        },
                    }
                )
            else:
                logger.info("ElevenLabs API key not configured, skipping")

        elif name == "cartesia":
            if settings.cartesia_api_key:
                provider_configs.append(
                    {
                        "name": "cartesia",
                        "config": {
                            "api_key": settings.cartesia_api_key,
                            "model_id": settings.cartesia_model_id,
                        },
                    }
                )
            else:
                logger.info("Cartesia API key not configured, skipping")

        elif name == "deepgram":
            if settings.deepgram_api_key:
                provider_configs.append(
                    {
                        "name": "deepgram",
                        "config": {
                            "api_key": settings.deepgram_api_key,
                            "model": settings.deepgram_model,
                        },
                    }
                )
            else:
                logger.info("Deepgram API key not configured, skipping")

        elif name == "nvidia":
            if settings.nvidia_api_key:
                provider_configs.append(
                    {
                        "name": "nvidia",
                        "config": {
                            "api_key": settings.nvidia_api_key,
                            "model": settings.nvidia_model,
                        },
                    }
                )
            else:
                logger.info("NVIDIA API key not configured, skipping")

        elif name == "coqui":
            provider_configs.append({"name": "coqui", "config": {}})

        elif name == "coqui_xtts":
            provider_configs.append({"name": "coqui_xtts", "config": {}})

        else:
            logger.warning(f"Unknown provider in priority list: {name}")

    if not provider_configs:
        # Fallback to Coqui XTTS (offline)
        logger.warning("No API keys configured, falling back to local Coqui XTTS")
        provider_configs.append({"name": "coqui_xtts", "config": {}})

    logger.info(
        f"Building voice adapter with {len(provider_configs)} providers: "
        f"{[c['name'] for c in provider_configs]}"
    )

    return VoiceProviderFallbackAdapter(provider_configs)


# Global adapter instance (lazy loaded)
_voice_adapter: VoiceProviderFallbackAdapter | None = None


def get_voice_adapter() -> VoiceProviderFallbackAdapter:
    """Get or create global voice adapter instance."""
    global _voice_adapter

    if _voice_adapter is None:
        _voice_adapter = build_voice_adapter()

    return _voice_adapter


def reset_voice_adapter() -> None:
    """Reset global voice adapter (useful for testing or config changes)."""
    global _voice_adapter
    _voice_adapter = None
