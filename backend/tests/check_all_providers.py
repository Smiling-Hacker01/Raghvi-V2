#!/usr/bin/env python3
"""Test script to verify all AI provider adapters work correctly.

This is a standalone script, not a pytest test.
Run with: uv run python tests/test_all_providers.py
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings


async def test_provider(provider_name: str, adapter_class):
    """Test a single provider."""
    print(f"\n🧪 Testing {provider_name}...")
    try:
        adapter = adapter_class()

        # Validate configuration
        await adapter.validate_config()
        print("   ✅ Configuration valid")

        # Get model info
        info = adapter.get_model_info()
        print(f"   📋 Model: {info['model_name']}")
        print(f"   📋 Provider: {info['provider']}")

        # Test API call
        response, tokens = await adapter.send_message(
            messages=[{"role": "user", "content": "Say 'hello' and nothing else"}],
            system_prompt="You are a helpful assistant. Keep responses very short.",
            max_tokens=20,
            temperature=0.5,
        )

        print("   ✅ API call successful!")
        print(f"   📝 Response: {response[:100]}")
        print(f"   🔢 Tokens used: {tokens}")
        return True

    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower():
            print(f"   ⚠️  Rate limit or quota exceeded: {str(e)[:150]}")
        elif "401" in err_str or "invalid" in err_str.lower() or "auth" in err_str.lower():
            print(f"   ❌ Authentication failed: {str(e)[:150]}")
        else:
            print(f"   ❌ Error: {str(e)[:150]}")
        return False


async def main():
    """Test all configured providers."""
    print("=" * 70)
    print("🧪 Testing All AI Provider Adapters")
    print("=" * 70)

    settings = get_settings()
    print(f"\n📋 Primary Provider: {settings.ai_provider}")

    results = {}

    # Test OpenAI
    if settings.openai_api_key:
        from app.services.ai.providers.openai import OpenAIAdapter

        results["openai"] = await test_provider("OpenAI", OpenAIAdapter)
    else:
        print("\n⏭️  Skipping OpenAI (no API key)")
        results["openai"] = None

    # Test Gemini
    if settings.gemini_api_key:
        from app.services.ai.providers.gemini import GeminiAdapter

        results["gemini"] = await test_provider("Gemini", GeminiAdapter)
    else:
        print("\n⏭️  Skipping Gemini (no API key)")
        results["gemini"] = None

    # Test Groq
    if settings.groq_api_key:
        from app.services.ai.providers.groq import GroqAdapter

        results["groq"] = await test_provider("Groq", GroqAdapter)
    else:
        print("\n⏭️  Skipping Groq (no API key)")
        results["groq"] = None

    # Test OpenRouter
    if settings.open_router_api_key:
        from app.services.ai.providers.openrouter import OpenRouterAdapter

        results["openrouter"] = await test_provider("OpenRouter", OpenRouterAdapter)
    else:
        print("\n⏭️  Skipping OpenRouter (no API key)")
        results["openrouter"] = None

    # Test HuggingFace
    if settings.hugging_face_api_key:
        from app.services.ai.providers.huggingface import HuggingFaceAdapter

        results["huggingface"] = await test_provider("HuggingFace", HuggingFaceAdapter)
    else:
        print("\n⏭️  Skipping HuggingFace (no API key)")
        results["huggingface"] = None

    # Test GitHub Models
    if settings.github_token:
        from app.services.ai.providers.github import GitHubModelsAdapter

        results["github"] = await test_provider("GitHub Models", GitHubModelsAdapter)
    else:
        print("\n⏭️  Skipping GitHub Models (no token)")
        results["github"] = None

    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)

    working = [name for name, status in results.items() if status is True]
    failed = [name for name, status in results.items() if status is False]
    skipped = [name for name, status in results.items() if status is None]

    if working:
        print(f"\n✅ Working providers ({len(working)}):")
        for name in working:
            print(f"   • {name}")

    if failed:
        print(f"\n❌ Failed providers ({len(failed)}):")
        for name in failed:
            print(f"   • {name}")

    if skipped:
        print(f"\n⏭️  Skipped providers ({len(skipped)}):")
        for name in skipped:
            print(f"   • {name}")

    if not working:
        print("\n⚠️  No providers are working!")
        return 1

    print(f"\n✅ {len(working)} provider(s) working successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
