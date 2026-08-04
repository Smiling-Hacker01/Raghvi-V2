"""Tests for AIProviderRegistry."""

import os
from unittest.mock import patch

import pytest

from app.services.ai.adapter import AIProviderAdapter
from app.services.ai.registry import AIProviderRegistry


class DummyAdapter(AIProviderAdapter):
    def validate_config(self) -> bool:
        return True

    def get_model_info(self) -> dict:
        return {"model": "dummy"}

    async def send_message(self, messages, system_prompt, max_tokens=2000, temperature=0.7):
        return ("dummy response", 5)


def test_ai_provider_registry_register_and_get():
    AIProviderRegistry.reset()
    AIProviderRegistry.register("dummy", DummyAdapter)

    with patch.dict(os.environ, {"AI_PROVIDER": "dummy"}):
        adapter = AIProviderRegistry.get_adapter()
        assert isinstance(adapter, DummyAdapter)
        # Verify singleton caching behavior
        adapter2 = AIProviderRegistry.get_adapter()
        assert adapter is adapter2

    AIProviderRegistry.reset()


def test_ai_provider_registry_unknown_provider():
    AIProviderRegistry.reset()
    with (
        patch.dict(os.environ, {"AI_PROVIDER": "unknown_provider_xyz"}),
        pytest.raises(ValueError, match="Unknown AI provider"),
    ):
        AIProviderRegistry.get_adapter()
    AIProviderRegistry.reset()
