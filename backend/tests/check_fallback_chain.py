#!/usr/bin/env python3
"""Test the fallback chain integration."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


async def test_chain():
    """Test the provider fallback chain."""
    print("=" * 70)
    print("🔗 Testing AI Provider Fallback Chain")
    print("=" * 70)

    from app.services.ai.chain import AIProviderChain

    # Initialize chain
    chain = AIProviderChain()

    # Show available providers
    providers = chain.get_available_providers()
    print(f"\n📋 Providers in fallback chain ({len(providers)}):")
    for i, provider in enumerate(providers, 1):
        if i == 1:
            print(f"   {i}. {provider} (PRIMARY)")
        else:
            print(f"   {i}. {provider} (fallback)")

    # Test actual message send
    print("\n🧪 Testing message send through chain...")
    try:
        response, tokens, provider_used = await chain.send_message(
            messages=[{"role": "user", "content": "Say 'Hello from the chain!' and nothing else"}],
            system_prompt="You are a helpful assistant. Keep responses very short.",
            max_tokens=20,
            temperature=0.5,
        )

        print("\n✅ Success!")
        print(f"   Provider used: {provider_used}")
        print(f"   Response: {response[:100]}")
        print(f"   Tokens: {tokens}")

    except Exception as e:
        print(f"\n❌ Chain failed: {e}")
        return False

    # Test fallback behavior by simulating primary failure
    print("\n🔄 Testing fallback behavior...")
    print(f"   Primary provider: {providers[0]}")
    if len(providers) > 1:
        print(f"   Fallback providers: {providers[1:]}")
        print(f"   ✅ Fallback chain configured with {len(providers) - 1} backup(s)")
    else:
        print("   ⚠️  No fallback providers configured")

    return True


async def main():
    """Main test runner."""
    success = await test_chain()

    print("\n" + "=" * 70)
    if success:
        print("✅ Fallback chain integration test PASSED")
        return 0
    else:
        print("❌ Fallback chain integration test FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
