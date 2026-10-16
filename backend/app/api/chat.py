"""Chat endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.session import get_db_session
from app.models.message import Message
from app.models.user import User
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatSendRequest,
    ChatSendResponse,
    ConversationResponse,
)
from app.services.chat import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Type aliases
CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/send", response_model=ChatSendResponse)
async def send_message(
    request: ChatSendRequest,
    current_user: CurrentUser,
    session: DbSession,
) -> ChatSendResponse:
    """Send message to Raghvi.

    Raghvi will:
    1. Retrieve your relevant memories for context
    2. Include them in the conversation
    3. Respond with personalized advice
    """
    # Extract user_id before try block (avoid lazy-load issues)
    user_id = str(current_user.id)

    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )

    try:
        result = await ChatService.send_message(
            user_id=user_id,
            user_message_content=request.content,
            session=session,
        )

        return ChatSendResponse(**result)

    except ValueError as e:
        logger.error(f"Chat validation error for user {user_id}: {e}")
        from app.services.ai.prompt import get_error_response

        return ChatSendResponse(
            user_message=request.content,
            assistant_message=get_error_response(),
            tokens_used=0,
        )

    except Exception as e:
        logger.error(f"Chat error for user {user_id}: {e}")
        await session.rollback()
        from app.services.ai.prompt import get_error_response

        return ChatSendResponse(
            user_message=request.content,
            assistant_message=get_error_response(),
            tokens_used=0,
        )


@router.post("/send-with-voice")
async def send_message_with_voice(
    request: ChatSendRequest,
    current_user: CurrentUser,
    session: DbSession,
    language: str = "en",
) -> dict:
    """
    Send message to Raghvi and get response with voice audio.

    This endpoint:
    1. Gets Raghvi's text response (same as /send)
    2. Synthesizes the response to audio
    3. Returns both text and audio (base64)

    Perfect for mobile apps and voice-enabled interfaces!
    """
    import base64

    # Extract user_id before try block
    user_id = str(current_user.id)

    if not request.content.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )

    try:
        # Get Raghvi's text response
        result = await ChatService.send_message(
            user_id=user_id,
            user_message_content=request.content,
            session=session,
        )

        # Synthesize the response to audio
        from app.services.voice.providers.base import VoiceSynthesisRequest
        from app.services.voice.voice_adapter_builder import get_voice_adapter
        from app.services.voice.voice_service import VoiceService

        # Get voice adapter with multi-provider fallback
        adapter = get_voice_adapter()

        # Get user's default voice or use system default
        voices = await VoiceService.get_user_voices(current_user.id, session)
        default_voices = [v for v in voices if v.is_default]

        # Default fallback voice for multilingual providers (Swara Indian Neural)
        voice_id = default_voices[0].voice_id if default_voices else "hi-IN-SwaraNeural"

        # Cleanse and normalize conversational response for smooth prosody
        from app.services.voice.text_normalizer import clean_text_for_speech

        raw_text = result.get("voice_text") or result.get("assistant_message") or ""
        is_hindi = language.lower().startswith("hi") or any(
            "\u0900" <= ch <= "\u097f" for ch in raw_text
        )
        cleaned_text = clean_text_for_speech(raw_text, is_hindi=is_hindi)
        if not cleaned_text.strip():
            cleaned_text = "जी, समझ गई।" if is_hindi else "I understand."

        # Create synthesis request using the phonetic voice_text and emotion
        synthesis_request = VoiceSynthesisRequest(
            text=cleaned_text,
            voice_id=voice_id,
            language=language,
            emotion=result.get("emotion"),
        )

        logger.info(f"Synthesizing Raghvi's response for user {user_id}")

        # Synthesize speech with automatic fallback
        audio_response = await adapter.synthesize_speech(synthesis_request)

        # Encode audio to base64
        audio_base64 = base64.b64encode(audio_response.audio_data).decode("utf-8")

        return {
            "user_message": result["user_message"],
            "assistant_message": result["assistant_message"],
            "tokens_used": result["tokens_used"],
            "audio": {
                "data_base64": audio_base64,
                "format": audio_response.audio_format,
                "sample_rate": 44100,
                "provider": "voice_synthesis",
                "duration_estimate": len(result["assistant_message"]) / 10,
            },
        }

    except ValueError as e:
        logger.error(f"Chat validation error for user {user_id}: {e}")
        from app.services.ai.prompt import get_error_response

        error_message = get_error_response()

        # Try to synthesize the error message
        audio_payload = None
        try:
            from app.services.voice.providers.base import VoiceSynthesisRequest
            from app.services.voice.text_normalizer import clean_text_for_speech
            from app.services.voice.voice_adapter_builder import get_voice_adapter

            adapter = get_voice_adapter()
            voice_id = "hi-IN-SwaraNeural"

            is_hindi = language.lower().startswith("hi") or any(
                "\u0900" <= ch <= "\u097f" for ch in error_message
            )
            cleaned_error = clean_text_for_speech(error_message, is_hindi=is_hindi)
            if not cleaned_error.strip():
                cleaned_error = "जी, समझ गई।" if is_hindi else "I understand."

            synthesis_request = VoiceSynthesisRequest(
                text=cleaned_error,
                voice_id=voice_id,
                language=language,
                emotion="empathetic",
            )
            audio_response = await adapter.synthesize_speech(synthesis_request)
            audio_base64 = base64.b64encode(audio_response.audio_data).decode("utf-8")
            audio_payload = {
                "data_base64": audio_base64,
                "format": audio_response.audio_format,
                "sample_rate": 44100,
                "provider": "voice_synthesis",
                "duration_estimate": len(error_message) / 10,
            }
        except Exception as synthesis_err:
            logger.error(f"Failed to synthesize friendly error voice response: {synthesis_err}")

        return {
            "user_message": request.content,
            "assistant_message": error_message,
            "tokens_used": 0,
            "audio": audio_payload,
        }

    except Exception as e:
        logger.error(f"Chat with voice error for user {user_id}: {e}", exc_info=True)
        await session.rollback()
        from app.services.ai.prompt import get_error_response

        error_message = get_error_response()

        # Try to synthesize the error message
        audio_payload = None
        try:
            from app.services.voice.providers.base import VoiceSynthesisRequest
            from app.services.voice.text_normalizer import clean_text_for_speech
            from app.services.voice.voice_adapter_builder import get_voice_adapter

            adapter = get_voice_adapter()
            voice_id = "hi-IN-SwaraNeural"

            is_hindi = language.lower().startswith("hi") or any(
                "\u0900" <= ch <= "\u097f" for ch in error_message
            )
            cleaned_error = clean_text_for_speech(error_message, is_hindi=is_hindi)
            if not cleaned_error.strip():
                cleaned_error = "जी, समझ गई।" if is_hindi else "I understand."

            synthesis_request = VoiceSynthesisRequest(
                text=cleaned_error,
                voice_id=voice_id,
                language=language,
                emotion="empathetic",
            )
            audio_response = await adapter.synthesize_speech(synthesis_request)
            audio_base64 = base64.b64encode(audio_response.audio_data).decode("utf-8")
            audio_payload = {
                "data_base64": audio_base64,
                "format": audio_response.audio_format,
                "sample_rate": 44100,
                "provider": "voice_synthesis",
                "duration_estimate": len(error_message) / 10,
            }
        except Exception as synthesis_err:
            logger.error(f"Failed to synthesize friendly error voice response: {synthesis_err}")

        return {
            "user_message": request.content,
            "assistant_message": error_message,
            "tokens_used": 0,
            "audio": audio_payload,
        }


@router.get("/", response_model=ConversationResponse)
async def get_conversation(
    current_user: CurrentUser,
    session: DbSession,
) -> ConversationResponse:
    """Get current conversation metadata.

    Protected endpoint (requires valid JWT token).

    Args:
        current_user: Current authenticated user
        session: Database session

    Returns:
        ConversationResponse with conversation metadata
    """
    try:
        conversation = await ChatService.get_or_create_conversation(current_user.id, session)
        message_count = await ChatService.get_conversation_message_count(conversation.id, session)

        return ConversationResponse(
            id=str(conversation.id),
            user_id=str(conversation.user_id),
            title=conversation.title,
            created_at=conversation.created_at.isoformat(),
            updated_at=conversation.updated_at.isoformat(),
            message_count=message_count,
        )
    except Exception as e:
        logger.error(f"Failed to get conversation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load conversation",
        ) from e


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    current_user: CurrentUser,
    session: DbSession,
    limit: int = 20,
    offset: int = 0,
) -> ChatHistoryResponse:
    """Get conversation history (paginated, newest first).

    Protected endpoint (requires valid JWT token).
    Returns messages in reverse chronological order (newest first).

    Args:
        limit: Max messages per page (default 20, max 100)
        offset: Pagination offset (default 0)
        current_user: Current authenticated user
        session: Database session

    Returns:
        ChatHistoryResponse with messages, total count, has_more flag
    """
    user_id = current_user.id

    try:
        # Validate pagination params
        limit = min(limit, 100)  # Cap at 100 to prevent abuse
        if limit < 1:
            limit = 20
        if offset < 0:
            offset = 0

        # Get user's conversation
        conversation = await ChatService.get_or_create_conversation(current_user.id, session)

        # Get total message count
        total = await ChatService.get_conversation_message_count(conversation.id, session)

        # Get paginated messages (newest first)
        messages = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .offset(offset)
            .limit(limit)
        )

        # Convert to response format
        message_list = [
            ChatMessageResponse(
                id=str(msg.id),
                role=msg.role,
                content=msg.content,
                tokens_used=msg.tokens_used,
                created_at=msg.created_at.isoformat(),
            )
            for msg in messages.all()
        ]

        # Reverse to get chronological order for client
        message_list.reverse()

        # Calculate has_more
        has_more = (offset + limit) < total

        logger.info(
            f"Retrieved {len(message_list)} messages for user {user_id} "
            f"(total: {total}, offset: {offset})"
        )

        return ChatHistoryResponse(
            messages=message_list,
            total=total,
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Failed to load chat history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load chat history",
        ) from e


class LiveGeminiVoiceRequest(BaseModel):
    message: str
    mode: str = "chat"  # "chat" (talk with Raghvi) or "translate" (transliterate input)
    history: list[dict[str, str]] = []
    sidecar_url: str | None = None
    speed: float = 1.0


@router.post("/live-gemini-voice")
async def live_gemini_voice(request: LiveGeminiVoiceRequest) -> dict:
    """Live conversational Gemini chat with zero-shot voice synthesis.

    Translates & responds to Hinglish/English intelligently without static mapping.
    """
    import base64

    import httpx

    from app.core.config import get_settings
    from app.services.ai.providers.gemini import GeminiAdapter
    from app.services.voice.text_normalizer import clean_text_for_speech

    msg = request.message.strip()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )

    settings = get_settings()
    sidecar_url = (request.sidecar_url or settings.indicf5_endpoint_url or "").rstrip("/")

    adapter = GeminiAdapter()

    if request.mode == "translate":
        system_prompt = (
            "You are an expert Hindi translator and transliterator. "
            "Convert the user's input into natural Hindi in pure Devanagari script (देवनागरी). "
            "Return ONLY the Devanagari Hindi text with no English words, quotes, or markdown."
        )
    else:
        system_prompt = (
            "You are Raghvi, a sweet, warm and intelligent AI companion assistant. "
            "The user may talk to you in Hinglish, Hindi, or English. "
            "Always reply warmly, helpfully and concisely (1-2 short sentences) in natural "
            "conversational Hindi using pure Devanagari script (देवनागरी). "
            "Do NOT use English or Latin alphabet so the speech synthesizer speaks smoothly."
        )

    messages = list(request.history)
    messages.append({"role": "user", "content": msg})

    try:
        reply_text, _ = await adapter.send_message(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=300,
            temperature=0.7,
        )
    except Exception as e:
        logger.error(f"Live Gemini API call failed: {e}")
        reply_text = "नमस्ते! मैं राघवी हूँ। मैं आपकी किस प्रकार सहायता कर सकती हूँ?"

    cleaned_speech_text = clean_text_for_speech(reply_text, is_hindi=True)

    audio_base64 = None
    if sidecar_url:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{sidecar_url}/synthesize",
                    json={
                        "text": cleaned_speech_text,
                        "language": "hi",
                        "speed": request.speed,
                    },
                )
                if res.status_code == 200:
                    audio_base64 = base64.b64encode(res.content).decode("utf-8")
                else:
                    logger.warning(f"Sidecar returned status {res.status_code}: {res.text}")
        except Exception as e:
            logger.warning(f"Voice synthesis via sidecar failed: {e}")

    return {
        "user_message": msg,
        "assistant_message": reply_text,
        "hindi_text": cleaned_speech_text,
        "audio_base64": audio_base64,
        "provider": "Gemini Live + IndicF5 GPU Cloned Voice",
    }
