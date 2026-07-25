#!/usr/bin/env python3
"""Diagnostic script to check API key configuration and test connectivity."""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings


def mask_key(key: str) -> str:
    """Mask API key for safe display."""
    if not key:
        return "❌ NOT SET"
    if len(key) < 10:
        return "⚠️  TOO SHORT (invalid)"
    return f"✅ {key[:8]}...{key[-4:]}"


async def test_gemini():
    """Test Gemini API connectivity."""
    print("\n🧪 Testing Gemini API...")
    try:
        from app.services.ai.providers.gemini import GeminiAdapter

        adapter = GeminiAdapter()
        await adapter.validate_config()

        # Try a simple test message
        response, tokens = await adapter.send_message(
            messages=[{"role": "user", "content": "Hi, respond with just 'ok'"}],
            system_prompt="You are a helpful assistant. Keep responses very short.",
            max_tokens=10,
            temperature=0.5,
        )

        print(f"   ✅ Gemini working! Response: {response[:50]}...")
        return True
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str:
            print(f"   ❌ Gemini quota exhausted: {str(e)[:200]}")
        elif "401" in err_str or "invalid" in err_str.lower():
            print(f"   ❌ Gemini auth failed (invalid key): {str(e)[:200]}")
        else:
            print(f"   ❌ Gemini error: {str(e)[:200]}")
        return False


async def test_openai():
    """Test OpenAI API connectivity."""
    print("\n🧪 Testing OpenAI API...")
    try:
        from app.services.ai.providers.openai import OpenAIAdapter

        adapter = OpenAIAdapter()
        await adapter.validate_config()

        # Try a simple test message
        response, tokens = await adapter.send_message(
            messages=[{"role": "user", "content": "Hi, respond with just 'ok'"}],
            system_prompt="You are a helpful assistant. Keep responses very short.",
            max_tokens=10,
            temperature=0.5,
        )

        print(f"   ✅ OpenAI working! Response: {response[:50]}...")
        return True
    except Exception as e:
        err_str = str(e)
        is_quota_error = (
            "429" in err_str
            or "quota" in err_str.lower()
            or "insufficient_quota" in err_str.lower()
        )
        if is_quota_error:
            print(f"   ❌ OpenAI quota exhausted (add payment method): {str(e)[:200]}")
        elif "401" in err_str or "invalid" in err_str.lower():
            print(f"   ❌ OpenAI auth failed (invalid key): {str(e)[:200]}")
        else:
            print(f"   ❌ OpenAI error: {str(e)[:200]}")
        return False


def main():
    """Run diagnostic checks."""
    print("=" * 70)
    print("🔍 API Key Diagnostic Tool")
    print("=" * 70)

    # Load settings
    print("\n📋 Loading configuration...")
    settings = get_settings()

    # Display current configuration
    print("\n🔑 API Keys:")
    print(f"   Gemini:       {mask_key(settings.gemini_api_key)}")
    print(f"   OpenAI:       {mask_key(settings.openai_api_key)}")
    print(f"   Groq:         {mask_key(settings.groq_api_key)}")
    print(f"   OpenRouter:   {mask_key(settings.open_router_api_key)}")
    print(f"   HuggingFace:  {mask_key(settings.hugging_face_api_key)}")
    print(f"   GitHub:       {mask_key(settings.github_token)}")

    print("\n⚙️  Models:")
    print(f"   Primary Provider:  {settings.ai_provider}")
    print(f"   Gemini Model:      {settings.gemini_model}")
    print(f"   OpenAI Model:      {settings.openai_model}")
    print(f"   Groq Model:        {settings.groq_model}")
    print(f"   OpenRouter Model:  {settings.open_router_model}")
    print(f"   HuggingFace Model: {settings.hugging_face_model}")
    print(f"   GitHub Model:      {settings.github_model}")

    # Check .env file location
    print("\n📁 Environment:")
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        print(f"   ✅ .env file found: {env_file}")
    else:
        print(f"   ⚠️  .env file not found: {env_file}")
        print("   (Keys may be from system environment)")

    # Validate key formats
    print("\n✅ Key Format Validation:")

    gemini_valid = False
    if settings.gemini_api_key:
        is_gemini_format = settings.gemini_api_key.startswith(
            "AIzaSy"
        ) or settings.gemini_api_key.startswith("AQ.")
        if is_gemini_format:
            print("   ✅ Gemini key format looks valid")
            gemini_valid = True
        else:
            print("   ❌ Gemini key format invalid (should start with 'AIzaSy' or 'AQ.')")
    else:
        print("   ⚠️  Gemini key not set")

    openai_valid = False
    if settings.openai_api_key:
        is_openai_format = settings.openai_api_key.startswith(
            "sk-"
        ) or settings.openai_api_key.startswith("sk-proj-")
        if is_openai_format:
            print("   ✅ OpenAI key format looks valid")
            openai_valid = True
        else:
            print("   ⚠️  OpenAI key format unusual (should start with 'sk-' or 'sk-proj-')")
    else:
        print("   ⚠️  OpenAI key not set")

    if settings.groq_api_key:
        if settings.groq_api_key.startswith("gsk_"):
            print("   ✅ Groq key format looks valid")
        else:
            print("   ❌ Groq key format invalid (should start with 'gsk_')")
    else:
        print("   ⚠️  Groq key not set")

    if settings.open_router_api_key:
        if settings.open_router_api_key.startswith("sk-or-v1-"):
            print("   ✅ OpenRouter key format looks valid")
        else:
            print("   ❌ OpenRouter key format invalid (should start with 'sk-or-v1-')")
    else:
        print("   ⚠️  OpenRouter key not set")

    if settings.hugging_face_api_key:
        if settings.hugging_face_api_key.startswith("hf_"):
            print("   ✅ HuggingFace key format looks valid")
        else:
            print("   ❌ HuggingFace key format invalid (should start with 'hf_')")
    else:
        print("   ⚠️  HuggingFace key not set")

    if settings.github_token:
        if settings.github_token.startswith("github_pat_"):
            print("   ✅ GitHub token format looks valid")
        else:
            print("   ❌ GitHub token format invalid (should start with 'github_pat_')")
    else:
        print("   ⚠️  GitHub token not set")

    # Test connectivity
    print("\n🌐 Testing API Connectivity...")

    gemini_works = False
    openai_works = False

    if gemini_valid:
        gemini_works = asyncio.run(test_gemini())
    else:
        print("\n   ⏭️  Skipping Gemini test (key not valid)")

    if openai_valid:
        openai_works = asyncio.run(test_openai())
    else:
        print("\n   ⏭️  Skipping OpenAI test (key not valid)")

    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)

    if gemini_works:
        print("✅ Gemini is working!")
    elif gemini_valid:
        print("❌ Gemini key valid but quota exhausted - wait or upgrade")
    else:
        print("❌ Gemini not configured properly")

    if openai_works:
        print("✅ OpenAI is working!")
    elif openai_valid:
        print("❌ OpenAI key valid but quota exhausted - add payment method")
    else:
        print("❌ OpenAI not configured properly")

    if not (gemini_works or openai_works):
        print("\n⚠️  NO WORKING AI PROVIDERS!")
        print("\n💡 Solutions:")
        print("   1. Gemini free tier: Wait until quota resets (20 requests/day)")
        print(
            "   2. OpenAI: Add payment method at "
            "https://platform.openai.com/settings/organization/billing/overview"
        )
        print("   3. Get new Gemini key: https://aistudio.google.com/apikey")
        print(
            "   4. After updating .env, rebuild: docker-compose down && docker-compose up --build"
        )
        return 1

    print("\n✅ At least one provider is working!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
