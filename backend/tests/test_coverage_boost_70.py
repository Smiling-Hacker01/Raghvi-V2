"""Targeted tests to push total backend test coverage well above 70% threshold."""

import base64
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.action import ActionProposal
from app.models.communication import CommunicationItem
from app.services.action_service import ActionService
from app.services.communication_service import CommunicationService
from app.services.google_oauth_service import GoogleOAuthService
from app.services.meeting_service import MeetingService
from app.services.voice.providers.base import (
    VoiceCloneRequest,
    VoiceSynthesisRequest,
)
from app.services.voice.providers.edge_tts_provider import (
    EdgeTTSProvider,
    VoiceProviderError,
)

# ---------------------------------------------------------------------------
# 1. EdgeTTSProvider Coverage
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edge_tts_provider_init_and_cloning_error():
    provider = EdgeTTSProvider(
        {
            "hindi_voice": "hi-IN-SwaraNeural",
            "english_voice": "en-IN-NeerjaNeural",
            "rate": "-10%",
        }
    )
    assert provider.default_hindi_voice == "hi-IN-SwaraNeural"
    assert provider.default_english_voice == "en-IN-NeerjaNeural"

    with pytest.raises(VoiceProviderError, match="does not support instant voice cloning"):
        await provider.clone_voice(
            VoiceCloneRequest(
                user_id="u1",
                voice_name="custom",
                audio_file_path="sample.wav",
            )
        )


@pytest.mark.asyncio
async def test_edge_tts_synthesis_hindi_and_hinglish():
    provider = EdgeTTSProvider({})

    mock_communicate = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"hindi_audio_chunk"}

    mock_communicate.stream = mock_stream

    with patch(
        "app.services.voice.providers.edge_tts_provider.edge_tts.Communicate",
        return_value=mock_communicate,
    ):
        # 1. Devanagari text
        req_devanagari = VoiceSynthesisRequest(
            text="नमस्ते, आप कैसे हैं?",
            voice_id="default",
        )
        res1 = await provider.synthesize_speech(req_devanagari)
        assert res1.audio_data == b"hindi_audio_chunk"
        assert res1.audio_format == "mp3"

        # 2. Hinglish text
        req_hinglish = VoiceSynthesisRequest(
            text="Hello Raghvi, main theek hoon yaar",
            voice_id="default",
        )
        res2 = await provider.synthesize_speech(req_hinglish)
        assert res2.audio_data == b"hindi_audio_chunk"


@pytest.mark.asyncio
async def test_edge_tts_synthesis_english_and_emotions():
    provider = EdgeTTSProvider({})

    mock_communicate = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"english_audio_chunk"}

    mock_communicate.stream = mock_stream

    with patch(
        "app.services.voice.providers.edge_tts_provider.edge_tts.Communicate",
        return_value=mock_communicate,
    ):
        req_en = VoiceSynthesisRequest(
            text="Hello Raghvi, let's sync up today",
            voice_id="default",
            emotion="excited",
        )
        res = await provider.synthesize_speech(req_en)
        assert res.audio_data == b"english_audio_chunk"


@pytest.mark.asyncio
async def test_edge_tts_voice_routing_and_fallbacks():
    provider = EdgeTTSProvider({})

    mock_communicate = MagicMock()

    async def mock_stream():
        yield {"type": "audio", "data": b"audio_bytes"}

    mock_communicate.stream = mock_stream

    with patch(
        "app.services.voice.providers.edge_tts_provider.edge_tts.Communicate",
        return_value=mock_communicate,
    ):
        # UUID voice id fallback
        req_uuid = VoiceSynthesisRequest(
            text="Testing generic voice id",
            voice_id="12345678-1234-5678-1234-567812345678",
        )
        res = await provider.synthesize_speech(req_uuid)
        assert res.audio_data == b"audio_bytes"

        # Direct Edge TTS neural voice
        req_direct = VoiceSynthesisRequest(
            text="Testing direct voice",
            voice_id="en-IN-PrabhatNeural",
        )
        res_direct = await provider.synthesize_speech(req_direct)
        assert res_direct.audio_data == b"audio_bytes"

        # Third-party voice ID -> delegate
        req_third_party = VoiceSynthesisRequest(
            text="Custom cloned voice",
            voice_id="custom_elevenlabs_voice_123",
        )
        with pytest.raises(VoiceProviderError, match="Delegating to next voice provider"):
            await provider.synthesize_speech(req_third_party)


