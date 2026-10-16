"""Unit tests for voice text normalization and persona consistency."""

import pytest

from app.services.voice.providers.base import VoiceSynthesisRequest
from app.services.voice.providers.edge_tts_provider import EdgeTTSProvider
from app.services.voice.text_normalizer import clean_text_for_speech


def test_clean_text_strips_markdown_formatting():
    """Verify that markdown formatting is stripped so TTS vocoders don't verbalize syntax."""
    raw = (
        "# Welcome to Raghvi!\n"
        "I can help you with **task management**, *scheduling*, and __productivity__.\n"
        "> Let's get things done today!\n"
        "Check out our [website](https://example.com/docs) for more info."
    )
    cleaned = clean_text_for_speech(raw)

    assert "#" not in cleaned
    assert "**" not in cleaned
    assert "*" not in cleaned
    assert ">" not in cleaned
    assert "https://" not in cleaned
    assert "Check out our website for more info." in cleaned
    assert "task management, scheduling, and productivity." in cleaned


def test_clean_text_strips_emojis_and_pictographs():
    """Verify emojis are eliminated so neural vocoders don't stutter or crash."""
    raw = "Hello! 👋 I am Raghvi. ✨ How are you doing today? 🤖 Let's make today great! 🚀"
    cleaned = clean_text_for_speech(raw)

    assert "👋" not in cleaned
    assert "✨" not in cleaned
    assert "🤖" not in cleaned
    assert "🚀" not in cleaned
    assert cleaned == "Hello! I am Raaghvi. How are you doing today? Let's make today great!"


def test_clean_text_normalizes_bullet_points_with_pauses():
    """Verify bullet points are converted into sentences with punctuation for natural pauses."""
    raw = (
        "Here are three important items:\n"
        "- First item on the list\n"
        "- Second item on the list\n"
        "- Third item on the list"
    )
    cleaned = clean_text_for_speech(raw)

    assert "- First" not in cleaned
    # Ensure natural sentence breaks with periods
    assert "First item on the list." in cleaned
    assert "Second item on the list." in cleaned
    assert "Third item on the list." in cleaned


def test_clean_text_handles_code_blocks():
    """Verify multi-line code blocks are replaced with conversational text."""
    raw = (
        "Here is the function you requested:\n"
        "```python\n"
        "def hello_world():\n"
        "    return 'Hello'\n"
        "```\n"
        "You can run it in your terminal."
    )
    cleaned = clean_text_for_speech(raw)

    assert "def hello_world" not in cleaned
    assert "Here is the code." in cleaned
    assert "You can run it in your terminal." in cleaned


def test_clean_text_abbreviations_and_name_phonetics():
    """Verify technical abbreviations and Raghvi's name are phonetically normalized."""
    english_raw = "Raghvi uses AI and an API to assist you."
    english_cleaned = clean_text_for_speech(english_raw, is_hindi=False)
    assert "Raaghvi" in english_cleaned
    assert "A.I." in english_cleaned
    assert "A.P.I." in english_cleaned

    hindi_raw = "Raghvi आपकी AI सहायक है।"
    hindi_cleaned = clean_text_for_speech(hindi_raw, is_hindi=True)
    assert "राघवी" in hindi_cleaned


def test_edge_tts_emotion_settings_stability():
    """Verify emotion adjustments are gentle to prevent timbre distortions."""
    settings = EdgeTTSProvider._EMOTION_SETTINGS
    assert settings["neutral"]["rate"] == "-8%"
    assert settings["neutral"]["pitch"] == "+0Hz"
    # Happy and excited shouldn't swing wildly
    assert settings["happy"]["rate"] == "-6%"
    assert settings["excited"]["pitch"] == "+1Hz"
    # Sad and empathetic shouldn't drop into robotic slow motion
    assert settings["sad"]["rate"] == "-10%"
    assert settings["empathetic"]["pitch"] == "-1Hz"


@pytest.mark.asyncio
async def test_edge_tts_persona_anchoring(monkeypatch):
    """Verify EdgeTTS defaults to Swara for consistent persona across languages."""
    provider = EdgeTTSProvider({})

    captured_voices = []

    class MockCommunicate:
        def __init__(self, text, voice, rate, pitch):
            captured_voices.append((voice, text, rate, pitch))

        async def stream(self):
            yield {"type": "audio", "data": b"fake_mp3_audio_data"}

    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", MockCommunicate)

    # 1. English text without explicit voice -> should anchor to Swara (unified persona)
    req1 = VoiceSynthesisRequest(
        text="Hello, how can I help you today? 👋",
        voice_id="default",
        language="en",
    )
    res1 = await provider.synthesize_speech(req1)
    assert res1.audio_data == b"fake_mp3_audio_data"
    assert captured_voices[-1][0] == "hi-IN-SwaraNeural"
    # Markdown/emoji should be cleaned
    assert "👋" not in captured_voices[-1][1]

    # 2. Hindi text without explicit voice -> also Swara
    req2 = VoiceSynthesisRequest(
        text="नमस्ते! मैं आपकी क्या सहायता करूँ?",
        voice_id=None,
        language="hi",
    )
    await provider.synthesize_speech(req2)
    assert captured_voices[-1][0] == "hi-IN-SwaraNeural"

    # 3. Explicitly requested Edge voice (e.g. Neerja) -> should be honored
    req3 = VoiceSynthesisRequest(
        text="This is Neerja speaking.",
        voice_id="en-IN-NeerjaNeural",
        language="en",
    )
    await provider.synthesize_speech(req3)
    assert captured_voices[-1][0] == "en-IN-NeerjaNeural"


@pytest.mark.asyncio
async def test_edge_tts_empty_text_fallback(monkeypatch):
    """Verify EdgeTTS safely synthesizes fallback phrase if input cleans to empty."""
    provider = EdgeTTSProvider({})
    captured_texts = []

    class MockCommunicate:
        def __init__(self, text, voice, rate, pitch):
            captured_texts.append(text)

        async def stream(self):
            yield {"type": "audio", "data": b"mock_speech"}

    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", MockCommunicate)

    # Pass text containing only emojis/whitespace
    req = VoiceSynthesisRequest(text="👋 ✨ 🚀", voice_id="default", language="en")
    await provider.synthesize_speech(req)
    assert captured_texts[-1] == "I understand."
