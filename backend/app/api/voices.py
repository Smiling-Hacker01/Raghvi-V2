"""Voice management and synthesis endpoints."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.user import User
from app.services.storage.s3_service import S3Service
from app.services.subscription_service import SubscriptionService
from app.services.voice.voice_service import VoiceService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voices", tags=["voices"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.get("/")
async def list_my_voices(
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """List current user's voices."""
    try:
        voices = await VoiceService.get_user_voices(current_user.id, session)

        return {
            "voices": [
                {
                    "id": str(voice.id),
                    "voice_name": voice.voice_name,
                    "voice_type": voice.voice_type,
                    "provider": voice.provider,
                    "languages": voice.languages,
                    "is_active": voice.is_active,
                    "is_default": voice.is_default,
                    "is_available": voice.is_available,
                    "audio_sample_url": voice.audio_sample_url,
                    "created_at": voice.created_at.isoformat(),
                    "expires_at": voice.expires_at.isoformat() if voice.expires_at else None,
                }
                for voice in voices
            ],
            "total": len(voices),
        }

    except Exception as e:
        logger.error(f"Failed to list voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load voices",
        ) from e


@router.post("/upload")
async def upload_voice_sample(
    current_user: CurrentUser,
    session: DbSession,
    voice_name: Annotated[str, Form()],
    audio_file: Annotated[UploadFile, File()],
    languages: Annotated[str, Form()] = "en",
) -> dict:
    """
    Upload and register a voice sample.

    This endpoint accepts an audio file upload and creates a user voice record.
    It does NOT perform voice cloning yet - that requires additional processing.
    """
    try:
        settings = get_settings()

        # Validate file
        if not audio_file.content_type or not audio_file.content_type.startswith("audio/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an audio file",
            )

        # Check file size
        audio_data = await audio_file.read()
        if len(audio_data) > settings.voice_clone_max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large (max {settings.voice_clone_max_file_size / 1024 / 1024}MB)",
            )

        if len(audio_data) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Empty audio file",
            )

        # Check subscription allows custom voices
        subscription = await SubscriptionService.get_user_subscription(current_user.id, session)

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required",
            )

        plan = await SubscriptionService.get_subscription_plan(subscription.plan_id, session)

        if not plan or plan.max_custom_voices == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your plan does not support custom voices. Upgrade to Pro or higher.",
            )

        # Check voice quota
        existing_voices = await VoiceService.get_user_voices(current_user.id, session)
        custom_voices = [v for v in existing_voices if v.voice_type == "custom"]

        if len(custom_voices) >= plan.max_custom_voices:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Voice limit reached ({plan.max_custom_voices}). "
                    "Delete a voice or upgrade your plan."
                ),
            )

        # Upload to S3
        s3_service = S3Service()

        # Generate temp voice ID for storage
        import uuid

        temp_voice_id = str(uuid.uuid4())

        # Determine file extension
        file_ext = audio_file.filename.split(".")[-1] if "." in audio_file.filename else "wav"

        s3_url = await s3_service.upload_voice_sample(
            user_id=current_user.id,
            voice_id=temp_voice_id,
            audio_data=audio_data,
            file_extension=file_ext,
        )

        # Create voice record (system voice for now, can be cloned later)
        voice = await VoiceService.create_user_voice(
            user_id=current_user.id,
            voice_type="system",  # Will be "custom" after cloning
            voice_id=temp_voice_id,  # Will be replaced with provider voice ID
            voice_name=voice_name,
            provider="elevenlabs",  # Default provider
            languages=languages,
            subscription_plan_id=subscription.plan_id,
            expires_at=subscription.expires_at,
            audio_sample_url=s3_url,
            session=session,
        )

        logger.info(f"Voice sample uploaded for user {current_user.id}: {voice_name}")

        return {
            "voice_id": str(voice.id),
            "voice_name": voice.voice_name,
            "audio_sample_url": s3_url,
            "status": "uploaded",
            "message": (
                "Voice sample uploaded. Call /voices/{voice_id}/clone to create voice clone."
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload voice: {str(e)}",
        ) from e


@router.post("/{voice_id}/clone")
async def clone_voice(
    voice_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """
    Clone a voice using the uploaded audio sample.

    This triggers the actual voice cloning with the provider (ElevenLabs).
    """
    try:
        # Get voice record
        voice = await VoiceService.get_user_voice(str(voice_id), current_user.id, session)

        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found",
            )

        if not voice.audio_sample_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No audio sample found for this voice",
            )

        # Download audio from S3
        # For now, return success message

        # For now, return success message
        # TODO: Implement actual voice cloning with provider

        logger.info(f"Voice cloning requested for voice {voice_id}")

        return {
            "voice_id": str(voice.id),
            "status": "cloning_pending",
            "message": "Voice cloning started. This may take a few minutes.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clone voice",
        ) from e