@pytest.mark.asyncio
async def test_edge_tts_list_voices():
    provider = EdgeTTSProvider({})
    voices = await provider.list_voices()
    assert len(voices) >= 3
    assert any(v["voice_id"] == "hi-IN-SwaraNeural" for v in voices)
    assert any(v["voice_id"] == "en-IN-NeerjaNeural" for v in voices)


# ---------------------------------------------------------------------------
# 2. GoogleOAuthService Coverage
# ---------------------------------------------------------------------------


def test_google_oauth_state_generation_and_validation():
    user_id = str(uuid4())
    state = GoogleOAuthService.create_oauth_state(user_id, "Personal Gmail")
    assert state is not None

    extracted_user, label = GoogleOAuthService.verify_oauth_state(state)
    assert extracted_user == user_id
    assert label == "Personal Gmail"

    # Tampered state
    with pytest.raises(ValueError):
        GoogleOAuthService.verify_oauth_state(state[:-4] + "abcd")

    # Empty state
    with pytest.raises(ValueError):
        GoogleOAuthService.verify_oauth_state("")

    # Malformed state
    with pytest.raises(ValueError):
        GoogleOAuthService.verify_oauth_state("invalid_string_part")


def test_google_oauth_auth_url():
    user_id = str(uuid4())
    url, state, configured = GoogleOAuthService.get_authorization_url(user_id, "Work")
    assert "accounts.google.com" in url
    assert "state=" in url
    assert "scope=" in url
    assert isinstance(configured, bool)


@pytest.mark.asyncio
async def test_google_oauth_missing_credentials_checks():
    with patch("app.services.google_oauth_service.get_settings") as mock_settings:
        mock_settings.return_value.google_oauth_client_id = None
        mock_settings.return_value.google_oauth_client_secret = None

        with pytest.raises(ValueError, match="not configured"):
            await GoogleOAuthService.exchange_auth_code("code_123")

        with pytest.raises(ValueError, match="missing for token refresh"):
            await GoogleOAuthService.refresh_access_token("refresh_123")


@pytest.mark.asyncio
async def test_google_oauth_http_calls():
    # Mock aiohttp client session for token exchange and userinfo
    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.json = AsyncMock(
        return_value={
            "access_token": "ya29.mock_token",
            "refresh_token": "1//refresh_xyz",
            "expires_in": 3600,
            "email": "user@gmail.com",
            "name": "Test User",
        }
    )
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=None)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.get = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    with patch("aiohttp.ClientSession", return_value=mock_session):
        tokens = await GoogleOAuthService.exchange_auth_code("code_abc")
        assert tokens["access_token"] == "ya29.mock_token"

        userinfo = await GoogleOAuthService.get_google_userinfo("ya29.mock_token")
        assert userinfo["email"] == "user@gmail.com"

        refreshed = await GoogleOAuthService.refresh_access_token("1//refresh_xyz")
        assert refreshed == "ya29.mock_token"


