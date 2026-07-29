"""Voice service — manage user voices and speech synthesis."""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.subscription import UserSubscription
from app.models.voice import SystemVoice, UserVoice
from app.services.voice.provider_factory import VoiceProviderFactory
from app.services.voice.providers.base import (
    VoiceCloneRequest,
    VoiceProviderError,
    VoiceSynthesisRequest,
)

logger = logging.getLogger(__name__)


class VoiceService:
    """Manage user voices and speech synthesis."""

    @staticmethod
    async def create_user_voice(
        user_id: str,
        voice_type: str,
        voice_id: str,
        voice_name: str,
        provider: str,
        languages: str = "en",
        subscription_plan_id: str | None = None,
        expires_at: datetime | None = None,
        audio_sample_url: str | None = None,
        session: AsyncSession = None,
    ) -> UserVoice:
        """Create a new user voice."""

        voice = UserVoice(
            user_id=user_id,
            voice_type=voice_type,
            voice_id=voice_id,
            voice_name=voice_name,
            provider=provider,
            languages=languages,
            subscription_plan_id=subscription_plan_id,
            expires_at=expires_at,
            audio_sample_url=audio_sample_url,
        )

        session.add(voice)
        await session.commit()

        logger.info(f"Created voice for user {user_id}: {voice_name}")

        return voice

    @staticmethod
    async def get_user_voices(
        user_id: str,
        session: AsyncSession,
        include_expired: bool = False,
    ) -> list[UserVoice]:
        """Get all user voices."""

        query = select(UserVoice).where(
            and_(
                UserVoice.user_id == user_id,
                UserVoice.deleted_at.is_(None),
            )
        )

        if not include_expired:
            now = datetime.utcnow()
            query = query.where((UserVoice.expires_at.is_(None)) | (UserVoice.expires_at > now))

        voices = await session.scalars(query)
        return voices.all()

    @staticmethod
    async def get_user_voice(
        voice_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> UserVoice | None:
        """Get a specific user voice."""

        return await session.scalar(
            select(UserVoice).where(
                and_(
                    UserVoice.id == voice_id,
                    UserVoice.user_id == user_id,
                    UserVoice.deleted_at.is_(None),
                )
            )
        )

    @staticmethod
    async def set_default_voice(
        voice_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> None:
        """Set a voice as default for user."""

        # Unset all other default voices for this user
        voices = await VoiceService.get_user_voices(user_id, session)

        for voice in voices:
            voice.is_default = False

        # Set new default
        voice = await VoiceService.get_user_voice(voice_id, user_id, session)

        if not voice:
            raise ValueError("Voice not found")

        voice.is_default = True
        voice.is_active = True

        await session.commit()

        logger.info(f"Set default voice for user {user_id}: {voice.voice_name}")

    @staticmethod
    async def delete_user_voice(
        voice_id: str,
        user_id: str,
        session: AsyncSession,
    ) -> None:
        """Soft delete a user voice."""

        voice = await VoiceService.get_user_voice(voice_id, user_id, session)

        if not voice:
            raise ValueError("Voice not found")

        voice.deleted_at = datetime.utcnow()
        voice.is_active = False

        await session.commit()

        logger.info(f"Deleted voice for user {user_id}: {voice.voice_name}")

    @staticmethod
    async def expire_user_voices(
        user_id: str,
        session: AsyncSession,
    ) -> int:
        """Expire all custom voices for a user (on subscription downgrade)."""

        voices = await session.scalars(
            select(UserVoice).where(
                and_(
                    UserVoice.user_id == user_id,
                    UserVoice.voice_type == "custom",
                    UserVoice.expires_with_subscription.is_(True),
                    UserVoice.deleted_at.is_(None),
                )
            )
        )

        count = 0
        now = datetime.utcnow()

        for voice in voices.all():
            voice.expires_at = now
            voice.is_active = False
            count += 1

        if count > 0:
            await session.commit()

        logger.info(f"Expired {count} voices for user {user_id}")

        return count

    @staticmethod
    async def get_system_voices(
        session: AsyncSession,
        language: str | None = None,
    ) -> list[SystemVoice]:
        """Get system voices."""

        query = select(SystemVoice).where(SystemVoice.is_active.is_(True))

        if language:
            query = query.where(SystemVoice.language == language)

        voices = await session.scalars(query)
        return voices.all()

    @staticmethod
    async def clone_voice(
        user_id: str,
        voice_name: str,
        audio_file_path: str,
        provider_name: str,
        provider_config: dict[str, Any],
        session: AsyncSession,
    ) -> UserVoice:
        """Clone a voice for a user."""

        # Check subscription allows custom voices
        subscription = await session.scalar(
            select(UserSubscription).where(
                and_(
                    UserSubscription.user_id == user_id,
                    UserSubscription.is_active.is_(True),
                )
            )
        )

        if not subscription:
            raise ValueError("No active subscription")

        # Create provider
        provider = VoiceProviderFactory.create_provider(provider_name, provider_config)

        # Clone voice
        request = VoiceCloneRequest(
            user_id=user_id,
            voice_name=voice_name,
            audio_file_path=audio_file_path,
        )

        try:
            response = await provider.clone_voice(request)

            # Create user voice record
            voice = await VoiceService.create_user_voice(
                user_id=user_id,
                voice_type="custom",
                voice_id=response.voice_id,
                voice_name=voice_name,
                provider=provider_name,
                subscription_plan_id=subscription.plan_id,
                expires_at=subscription.expires_at,
                audio_sample_url=response.audio_sample_url,
                session=session,
            )

            logger.info(f"Voice cloned for user {user_id}: {voice_name}")

            return voice

        except VoiceProviderError as e:
            logger.error(f"Voice cloning failed: {e}")
            raise

    @staticmethod
    async def synthesize_speech(
        text: str,
        voice_id: str,
        user_id: str,
        provider_name: str,
        provider_config: dict[str, Any],
        session: AsyncSession,
        language: str = "en",
    ) -> bytes:
        """Synthesize speech using a voice."""

        # Verify voice belongs to user
        voice = await VoiceService.get_user_voice(voice_id, user_id, session)

        if not voice:
            raise ValueError("Voice not found")

        if not voice.is_available:
            raise ValueError("Voice is not available (expired or deleted)")

        # Create provider
        provider = VoiceProviderFactory.create_provider(provider_name, provider_config)

        # Synthesize speech
        request = VoiceSynthesisRequest(
            text=text,
            voice_id=voice.voice_id,
            language=language,
        )

        try:
            response = await provider.synthesize_speech(request)

            logger.info(f"Speech synthesized for user {user_id}: {len(response.audio_data)} bytes")

            return response.audio_data

        except VoiceProviderError as e:
            logger.error(f"Speech synthesis failed: {e}")
            raise


def get_voice_service() -> VoiceService:
    """Get voice service instance."""
    return VoiceService()
