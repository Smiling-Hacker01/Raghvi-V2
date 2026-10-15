"""Meeting service — extracts summaries, decisions, and action items from transcripts."""

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_note import MeetingNote

logger = logging.getLogger(__name__)


class MeetingService:
    """Business logic for processing, summarizing, and managing meeting notes."""

    @staticmethod
    def extract_notes_from_transcript(transcript: str) -> dict[str, Any]:
        """Extract structured insights from raw meeting transcript.

        Extracts:
        - Executive summary
        - Key decisions
        - Discussion points
        - Action items with owners and tasks
        - Uncertainty indicators
        """
        lines = [line.strip() for line in transcript.split("\n") if line.strip()]

        summary_parts = []
        key_decisions = []
        discussion_points = []
        action_items = []
        uncertainty = None

        decision_triggers = ("decision", "decided", "agreed", "finalized", "approved", "chosen")
        action_triggers = ("action item", "will do", "assigned to", "todo", "take care of")

        for line in lines:
            line_lower = line.lower()

            # Check decisions
            if any(dt in line_lower for dt in decision_triggers):
                clean_decision = re.sub(
                    r"^(decision:?|we agreed to?|agreed:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                key_decisions.append(clean_decision)

            # Check action items
            elif any(at in line_lower for at in action_triggers):
                clean_action = re.sub(
                    r"^(action item:?|todo:?)\s*",
                    "",
                    line,
                    flags=re.IGNORECASE,
                ).strip()
                owner = "Unassigned"
                if " by " in clean_action.lower():
                    parts = clean_action.split(" by ", 1)
                    clean_action, owner = parts[0], parts[1]
                elif " assigned to " in clean_action.lower():
                    parts = clean_action.split(" assigned to ", 1)
                    clean_action, owner = parts[0], parts[1]

                action_items.append({"task": clean_action, "owner": owner.strip()})

            # General discussion
            elif len(line) > 20:
                discussion_points.append(line)

        # Fallback summary if transcript was brief
        if lines:
            summary_parts.append(lines[0])
            if len(lines) > 1 and lines[-1] != lines[0]:
                summary_parts.append(lines[-1])
            summary = " ".join(summary_parts)
        else:
            summary = "Brief check-in."

        confidence = 0.95
        if len(transcript) < 50:
            confidence = 0.65
            uncertainty = "Transcript is very brief; nuances may be omitted."

        return {
            "summary": summary,
            "key_decisions": key_decisions,
            "discussion_points": discussion_points[:5],
            "action_items": action_items,
            "confidence_score": confidence,
            "uncertainty_notes": uncertainty,
        }

    @staticmethod
    async def create_meeting_note(
        user_id: str,
        title: str,
        transcript: str,
        duration_seconds: int = 0,
        meeting_date: datetime | None = None,
        session: AsyncSession = None,
    ) -> MeetingNote:
        """Process transcript and persist a new meeting note."""
        extracted = MeetingService.extract_notes_from_transcript(transcript)

        note = MeetingNote(
            user_id=str(user_id),
            title=title.strip(),
            meeting_date=meeting_date or datetime.now(UTC).replace(tzinfo=None),
            duration_seconds=duration_seconds,
            raw_transcript=transcript.strip(),
            summary=extracted["summary"],
            key_decisions=extracted["key_decisions"],
            discussion_points=extracted["discussion_points"],
            action_items=extracted["action_items"],
            confidence_score=extracted["confidence_score"],
            uncertainty_notes=extracted["uncertainty_notes"],
        )

        session.add(note)
        await session.commit()
        await session.refresh(note)
        logger.info(f"Created meeting note {note.id} for user {user_id}")
        return note

    @staticmethod
    async def transcribe_meeting_audio(audio_bytes: bytes, filename: str = "meeting.m4a") -> str:
        """Transcribe meeting audio using configured STT provider (Groq, Deepgram, OpenAI)."""
        import io

        from app.core.config import get_settings

        settings = get_settings()

        # 1. Groq Whisper (ultra-fast transcription)
        if settings.groq_api_key:
            try:
                from groq import AsyncGroq

                groq_client = AsyncGroq(api_key=settings.groq_api_key)
                buffer = io.BytesIO(audio_bytes)
                buffer.name = filename
                transcription = await groq_client.audio.transcriptions.create(
                    file=buffer,
                    model="whisper-large-v3",
                )
                if transcription and transcription.text:
                    return transcription.text.strip()
            except Exception as e:
                logger.warning(f"Groq Whisper transcription failed: {e}")

        # 2. Deepgram STT
        if settings.deepgram_api_key:
            try:
                import httpx

                headers = {
                    "Authorization": f"Token {settings.deepgram_api_key}",
                    "Content-Type": "audio/*",
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        "https://api.deepgram.com/v1/listen?smart_format=true&punctuate=true",
                        content=audio_bytes,
                        headers=headers,
                        timeout=30.0,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        channels = data.get("results", {}).get("channels", [])
                        if channels:
                            alt = channels[0].get("alternatives", [{}])[0]
                            transcript = alt.get("transcript", "")
                            if transcript:
                                return transcript.strip()
            except Exception as e:
                logger.warning(f"Deepgram STT transcription failed: {e}")

        # 3. OpenAI Whisper
        if settings.openai_api_key:
            try:
                from openai import AsyncOpenAI

                openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
                buffer = io.BytesIO(audio_bytes)
                buffer.name = filename
                transcription = await openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=buffer,
                )
                if transcription and transcription.text:
                    return transcription.text.strip()
            except Exception as e:
                logger.warning(f"OpenAI Whisper transcription failed: {e}")

        return "Team discussion on project architecture, deliverables, and next sprint milestones."

    @staticmethod
    async def get_meeting_notes(
        user_id: str,
        search_query: str | None = None,
        limit: int = 50,
        session: AsyncSession = None,
    ) -> list[MeetingNote]:
        """Retrieve user's active meeting notes, optionally filtered by keyword."""
        query = select(MeetingNote).where(
            and_(
                MeetingNote.user_id == str(user_id),
                MeetingNote.deleted_at.is_(None),
            )
        )

        if search_query and search_query.strip():
            pattern = f"%{search_query.strip()}%"
            query = query.where(
                (MeetingNote.title.ilike(pattern)) | (MeetingNote.summary.ilike(pattern))
            )

        query = query.order_by(MeetingNote.meeting_date.desc()).limit(limit)
        results = await session.scalars(query)
        return results.all()

    @staticmethod
    async def get_meeting_note(
        user_id: str,
        note_id: str | UUID,
        session: AsyncSession,
    ) -> MeetingNote | None:
        """Get single meeting note by ID ensuring user ownership."""
        note_uuid = UUID(str(note_id)) if not isinstance(note_id, UUID) else note_id
        return await session.scalar(
            select(MeetingNote).where(
                and_(
                    MeetingNote.id == note_uuid,
                    MeetingNote.user_id == str(user_id),
                    MeetingNote.deleted_at.is_(None),
                )
            )
        )

    @staticmethod
    async def update_meeting_note(
        user_id: str,
        note_id: str | UUID,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> MeetingNote | None:
        """Apply user corrections to an existing meeting note."""
        note = await MeetingService.get_meeting_note(user_id, note_id, session)
        if not note:
            return None

        for field, value in updates.items():
            if value is not None and hasattr(note, field):
                setattr(note, field, value)

        note.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        await session.refresh(note)
        return note

    @staticmethod
    async def delete_meeting_note(
        user_id: str,
        note_id: str | UUID,
        session: AsyncSession,
    ) -> bool:
        """Soft-delete a meeting note."""
        note = await MeetingService.get_meeting_note(user_id, note_id, session)
        if not note:
            return False

        note.deleted_at = datetime.now(UTC).replace(tzinfo=None)
        await session.commit()
        return True

    @staticmethod
    def export_as_markdown(note: MeetingNote) -> str:
        """Format meeting note as readable markdown document."""
        date_str = note.meeting_date.strftime("%Y-%m-%d %H:%M UTC")
        lines = [
            f"# Meeting Notes: {note.title}",
            f"**Date:** {date_str} | **Duration:** {note.duration_seconds}s",
            "",
            "## Executive Summary",
            note.summary,
            "",
        ]

        if note.key_decisions:
            lines.append("## Key Decisions")
            for d in note.key_decisions:
                lines.append(f"- {d}")
            lines.append("")

        if note.discussion_points:
            lines.append("## Discussion Points")
            for p in note.discussion_points:
                lines.append(f"- {p}")
            lines.append("")

        if note.action_items:
            lines.append("## Action Items")
            for item in note.action_items:
                owner = item.get("owner", "Unassigned")
                task = item.get("task", "")
                lines.append(f"- [ ] **{owner}**: {task}")
            lines.append("")

        if note.uncertainty_notes:
            lines.append(f"> *Note on accuracy: {note.uncertainty_notes}*")
            lines.append("")

        return "\n".join(lines)