@pytest.mark.asyncio
async def test_google_oauth_sync_emails_flow():
    user_id = str(uuid4())
    account_id = uuid4()
    mock_db = AsyncMock()
    mock_db.scalar = AsyncMock(return_value=None)

    # Mock refresh token
    with patch.object(
        GoogleOAuthService, "refresh_access_token", AsyncMock(return_value="ya29.fresh")
    ):
        # Mock aiohttp
        mock_list_resp = AsyncMock()
        mock_list_resp.status = 200
        mock_list_resp.json = AsyncMock(return_value={"messages": [{"id": "m1"}]})
        mock_list_resp.__aenter__ = AsyncMock(return_value=mock_list_resp)
        mock_list_resp.__aexit__ = AsyncMock(return_value=None)

        msg_body = base64.urlsafe_b64encode(b"Meeting at 4pm").decode("utf-8")
        mock_msg_resp = AsyncMock()
        mock_msg_resp.status = 200
        mock_msg_resp.json = AsyncMock(
            return_value={
                "id": "m1",
                "threadId": "t1",
                "snippet": "Meeting at 4pm",
                "payload": {
                    "headers": [
                        {"name": "subject", "value": "Sync call"},
                        {"name": "from", "value": "Rahul <rahul@example.com>"},
                        {"name": "to", "value": "me@example.com"},
                    ],
                    "parts": [{"mimeType": "text/plain", "body": {"data": msg_body}}],
                },
            }
        )
        mock_msg_resp.__aenter__ = AsyncMock(return_value=mock_msg_resp)
        mock_msg_resp.__aexit__ = AsyncMock(return_value=None)

        mock_http = MagicMock()
        # First call gets list, second gets message detail
        mock_http.get = MagicMock(side_effect=[mock_list_resp, mock_msg_resp])
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)

        with patch("aiohttp.ClientSession", return_value=mock_http):
            items = await GoogleOAuthService.sync_emails_via_gmail_api(
                user_id=user_id,
                account_id=account_id,
                account_label="Work",
                refresh_token="ref123",
                session=mock_db,
                limit=5,
            )
            assert len(items) == 1
            assert items[0].subject == "Sync call"
            assert items[0].sender_name == "Rahul"


# ---------------------------------------------------------------------------
# 3. CommunicationService Coverage
# ---------------------------------------------------------------------------


def test_communication_draft_human_email_replies():
    target = CommunicationItem(
        id=uuid4(),
        user_id="user1",
        sender="boss@example.com",
        sender_name="Mr. Sharma",
        recipient="me@example.com",
        subject="Project status check",
        body="Can you please provide an update on the Q3 roadmap timeline?",
        channel="email",
    )

    # 1. Timeline query reply
    reply1 = CommunicationService.draft_human_email_reply(target, user_display_name="Vishal")
    assert "Hi Mr. Sharma" in reply1 or "Sharma" in reply1
    assert "on track" in reply1 or "draft" in reply1

    # 2. Meeting query reply
    target_meet = CommunicationItem(
        id=uuid4(),
        user_id="user1",
        sender="partner@example.com",
        sender_name="Pooja",
        recipient="me@example.com",
        subject="Sync call",
        body="Can we meet tomorrow for coffee or zoom sync?",
        channel="email",
    )
    reply2 = CommunicationService.draft_human_email_reply(target_meet, user_display_name="Vishal")
    assert "calendar invite" in reply2 or "timing" in reply2

    # 3. Custom instructions
    reply_custom = CommunicationService.draft_human_email_reply(
        target,
        user_instructions="Send them the deck directly",
        user_display_name="Vishal",
    )
    assert "Send them the deck directly" in reply_custom


def test_communication_draft_human_whatsapp_replies():
    items = [
        CommunicationItem(
            id=uuid4(),
            user_id="user1",
            sender="+919876543210",
            sender_name="Rahul",
            recipient="me",
            body="Bhai kahan ho? Kab tak pahuncho ge?",
            channel="whatsapp",
        )
    ]

    # Custom instruction
    reply = CommunicationService.draft_human_whatsapp_reply(
        recent_messages=items,
        user_instructions="Bas 10 minute mein aa raha hoon",
    )
    assert "10 minute" in reply

    # Automated contextual replies (kahan keyword)
    reply_kahan = CommunicationService.draft_human_whatsapp_reply(recent_messages=items)
    assert "nikal" in reply_kahan or "10 minute" in reply_kahan

    # Coffee / meet keywords
    items_meet = [
        CommunicationItem(
            id=uuid4(),
            user_id="user1",
            sender="+919876543210",
            sender_name="Rahul",
            recipient="me",
            body="Coffee pe milte hain shaam ko?",
            channel="whatsapp",
        )
    ]
    reply_meet = CommunicationService.draft_human_whatsapp_reply(recent_messages=items_meet)
    assert "milte" in reply_meet or "done" in reply_meet

    # Empty list fallback
    reply_empty = CommunicationService.draft_human_whatsapp_reply(recent_messages=[])
    assert "done" in reply_empty or "baat" in reply_empty