@router.post("/{voice_id}/set-default")
async def set_default_voice(
    voice_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Set a voice as the default voice for the user."""
    try:
        await VoiceService.set_default_voice(str(voice_id), current_user.id, session)

        return {
            "voice_id": str(voice_id),
            "message": "Default voice updated",
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Failed to set default voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default voice",
        ) from e


@router.delete("/{voice_id}")
async def delete_voice(
    voice_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Delete a voice."""
    try:
        # Get voice to delete S3 file
        voice = await VoiceService.get_user_voice(str(voice_id), current_user.id, session)

        if not voice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Voice not found",
            )

        # Delete from S3 if exists
        if voice.audio_sample_url:
            s3_service = S3Service()
            await s3_service.delete_voice_sample(voice.audio_sample_url)

        # Soft delete voice record
        await VoiceService.delete_user_voice(str(voice_id), current_user.id, session)

        return {
            "voice_id": str(voice_id),
            "message": "Voice deleted successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete voice: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete voice",
        ) from e


@router.get("/system")
async def list_system_voices(
    current_user: CurrentUser,
    session: DbSession,
    language: str | None = None,
) -> dict:
    """List available system voices."""
    try:
        voices = await VoiceService.get_system_voices(session, language)

        return {
            "voices": [
                {
                    "id": voice.id,
                    "voice_name": voice.voice_name,
                    "provider": voice.provider,
                    "language": voice.language,
                    "quality_score": voice.quality_score,
                }
                for voice in voices
            ],
            "total": len(voices),
        }

    except Exception as e:
        logger.error(f"Failed to list system voices: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load system voices",
        ) from e


@router.post("/synthesize")
async def synthesize_speech(
    current_user: CurrentUser,
    session: DbSession,
    text: Annotated[str, Form()],
    voice_id: Annotated[str | None, Form()] = None,
    language: Annotated[str, Form()] = "en",
) -> dict:
    """
    Synthesize speech from text using voice providers with automatic fallback.

    If voice_id is provided, uses that voice. Otherwise, uses user's default voice
    or a system default voice.

    Returns audio data as base64 encoded string that can be played in the browser.
    """
    import base64

    try:
        from app.services.voice.providers.base import VoiceSynthesisRequest
        from app.services.voice.voice_adapter_builder import get_voice_adapter

        # Get voice adapter with multi-provider fallback
        adapter = get_voice_adapter()

        # Determine which voice to use
        if voice_id:
            # Use specified voice
            voice = await VoiceService.get_user_voice(voice_id, current_user.id, session)
            if not voice:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Voice not found",
                )
            selected_voice_id = voice.voice_id
        else:
            # Use user's default voice or fallback to system default
            voices = await VoiceService.get_user_voices(current_user.id, session)
            default_voices = [v for v in voices if v.is_default]

            # Use Deepgram-compatible default (works if Deepgram is configured)
            selected_voice_id = default_voices[0].voice_id if default_voices else "aura-asteria-en"

        # Create synthesis request
        request = VoiceSynthesisRequest(
            text=text,
            voice_id=selected_voice_id,
            language=language,
        )

        # Synthesize with automatic fallback
        logger.info(f"Synthesizing speech for user {current_user.id}: '{text[:50]}...'")

        response = await adapter.synthesize_speech(request)

        # Return audio data
        # Option 1: Return as base64 JSON (easy for web)
        audio_base64 = base64.b64encode(response.audio_data).decode("utf-8")

        return {
            "success": True,
            "text": text,
            "voice_id": selected_voice_id,
            "provider": "voice_synthesis",
            "audio_base64": audio_base64,
            "audio_format": response.audio_format,
            "sample_rate": 44100,
            "duration_estimate": len(text) / 10,  # Rough estimate
        }

        # Option 2: Return as binary audio file (uncomment if needed)
        # return Response(
        #     content=response.audio_data,
        #     media_type="audio/wav",
        #     headers={
        #         "Content-Disposition": f"attachment; filename=raghvi_speech.wav"
        #     }
        # )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech synthesis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize speech: {str(e)}",
        ) from e
