"""Conversational quality, personality boundaries, and multi-turn regression tests."""

import re

import pytest

from app.models.memory import Memory
from app.models.task import Task
from app.services.ai.prompt import (
    build_system_prompt,
    get_error_response,
)

# ==============================================================================
# Phase 3 Personality, Identity & Boundary Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_personality_friend_identity_and_never_ai():
    """Verify Raghvi is strictly the user's closest friend and NEVER claims to be an AI."""
    prompt = await build_system_prompt()

    # Must state she is the user's closest friend and companion
    assert "You are Raghavi — someone's closest friend and companion." in prompt
    assert "You will NEVER say that you are an AI" in prompt
    assert "ALWAYS say that you are their friend" in prompt
    assert 'write your name as "Raghavi"' in prompt


@pytest.mark.asyncio
async def test_language_and_speech_rhythm_instructions():
    """Verify prompt instructs Devanagari for Hindi voice_text and natural conversational pacing."""
    prompt = await build_system_prompt()

    assert "ALWAYS write Hindi/Urdu words in Devanagari script" in prompt
    assert "<emotion>" in prompt
    assert "<voice_text>" in prompt
    assert "<chat_text>" in prompt
    assert "NATURAL SPEECH RHYTHM" in prompt


@pytest.mark.asyncio
async def test_memory_context_formatting_natural():
    """Verify user memories are formatted organically rather than as robotic database dumps."""
    mem1 = Memory(
        user_id="test-user-id",
        content="Loves reading science fiction and astrophotography",
    )
    mem2 = Memory(
        user_id="test-user-id",
        content="Working on a Rust distributed systems project as a developer",
    )

    prompt = await build_system_prompt(user_memories=[mem1, mem2])

    assert "Things I know about you (because you've told me):" in prompt
    assert "Loves reading science fiction and astrophotography" in prompt
    assert "Working on a Rust distributed systems project as a developer" in prompt
    # Verify no internal metadata leaked into prompt
    assert "test-user-id" not in prompt


@pytest.mark.asyncio
async def test_task_context_integration():
    """Verify user goals/tasks are integrated warmly without nagging."""
    task1 = Task(
        user_id="test-user-id",
        title="Complete backend API tests",
        priority="high",
        status="pending",
    )

    prompt = await build_system_prompt(user_tasks=[task1])

    assert "Things you're currently working on / goals you've mentioned to me:" in prompt
    assert "Complete backend API tests" in prompt
    assert "never nag or act like a project manager" in prompt


def test_friendly_error_responses_no_robotic_jargon():
    """Verify fallback error responses sound human and avoid AI disclaimers."""
    for _ in range(20):
        error_msg = get_error_response()
        assert "AI language model" not in error_msg
        assert "OpenAI" not in error_msg
        assert "server error" not in error_msg
        assert "system exception" not in error_msg
        assert len(error_msg) > 10


# ==============================================================================
# Multi-turn Context and XML Parsing Tests
# ==============================================================================


def test_xml_structure_regex_parsing():
    """Verify parsing handles edge cases, whitespace, and case sensitivity."""
    xml_sample = """
    <emotion>playful</emotion>
    <voice_text>अरे वाह! यह तो बहुत बढ़िया है!</voice_text>
    <chat_text>Are wah! Yeh toh bahut badhiya hai! 😄</chat_text>
    """

    _flags = re.DOTALL | re.IGNORECASE
    emotion_match = re.search(r"<emotion>(.*?)</emotion>", xml_sample, _flags)
    voice_match = re.search(r"<voice_text>(.*?)</voice_text>", xml_sample, _flags)
    chat_match = re.search(r"<chat_text>(.*?)</chat_text>", xml_sample, _flags)

    assert emotion_match is not None
    assert emotion_match.group(1).strip() == "playful"
    assert voice_match is not None
    assert "अरे वाह!" in voice_match.group(1).strip()
    assert chat_match is not None
    assert "Are wah!" in chat_match.group(1).strip()