def test_communication_intent_parser():
    # Meeting intents
    intent_meeting = CommunicationService.parse_communication_intent(
        "Schedule meeting with team@example.com on Friday at 3 PM"
    )
    assert intent_meeting["type"] == "schedule_meeting"
    assert "team@example.com" in intent_meeting["attendees"]

    # Email search / check
    intent_email = CommunicationService.parse_communication_intent(
        "Check email from rahul in work account"
    )
    assert intent_email["type"] == "check_email"
    assert intent_email["account_label"] == "work"

    # WhatsApp check
    intent_wa = CommunicationService.parse_communication_intent(
        "Check new whatsapp message from Priya"
    )
    assert intent_wa["type"] == "check_whatsapp"

    # Non-communication casual message
    intent_none = CommunicationService.parse_communication_intent(
        "What is the weather in Delhi today?"
    )
    assert intent_none is None


def test_send_real_email_via_smtp():
    # 1. No credentials
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.email_user = None
        mock_settings.return_value.email_password = None
        ok = CommunicationService.send_real_email_via_smtp(
            recipient="test@example.com",
            subject="Test",
            body="Hello",
        )
        assert ok is False

    # 2. Success with mocked smtplib
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.email_smtp_host = "smtp.example.com"
        mock_settings.return_value.email_smtp_port = 465
        mock_settings.return_value.email_user = "sender@example.com"
        mock_settings.return_value.email_password = "password123"

        mock_server = MagicMock()
        with patch("smtplib.SMTP_SSL", return_value=mock_server):
            mock_server.__enter__.return_value = mock_server
            success = CommunicationService.send_real_email_via_smtp(
                recipient="test@example.com",
                subject="Test",
                body="Hello",
            )
            assert success is True
            mock_server.login.assert_called_once()
            mock_server.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_communication_send_meeting_invitations():
    user_id = str(uuid4())
    mock_session = AsyncMock()

    # Empty attendees
    res_empty = await CommunicationService.send_meeting_invitations(
        user_id=user_id,
        title="Quick Sync",
        date="2026-10-20",
        start_time="11:00 AM",
        attendees=[],
        session=mock_session,
    )
    assert res_empty["sent_to"] == []

    # Mock no connected oauth account and fallback to smtp
    mock_result = MagicMock()
    mock_result.all.return_value = []
    mock_session.scalars = AsyncMock(return_value=mock_result)

    with patch(
        "app.services.communication_service.CommunicationService.send_real_email_via_smtp",
        return_value=True,
    ):
        res = await CommunicationService.send_meeting_invitations(
            user_id=user_id,
            title="Sprint Planning",
            date="2026-10-20",
            start_time="11:00 AM",
            attendees=["team@example.com"],
            session=mock_session,
        )
        assert "team@example.com" in res["sent_to"]
        assert "meet_link" in res


# ---------------------------------------------------------------------------
# 4. ActionService Coverage
# ---------------------------------------------------------------------------


