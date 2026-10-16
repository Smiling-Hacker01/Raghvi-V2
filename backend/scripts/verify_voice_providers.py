"""Interactive CLI verification script for Voice AI Providers (IndicF5, Coqui XTTS, VoiceRouter).

Usage:
    cd backend
    uv run python scripts/verify_voice_providers.py
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.services.voice.provider_factory import VoiceProviderFactory  # noqa: E402
from app.services.voice.providers.base import (  # noqa: E402
    VoiceCapability,
    VoiceCloneRequest,
    VoiceSynthesisRequest,
)
from app.services.voice.router import VoiceRouter  # noqa: E402


async def main():
    print("=" * 70)
    print("🎙️  RAGHVI V2 — VOICE PROVIDER & MODEL VERIFICATION SUITE")
    print("=" * 70)

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Provider Registry Inspection
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 1] Inspecting Voice Provider Registry...")
    registered = VoiceProviderFactory.list_providers()
    print(f"  • Registered providers in factory: {', '.join(registered)}")
    assert "indicf5" in registered, "IndicF5 provider must be registered"
    assert "coqui_xtts" in registered, "Coqui XTTS provider must be registered"
    print("  ✓ Factory registration verified successfully.")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. IndicF5 Verification (11 Indian Languages + Zero-Shot Cloning)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 2] Testing IndicF5 Provider (AI4Bharat Flow-Matching)...")
    indic_provider = VoiceProviderFactory.create_provider("indicf5", {})

    # Capabilities
    caps = indic_provider.get_capabilities()
    langs_str = ", ".join(sorted(caps.supported_languages))
    print(f"  • Provider Name: {indic_provider.provider_name}")
    print(f"  • License: {caps.license_type} (Commercial Ready: {caps.is_commercial_ready})")
    print(f"  • Supported Languages ({len(caps.supported_languages)}): {langs_str}")
    print(f"  • Capabilities: {', '.join(c.value for c in caps.capabilities)}")
    print(f"  • Sample Rate: {caps.sample_rates} Hz")

    # Health Check
    health = await indic_provider.check_health()
    print(f"  • Health Status: {health.get('status')} (Mode: {health.get('mode')})")

    # Speech Synthesis Test (Hindi & Script Detection)
    hindi_text = "नमस्ते! मैं राघवी हूँ, आपकी बुद्धिमत्तापूर्ण एआई साथी।"
    print(f"  • Synthesizing Hindi test phrase: '{hindi_text}'")
    synth_req = VoiceSynthesisRequest(
        text=hindi_text,
        voice_id="indicf5_hi_default",
        language="hi",
    )
    indic_response = await indic_provider.synthesize_speech(synth_req)
    output_wav_indic = backend_dir / "indicf5_sample_output.wav"
    output_wav_indic.write_bytes(indic_response.audio_data)
    print(
        f"  ✓ Hindi speech synthesized: {len(indic_response.audio_data)} bytes "
        f"({indic_response.audio_format})"
    )
    print(f"  📁 Saved sample audio to: {output_wav_indic}")

    # Zero-Shot Voice Cloning Simulation
    print("  • Verifying Zero-Shot Cloning Contract...")
    clone_req = VoiceCloneRequest(
        user_id="demo_user",
        voice_name="IndicF5ClonedVoice",
        audio_file_path=str(output_wav_indic),
        reference_text="नमस्ते, यह मेरी आवाज़ का नमूना है।",
        consent_confirmed=True,
    )
    clone_res = await indic_provider.clone_voice(clone_req)
    print(f"  ✓ Voice cloned successfully! ID: {clone_res.voice_id}")
    print(f"    Reference transcript: {clone_res.reference_text}")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Coqui XTTS Verification (English TTS + CPML Guardrail)
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 3] Testing Coqui XTTS Provider (Multilingual / English)...")
    coqui_provider = VoiceProviderFactory.create_provider("coqui_xtts", {})

    # Capabilities & Licensing Guardrail
    coqui_caps = coqui_provider.get_capabilities()
    print(f"  • Provider Name: {coqui_provider.provider_name}")
    print(f"  • License: {coqui_caps.license_type}")
    print(
        f"  • Commercial Production Ready: {coqui_caps.is_commercial_ready} "
        "(Guarded by CPML license)"
    )
    print(f"  • Capabilities: {', '.join(c.value for c in coqui_caps.capabilities)}")

    # Health Check
    coqui_health = await coqui_provider.check_health()
    print(f"  • Health Status: {coqui_health.get('status')} (Mode: {coqui_health.get('mode')})")

    # Speech Synthesis Test (English)
    english_text = "Hello! I am Raghvi, testing vendor-agnostic speech synthesis."
    print(f"  • Synthesizing English test phrase: '{english_text}'")
    coqui_req = VoiceSynthesisRequest(
        text=english_text,
        voice_id="xtts_default",
        language="en",
    )
    coqui_response = await coqui_provider.synthesize_speech(coqui_req)
    output_wav_coqui = backend_dir / "coqui_xtts_sample_output.wav"
    output_wav_coqui.write_bytes(coqui_response.audio_data)
    print(
        f"  ✓ English speech synthesized: {len(coqui_response.audio_data)} bytes "
        f"({coqui_response.audio_format})"
    )
    print(f"  📁 Saved sample audio to: {output_wav_coqui}")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. VoiceRouter & Capability-Aware Routing Verification
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[Step 4] Testing VoiceRouter (Intelligent Routing & Failover)...")
    router = VoiceRouter([indic_provider, coqui_provider])

    # Route Indian language -> IndicF5
    hi_candidates = router.find_compatible_providers("hi", VoiceCapability.TEXT_TO_SPEECH)
    print(f"  • Candidate providers for language 'hi': {[p.provider_name for p in hi_candidates]}")
    assert hi_candidates[0].provider_name == "indicf5", "Hindi must route to IndicF5 first"
    print("  ✓ Hindi routed to IndicF5 as primary provider.")

    # Route Tamil language -> IndicF5
    ta_candidates = router.find_compatible_providers("ta", VoiceCapability.TEXT_TO_SPEECH)
    print(f"  • Candidate providers for language 'ta': {[p.provider_name for p in ta_candidates]}")
    assert ta_candidates[0].provider_name == "indicf5", "Tamil must route to IndicF5"
    print("  ✓ Tamil routed to IndicF5 as primary provider.")

    # Route English language -> Coqui XTTS
    en_candidates = router.find_compatible_providers("en", VoiceCapability.TEXT_TO_SPEECH)
    print(f"  • Candidate providers for language 'en': {[p.provider_name for p in en_candidates]}")
    assert en_candidates[0].provider_name == "coqui_xtts", "English must route to Coqui XTTS"
    print("  ✓ English routed to Coqui XTTS.")

    # Routed Speech Synthesis
    print("  • Executing routed speech synthesis via VoiceRouter...")
    routed_resp = await router.synthesize_speech(
        VoiceSynthesisRequest(text="வணக்கம், நான் ராகவி.", voice_id="default", language="ta")
    )
    print(f"  ✓ Routed Tamil synthesis succeeded via provider: {routed_resp.provider}")

    # Clean up generated test audio
    for p in (output_wav_indic, output_wav_coqui):
        if p.exists():
            p.unlink()

    print("\n" + "=" * 70)
    print("🎉 ALL VOICE PROVIDERS AND ROUTING POLICIES ARE FUNCTIONING CORRECTLY!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
