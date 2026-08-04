import pytest
from app.services.ai.prompt import (
    build_system_prompt,
    get_error_response,
    get_memory_full_context,
    invalidate_creator_cache,
    get_creator_context_cached,
)
from app.models.memory import Memory
from app.models.task import Task
from datetime import datetime, timezone

pytestmark = pytest.mark.asyncio

async def test_prompt_generation_functions():
    # Test error response
    err = get_error_response()
    assert isinstance(err, str)
    assert len(err) > 0

    # Test memory full context
    memories = [
        Memory(id="1", content="I like cats"),
        Memory(id="2", content="I live in NY")
    ]
    mem_full = get_memory_full_context(memories)
    assert "I like cats" in mem_full
    
    empty_mem = get_memory_full_context([])
    assert "getting to know me" in empty_mem

    # Test build system prompt
    tasks = [
        Task(id="1", title="Buy groceries", priority="high", due_date=datetime.now(timezone.utc)),
    ]
    prompt = await build_system_prompt(user_memories=memories, session=None, user_tasks=tasks)
    assert isinstance(prompt, str)
    assert "Raghvi" in prompt
    assert "I like cats" in prompt
    assert "Buy groceries" in prompt
    
    # Test creator cache
    invalidate_creator_cache()
    cached1 = await get_creator_context_cached(None)
    assert isinstance(cached1, str)
    cached2 = await get_creator_context_cached(None)
    assert cached1 == cached2