def test_action_service_validate_params():
    # Valid params
    ActionService.validate_action_params("draft_email", {"recipient": "test@example.com"})
    ActionService.validate_action_params(
        "schedule_meeting", {"title": "Sync", "date": "2026-10-20"}
    )
    ActionService.validate_action_params(
        "send_whatsapp_message", {"recipient": "9876543210", "message": "Hi"}
    )
    ActionService.validate_action_params("open_maps", {"destination": "Connaught Place"})
    ActionService.validate_action_params("open_app", {"package_name": "com.whatsapp"})

    # Invalid action type
    with pytest.raises(ValueError, match="Unsupported action type"):
        ActionService.validate_action_params("unsupported_action", {})

    # Invalid email
    with pytest.raises(ValueError, match="valid email address"):
        ActionService.validate_action_params("draft_email", {"recipient": "not_an_email"})

    # Missing meeting title or date
    with pytest.raises(ValueError, match="requires a title"):
        ActionService.validate_action_params("schedule_meeting", {"date": "2026-10-20"})
    with pytest.raises(ValueError, match="requires a date"):
        ActionService.validate_action_params("schedule_meeting", {"title": "Sync"})

    # Missing WhatsApp params
    with pytest.raises(ValueError, match="requires a recipient"):
        ActionService.validate_action_params("send_whatsapp_message", {"message": "Hi"})
    with pytest.raises(ValueError, match="requires a non-empty message"):
        ActionService.validate_action_params("send_whatsapp_message", {"recipient": "9876543210"})

    # Missing maps destination
    with pytest.raises(ValueError, match="destination"):
        ActionService.validate_action_params("open_maps", {})

    # Missing app package
    with pytest.raises(ValueError, match="package_name"):
        ActionService.validate_action_params("open_app", {})


@pytest.mark.asyncio
async def test_action_service_lifecycle_and_hooks():
    user_id = str(uuid4())
    mock_session = AsyncMock()

    # 1. Propose action
    proposal = await ActionService.propose_action(
        user_id=user_id,
        action_type="draft_email",
        parameters={"recipient": "test@example.com"},
        description="Draft test email",
        session=mock_session,
    )
    assert proposal.status == "awaiting_confirmation"
    assert proposal.action_type == "draft_email"

    # 2. Get proposal invalid UUID
    with pytest.raises(HTTPException) as exc_info:
        await ActionService.get_proposal(user_id, "invalid_uuid", mock_session)
    assert exc_info.value.status_code == 404

    # 3. Get proposal wrong user
    proposal.user_id = str(uuid4())
    mock_session.scalar = AsyncMock(return_value=proposal)
    with pytest.raises(HTTPException) as exc_info:
        await ActionService.get_proposal(user_id, str(proposal.id), mock_session)
    assert exc_info.value.status_code == 404

    # 4. Confirm meeting execution hook
    meeting_proposal = ActionProposal(
        id=uuid4(),
        user_id=user_id,
        action_type="schedule_meeting",
        parameters={"title": "Demo", "date": "2026-10-20", "attendees": ["test@example.com"]},
        status="awaiting_confirmation",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
    )
    mock_session.scalar = AsyncMock(return_value=meeting_proposal)

    with patch(
        "app.services.communication_service.CommunicationService.send_meeting_invitations",
        AsyncMock(return_value={"meet_link": "https://meet.google.com/abc-defg-hij"}),
    ):
        confirmed = await ActionService.confirm_action(
            user_id=user_id,
            proposal_id=str(meeting_proposal.id),
            confirmed=True,
            session=mock_session,
        )
        assert confirmed.status == "executed"
        assert confirmed.parameters["meet_link"] == "https://meet.google.com/abc-defg-hij"

    # 5. List proposals and filter
    mock_result = MagicMock()
    mock_result.all.return_value = [meeting_proposal]
    mock_session.scalars = AsyncMock(return_value=mock_result)

    proposals = await ActionService.list_proposals(
        user_id=user_id,
        status_filter="executed",
        session=mock_session,
    )
    assert len(proposals) == 1


# ---------------------------------------------------------------------------
# 5. MeetingService Coverage
# ---------------------------------------------------------------------------


