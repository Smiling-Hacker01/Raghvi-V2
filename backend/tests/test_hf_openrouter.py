#!/usr/bin/env python3
"""Quick test for HuggingFace and OpenRouter providers."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_huggingface():
    """Test HuggingFace provider."""
    print("\n🧪 Testing HuggingFace...")
    try:
        from app.services.ai.providers.huggingface import HuggingFaceAdapter

        adapter = HuggingFaceAdapter()
        await adapter.validate_config()
        print("   ✅ Configuration valid")

        info = adapter.get_model_info()
        print(f"   📋 Model: {info['model_name']}")

        response, tokens = await adapter.send_message(
            messages=[{"role": "user", "content": "Say 'hello' only"}],
            system_prompt="Be concise.",
            max_tokens=20,
            temperature=0.5,
        )

        print("   ✅ API call successful!")
        print(f"   📝 Response: {response[:100]}")
        print(f"   🔢 Tokens: {tokens}")
        return True

    except Exception as e:
        print(f"   ❌ Error: {str(e)[:200]}")
        return False


async def test_openrouter():
    """Test OpenRouter provider."""
    print("\n🧪 Testing OpenRouter...")
    try:
        from app.services.ai.providers.openrouter import OpenRouterAdapter

        adapter = OpenRouterAdapter()
        await adapter.validate_config()
        print("   ✅ Configuration valid")

        info = adapter.get_model_info()
        print(f"   📋 Model: {info['model_name']}")

        response, tokens = await adapter.send_message(
            messages=[{"role": "user", "content": "Say 'hello' only"}],
            system_prompt="Be concise.",
            max_tokens=20,
            temperature=0.5,
        )

        print("   ✅ API call successful!")
        print(f"   📝 Response: {response[:100]}")
        print(f"   🔢 Tokens: {tokens}")
        return True

    except Exception as e:
        print(f"   ❌ Error: {str(e)[:200]}")
        return False


async def main():
    """Test both providers."""
    print("=" * 70)
    print("🔍 Testing HuggingFace and OpenRouter")
    print("=" * 70)

    hf_works = await test_huggingface()
    or_works = await test_openrouter()

    print("\n" + "=" * 70)
    print("📊 Results")
    print("=" * 70)
    print(f"HuggingFace: {'✅ Working' if hf_works else '❌ Failed'}")
    print(f"OpenRouter:  {'✅ Working' if or_works else '❌ Failed'}")

    if hf_works and or_works:
        print("\n✅ Both providers working!")
        return 0
    elif hf_works or or_works:
        print("\n⚠️  One provider working")
        return 0
    else:
        print("\n❌ Both providers failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