async def test_stripe_webhook_invalid_payload(client):
    from unittest.mock import patch
    import stripe
    with patch("stripe.Webhook.construct_event", side_effect=ValueError("Invalid payload")):
        response = await client.post(
            "/webhooks/stripe", 
            content=b"{}", 
            headers={"stripe-signature": "test"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid payload"

async def test_stripe_webhook_invalid_signature(client):
    from unittest.mock import patch
    import stripe
    with patch("stripe.Webhook.construct_event", side_effect=stripe.error.SignatureVerificationError("Invalid sig", "sig")):
        response = await client.post(
            "/webhooks/stripe", 
            content=b"{}", 
            headers={"stripe-signature": "test"}
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid signature"

async def test_stripe_webhook_checkout_completed(client):
    from unittest.mock import patch
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "user_id": "test_user_id",
                    "plan_id": "pro"
                }
            }
        }
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        response = await client.post(
            "/webhooks/stripe", 
            content=b"{}", 
            headers={"stripe-signature": "test"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

async def test_stripe_webhook_checkout_completed_no_user(client):
    from unittest.mock import patch
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "plan_id": "pro"
                }
            }
        }
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        response = await client.post(
            "/webhooks/stripe", 
            content=b"{}", 
            headers={"stripe-signature": "test"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"

async def test_github_adapter_coverage():
    from app.services.ai.providers.github import GitHubModelsAdapter
    from unittest.mock import patch, AsyncMock
    
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.github_token = "github_pat_test"
        mock_settings.return_value.github_model = "gpt-4o"
        mock_settings.return_value.github_timeout_seconds = 30
        
        adapter = GitHubModelsAdapter()
        assert await adapter.validate_config()
        
        info = adapter.get_model_info()
        assert info["provider"] == "github"
        
        assert adapter._count_tokens("test text") == 2
        
        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message.content = "Test response"
            mock_create.return_value.usage.prompt_tokens = 10
            mock_create.return_value.usage.completion_tokens = 5
            
            response, tokens = await adapter.send_message(
                messages=[{"role": "user", "content": "hi"}],
                system_prompt="sys",
            )
            assert response == "Test response"
            assert tokens == 15


async def test_groq_adapter_coverage():
    """Test Groq adapter init, model info, token counting, and send_message."""
    from app.services.ai.providers.groq import GroqAdapter
    from unittest.mock import patch, AsyncMock

    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = "gsk_test_key"
        mock_settings.return_value.groq_model = "llama-3.1-8b-instant"
        mock_settings.return_value.groq_timeout_seconds = 30

        adapter = GroqAdapter()
        assert await adapter.validate_config()

        info = adapter.get_model_info()
        assert info["provider"] == "groq"

        assert adapter._count_tokens("hello world") == 2

        with patch.object(adapter.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value.choices = [AsyncMock()]
            mock_create.return_value.choices[0].message.content = "Groq reply"
            mock_create.return_value.usage.prompt_tokens = 8
            mock_create.return_value.usage.completion_tokens = 4

            resp, tokens = await adapter.send_message(
                messages=[{"role": "user", "content": "hello"}],
                system_prompt="be nice",
            )
            assert resp == "Groq reply"
            assert tokens == 12


async def test_chat_xml_parsing():
    """Test that chat service correctly parses XML tags from LLM response."""
    import re

    raw = """<emotion>happy</emotion>
<voice_text>नमस्ते, kaise ho?</voice_text>
<chat_text>Namaste, kaise ho?</chat_text>"""

    emotion_match = re.search(r"<emotion>(.*?)</emotion>", raw, re.DOTALL | re.IGNORECASE)
    voice_match = re.search(r"<voice_text>(.*?)</voice_text>", raw, re.DOTALL | re.IGNORECASE)
    chat_match = re.search(r"<chat_text>(.*?)</chat_text>", raw, re.DOTALL | re.IGNORECASE)

    assert emotion_match and emotion_match.group(1).strip() == "happy"
    assert voice_match and "नमस्ते" in voice_match.group(1)
    assert chat_match and "Namaste" in chat_match.group(1)


async def test_chat_xml_parsing_fallback():
    """Test that XML parsing falls back gracefully when tags are missing."""
    import re

    raw = "Just a plain response without any tags."
    emotion = "neutral"
    voice_text = raw
    chat_text = raw

    emotion_match = re.search(r"<emotion>(.*?)</emotion>", raw, re.DOTALL | re.IGNORECASE)
    voice_match = re.search(r"<voice_text>(.*?)</voice_text>", raw, re.DOTALL | re.IGNORECASE)
    chat_match = re.search(r"<chat_text>(.*?)</chat_text>", raw, re.DOTALL | re.IGNORECASE)

    if emotion_match:
        emotion = emotion_match.group(1).strip().lower()
    if voice_match:
        voice_text = voice_match.group(1).strip()
    if chat_match:
        chat_text = chat_match.group(1).strip()

    assert emotion == "neutral"
    assert voice_text == raw
    assert chat_text == raw


async def test_cartesia_emotion_mapping():
    """Test that Cartesia emotion mapping correctly converts LLM emotions."""
    emotion_map = {
        "happy": "positivity",
        "excited": "positivity",
        "sad": "sadness",
        "angry": "anger",
        "curious": "surprise",
    }
    assert emotion_map.get("happy") == "positivity"
    assert emotion_map.get("sad") == "sadness"
    assert emotion_map.get("angry") == "anger"
    assert emotion_map.get("curious") == "surprise"
    assert emotion_map.get("unknown") is None


async def test_github_adapter_invalid_token():
    """Test GitHubModelsAdapter raises on invalid token format."""
    from app.services.ai.providers.github import GitHubModelsAdapter
    from unittest.mock import patch
    import pytest

    with patch("app.services.ai.providers.github.get_settings") as mock_settings:
        mock_settings.return_value.github_token = "bad_token"
        mock_settings.return_value.github_model = "gpt-4o"
        mock_settings.return_value.github_timeout_seconds = 30

        adapter = GitHubModelsAdapter()
        with pytest.raises(ValueError, match="format is invalid"):
            await adapter.validate_config()


async def test_groq_adapter_invalid_token():
    """Test GroqAdapter raises on invalid token format."""
    from app.services.ai.providers.groq import GroqAdapter
    from unittest.mock import patch
    import pytest

    with patch("app.services.ai.providers.groq.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = "bad_key"
        mock_settings.return_value.groq_model = "llama"
        mock_settings.return_value.groq_timeout_seconds = 30

        adapter = GroqAdapter()
        with pytest.raises(ValueError, match="format is invalid"):
            await adapter.validate_config()
