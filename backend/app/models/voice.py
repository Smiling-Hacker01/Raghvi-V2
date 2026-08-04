"""Voice models — user voices and system voices."""

from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Uuid

from app.db.base import Base, get_utc_now


class UserVoice(Base):
    """User's custom or selected voices."""

    __tablename__ = "user_voices"

    id = Column(Uuid, primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)

    # Voice type
    voice_type = Column(String(20), nullable=False)  # "system", "custom"

    # Voice info
    voice_id = Column(String(500), nullable=False)  # Provider's voice ID
    voice_name = Column(String(200), nullable=False)  # "My Voice", "Sarah"
    provider = Column(String(50), nullable=False)  # "elevenlabs", "coqui"

    # Languages
    languages = Column(String(100), nullable=False, default="en")  # "en,hi"

    # Status
    is_active = Column(Boolean, nullable=False, default=False)
    is_default = Column(Boolean, nullable=False, default=False)  # Fallback voice

    # Subscription tracking
    subscription_plan_id = Column(String(50), nullable=True)  # "pro", "premium"
    expires_with_subscription = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime, nullable=True)  # Expiration date

    # Audio sample
    audio_sample_url = Column(String(500), nullable=True)  # S3 URL
    audio_sample_duration = Column(Integer, nullable=True)  # Seconds

    # Metadata
    created_at = Column(DateTime, nullable=False, default=get_utc_now)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    __table_args__ = (
        Index("ix_user_voice_active", "user_id", "is_active"),
        Index("ix_user_voice_expires", "user_id", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<UserVoice user_id={self.user_id} name={self.voice_name} type={self.voice_type}>"

    @property
    def is_expired(self) -> bool:
        """Check if voice is expired."""
        if not self.expires_at:
            return False
        return get_utc_now() > self.expires_at

    @property
    def is_available(self) -> bool:
        """Check if voice is available (not deleted, not expired)."""
        return self.deleted_at is None and not self.is_expired


class SystemVoice(Base):
    """Default system voices (available to all users)."""

    __tablename__ = "system_voices"

    id = Column(String(50), primary_key=True)  # "en_system_default", "hi_system_default"

    # Voice info
    voice_name = Column(String(200), nullable=False)  # "Raghvi (English)", "रघवी (Hindi)"
    voice_id = Column(String(500), nullable=False)  # Provider's voice ID
    provider = Column(String(50), nullable=False)  # "elevenlabs"
    language = Column(String(10), nullable=False, index=True)  # "en", "hi"

    # Quality
    quality_score = Column(Float, nullable=True)  # 0.0-1.0

    # Metadata
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=get_utc_now)

    def __repr__(self) -> str:
        return f"<SystemVoice language={self.language} name={self.voice_name}>"