def test_meeting_service_transcript_extraction():
    transcript = """
    Vishal: Good morning everyone.
    We decided to launch the feature on Monday.
    Deepali: I agree with that timeline.
    Action item: prepare release documentation assigned to Deepali
    Todo: review pull requests by Vishal
    General discussion on system performance and metrics.
    """
    notes = MeetingService.extract_notes_from_transcript(transcript)
    assert len(notes["key_decisions"]) >= 1
    assert any("launch the feature on Monday" in d for d in notes["key_decisions"])
    assert len(notes["action_items"]) == 2
    assert notes["action_items"][0]["owner"] == "Deepali"
    assert notes["action_items"][1]["owner"] == "Vishal"
    assert notes["confidence_score"] == 0.95


@pytest.mark.asyncio
async def test_meeting_service_transcription_providers():
    audio = b"fake_audio_bytes"

    # 1. Groq Whisper provider
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = "gsk_test"
        mock_settings.return_value.deepgram_api_key = None
        mock_settings.return_value.openai_api_key = None

        mock_groq = MagicMock()
        mock_transcription = MagicMock()
        mock_transcription.text = "Groq transcribed meeting"
        mock_groq.audio.transcriptions.create = AsyncMock(return_value=mock_transcription)

        with patch("groq.AsyncGroq", return_value=mock_groq):
            text = await MeetingService.transcribe_meeting_audio(audio)
            assert text == "Groq transcribed meeting"

    # 2. Deepgram STT provider
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = None
        mock_settings.return_value.deepgram_api_key = "dg_test"
        mock_settings.return_value.openai_api_key = None

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "results": {
                "channels": [{"alternatives": [{"transcript": "Deepgram transcribed meeting"}]}]
            }
        }
        with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
            text_dg = await MeetingService.transcribe_meeting_audio(audio)
            assert text_dg == "Deepgram transcribed meeting"

    # 3. Fallback when no keys configured
    with patch("app.core.config.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = None
        mock_settings.return_value.deepgram_api_key = None
        mock_settings.return_value.openai_api_key = None

        fallback_text = await MeetingService.transcribe_meeting_audio(audio)
        assert "Team discussion" in fallback_text


@pytest.mark.asyncio
async def test_meeting_service_crud():
    user_id = str(uuid4())
    mock_session = AsyncMock()

    # 1. Create meeting note
    note = await MeetingService.create_meeting_note(
        user_id=user_id,
        title="Weekly Sync",
        transcript="We decided to deploy. Action item: run tests by Deepali.",
        duration_seconds=120,
        session=mock_session,
    )
    note.id = uuid4()
    assert note.title == "Weekly Sync"
    assert note.user_id == user_id
    assert len(note.key_decisions) >= 1

    # 2. Get meeting notes
    mock_result = MagicMock()
    mock_result.all.return_value = [note]
    mock_session.scalars = AsyncMock(return_value=mock_result)

    notes = await MeetingService.get_meeting_notes(
        user_id=user_id,
        search_query="Weekly",
        session=mock_session,
    )
    assert len(notes) == 1

    # 3. Get by ID
    mock_session.scalar = AsyncMock(return_value=note)
    fetched = await MeetingService.get_meeting_note(
        user_id=user_id,
        note_id=str(note.id),
        session=mock_session,
    )
    assert fetched == note

    # 4. Update meeting note
    updated = await MeetingService.update_meeting_note(
        user_id=user_id,
        note_id=str(note.id),
        updates={"title": "Updated Weekly Sync", "summary": "All tests passed"},
        session=mock_session,
    )
    assert updated.title == "Updated Weekly Sync"
    assert updated.summary == "All tests passed"

    # 5. Export as markdown
    md = MeetingService.export_as_markdown(note)
    assert "Meeting Notes" in md
    assert "Executive Summary" in md

    # 6. Delete meeting note
    deleted = await MeetingService.delete_meeting_note(
        user_id=user_id,
        note_id=str(note.id),
        session=mock_session,
    )
    assert deleted is True
    assert note.deleted_at is not None
