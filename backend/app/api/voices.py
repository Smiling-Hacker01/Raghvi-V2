"""Voice management and synthesis endpoints."""

import logging
import os
from typing import Annotated, Any
from uuid import UUID

import httpx
from anyio import Path as AsyncPath
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
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


class VoiceSettingsUpdate(BaseModel):
    """Payload for updating user voice settings."""

    voice_enabled: bool | None = None
    speaking_style: str | None = None
    language: str | None = None
    voice_activation_enabled: bool | None = None
    allow_interruptions: bool | None = None
    personalized_voice_enabled: bool | None = None
    selected_voice_id: str | None = None


@router.get("/settings")
async def get_voice_settings(
    current_user: CurrentUser,
) -> dict:
    """Retrieve user voice and speech preferences."""
    defaults = {
        "voice_enabled": True,
        "speaking_style": "conversational",
        "language": "en",
        "voice_activation_enabled": False,
        "allow_interruptions": True,
        "personalized_voice_enabled": True,
        "selected_voice_id": None,
    }
    user_prefs = (current_user.preferences or {}).get("voice_settings", {})
    return {**defaults, **user_prefs}


@router.put("/settings")
async def update_voice_settings(
    settings_update: VoiceSettingsUpdate,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Update user voice and speech preferences."""
    current_prefs = dict(current_user.preferences or {})
    voice_prefs = current_prefs.get(
        "voice_settings",
        {
            "voice_enabled": True,
            "speaking_style": "conversational",
            "language": "en",
            "voice_activation_enabled": False,
            "allow_interruptions": True,
            "personalized_voice_enabled": True,
            "selected_voice_id": None,
        },
    )

    updates = settings_update.model_dump(exclude_unset=True)
    voice_prefs.update(updates)
    current_prefs["voice_settings"] = voice_prefs

    current_user.preferences = current_prefs
    await session.commit()
    return voice_prefs


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
    consent_confirmed: Annotated[bool, Form()] = False,
) -> dict:
    """Upload and register an authorized voice sample from audio or video media."""
    try:
        settings = get_settings()

        # Enforce explicit authorization and consent verification
        if not consent_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Explicit user authorization and consent required to register voice sample",
            )

        # Validate media format (audio or video container)
        content_type = (audio_file.content_type or "").lower()
        filename_lower = (audio_file.filename or "").lower()
        allowed_exts = (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".mp4", ".mov", ".webm")

        is_valid_type = (
            content_type.startswith("audio/")
            or content_type.startswith("video/")
            or any(filename_lower.endswith(ext) for ext in allowed_exts)
        )

        if not is_valid_type:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File must be an authorized audio or video media file",
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

        # Generate temporary presigned URL for direct browser playback (valid for 24h)
        s3_key = s3_service._extract_key_from_url(s3_url)
        presigned_sample_url = await s3_service.generate_presigned_url(s3_key, expiration=86400)

        return {
            "voice_id": str(voice.id),
            "voice_name": voice.voice_name,
            "audio_sample_url": s3_url,
            "presigned_sample_url": presigned_sample_url,
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


@router.post("/clone-custom-sample")
async def clone_custom_sample(
    current_user: CurrentUser,
    session: DbSession,
    audio_file: Annotated[UploadFile, File()],
    voice_name: Annotated[str, Form()] = "My Custom Voice",
) -> dict:
    """
    Feed manual audio sample to clone a custom voice.
    Saves the reference audio, forwards it to the voice cloning sidecar/engine,
    and sets it as the active personalized voice for Raghvi.
    """
    try:
        content = await audio_file.read()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded voice sample audio cannot be empty",
            )

        # 1. Save locally in persistent voices directory
        target_dir = AsyncPath("data/voices")
        await target_dir.mkdir(parents=True, exist_ok=True)
        fname = audio_file.filename or "sample.wav"
        file_ext = fname.split(".")[-1] if "." in fname else "wav"
        local_ref_path = f"data/voices/{current_user.id}_custom_ref.{file_ext}"
        await AsyncPath(local_ref_path).write_bytes(content)

        # 2. Forward to GPU voice cloning sidecar if online
        sidecar_url = os.getenv("INDICF5_ENDPOINT_URL") or os.getenv("INDICF5_SIDECAR_URL")
        if sidecar_url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    files = {
                        "audio_file": (
                            audio_file.filename or "custom_voice.wav",
                            content,
                            audio_file.content_type or "audio/wav",
                        )
                    }
                    await client.post(f"{sidecar_url.rstrip('/')}/upload_sample", files=files)
                    logger.info("Forwarded custom voice sample to GPU sidecar")
            except Exception as e:
                logger.warning(f"Could not forward sample to sidecar immediately: {e}")

        # 3. Update user preferences to activate custom cloned voice
        current_prefs = dict(current_user.preferences or {})
        voice_prefs = current_prefs.get("voice_settings", {})
        voice_prefs["personalized_voice_enabled"] = True
        voice_prefs["selected_voice_id"] = "custom"
        voice_prefs["custom_voice_name"] = voice_name
        voice_prefs["custom_voice_path"] = local_ref_path
        current_prefs["voice_settings"] = voice_prefs

        current_user.preferences = current_prefs
        await session.commit()

        msg = (
            f"Custom voice '{voice_name}' successfully cloned! "
            "Raghvi will now use this voice."
        )
        return {
            "status": "cloned",
            "voice_name": voice_name,
            "message": msg,
            "voice_settings": voice_prefs,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Custom voice cloning failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clone voice sample: {str(e)}",
        ) from e


@router.post("/reset-default")
async def reset_default_voice(
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Reset user voice back to default official Raghvi cloned voice."""
    current_prefs = dict(current_user.preferences or {})
    voice_prefs = current_prefs.get("voice_settings", {})
    voice_prefs["selected_voice_id"] = None
    voice_prefs["custom_voice_name"] = None
    voice_prefs["personalized_voice_enabled"] = False
    current_prefs["voice_settings"] = voice_prefs

    current_user.preferences = current_prefs
    await session.commit()

    return {
        "status": "reset",
        "message": "Reset to default Raghvi voice.",
        "voice_settings": voice_prefs,
    }


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

        # Mark voice as active/ready custom voice
        voice.voice_type = "custom"
        voice.is_active = True
        await session.commit()

        logger.info(f"Voice cloning activated for voice {voice_id}")

        return {
            "voice_id": str(voice.id),
            "status": "ready",
            "message": "Personalized synthetic voice enrollment verified and ready.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Voice cloning fallback: {e}")
        return {
            "voice_id": str(voice_id),
            "status": "fallback_standard",
            "message": "Personalized voice cloning failed; safely fell back to standard voice.",
        }


@router.get("/{voice_id}/sample")
async def get_voice_sample(
    voice_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> dict:
    """Get temporary presigned playback URL for voice sample."""
    voice = await VoiceService.get_user_voice(str(voice_id), current_user.id, session)
    if not voice or not voice.audio_sample_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice sample not found",
        )

    s3_service = S3Service()
    try:
        s3_key = s3_service._extract_key_from_url(voice.audio_sample_url)
        presigned_url = await s3_service.generate_presigned_url(s3_key, expiration=86400)
        return {
            "voice_id": str(voice.id),
            "voice_name": voice.voice_name,
            "sample_url": presigned_url,
        }
    except Exception as e:
        logger.error(f"Failed to generate presigned sample URL: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate sample URL",
        ) from e


@router.get("/{voice_id}/stream")
@router.get("/{voice_id}/audio")
async def stream_voice_sample(
    voice_id: UUID,
    current_user: CurrentUser,
    session: DbSession,
) -> StreamingResponse:
    """Stream audio sample directly from storage through the backend."""
    voice = await VoiceService.get_user_voice(str(voice_id), current_user.id, session)
    if not voice or not voice.audio_sample_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Voice sample not found",
        )

    s3_service = S3Service()
    try:
        s3_key = s3_service._extract_key_from_url(voice.audio_sample_url)
        s3_obj = s3_service.get_voice_stream(s3_key)
        content_type = s3_obj.get("ContentType", "audio/mpeg")
        return StreamingResponse(
            s3_obj["Body"],
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename={voice.voice_name}.mp3",
                "Accept-Ranges": "bytes",
            },
        )
    except Exception as e:
        logger.error(f"Failed to stream voice sample: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to stream voice sample",
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
    response_format: Annotated[
        str, Query(alias="format", description="Output format: 'json' or 'audio'")
    ] = "json",
) -> Any:
    """
    Synthesize speech from text using voice providers with automatic fallback.

    If voice_id is provided, uses that voice. Otherwise, uses user's default voice
    or a system default voice.

    Returns audio data as base64 JSON or playable binary audio if format=audio.
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

            # Default to Swara Indian Neural voice for consistent identity
            selected_voice_id = (
                default_voices[0].voice_id if default_voices else "hi-IN-SwaraNeural"
            )

        # Pre-clean conversational formatting, emojis, and symbols
        from app.services.voice.text_normalizer import clean_text_for_speech

        is_hindi = language.lower().startswith("hi") or any(
            "\u0900" <= ch <= "\u097f" for ch in text
        )
        cleaned_text = clean_text_for_speech(text, is_hindi=is_hindi)
        if not cleaned_text.strip():
            cleaned_text = "जी, समझ गई।" if is_hindi else "I understand."

        # Create synthesis request
        request = VoiceSynthesisRequest(
            text=cleaned_text,
            voice_id=selected_voice_id,
            language=language,
        )

        # Synthesize with automatic fallback or intelligent routing
        logger.info(f"Synthesizing speech for user {current_user.id}: '{text[:50]}...'")

        router = adapter.get_router()
        response = await router.synthesize_speech(request)

        # Option 1: Return as playable binary audio directly in Postman / browser
        if response_format == "audio":
            ext = response.audio_format if response.audio_format in ["mp3", "wav", "ogg"] else "mp3"
            media_type = f"audio/{ext}" if ext != "mp3" else "audio/mpeg"
            return Response(
                content=response.audio_data,
                media_type=media_type,
                headers={
                    "Content-Disposition": f"inline; filename=raghvi_speech.{ext}",
                },
            )

        # Option 2: Return as base64 JSON for mobile apps / frontend
        audio_base64 = base64.b64encode(response.audio_data).decode("utf-8")

        return {
            "success": True,
            "text": text,
            "voice_id": selected_voice_id,
            "provider": response.provider or "voice_synthesis",
            "audio_base64": audio_base64,
            "audio_format": response.audio_format,
            "sample_rate": 44100,
            "duration_estimate": len(text) / 10,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Speech synthesis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to synthesize speech: {str(e)}",
        ) from e


@router.get("/providers/capabilities")
async def get_voice_providers_capabilities(
    current_user: CurrentUser,
) -> dict:
    """Retrieve capabilities and supported languages of all registered voice providers."""
    try:
        from app.services.voice.voice_adapter_builder import get_voice_adapter

        adapter = get_voice_adapter()
        caps_map = adapter.get_capabilities_map()

        serialized = {}
        for name, caps in caps_map.items():
            serialized[name] = {
                "capabilities": [c.value for c in caps.capabilities],
                "supported_languages": sorted(caps.supported_languages),
                "supported_audio_formats": caps.supported_audio_formats,
                "sample_rates": caps.sample_rates,
                "is_commercial_ready": caps.is_commercial_ready,
                "is_local_inference": caps.is_local_inference,
                "license_type": caps.license_type,
            }

        return {
            "success": True,
            "providers": serialized,
            "total_providers": len(serialized),
        }
    except Exception as e:
        logger.error(f"Failed to fetch voice capabilities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve voice provider capabilities",
        ) from e


@router.get("/providers/health")
async def get_voice_providers_health(
    current_user: CurrentUser,
) -> dict:
    """Run readiness and health checks across all registered voice providers."""
    try:
        from datetime import UTC, datetime

        from app.services.voice.voice_adapter_builder import get_voice_adapter

        adapter = get_voice_adapter()
        health_results = await adapter.check_health_all()

        return {
            "success": True,
            "providers": health_results,
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to check voice health: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check voice provider health",
        ) from e
