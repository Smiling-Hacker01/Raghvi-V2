"""Integration tests for Voice API endpoints and user voice settings."""

from io import BytesIO

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_and_update_voice_settings(client: AsyncClient, auth_headers: dict):
    """Test getting and updating voice settings."""
    # 1. Fetch initial defaults
    response = await client.get("/voices/settings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["voice_enabled"] is True
    assert data["allow_interruptions"] is True

    # 2. Update settings (disable voice, enable activation, change style)
    update_payload = {
        "voice_enabled": False,
        "speaking_style": "expressive",
        "allow_interruptions": False,
        "personalized_voice_enabled": False,
    }
    put_resp = await client.put("/voices/settings", json=update_payload, headers=auth_headers)
    assert put_resp.status_code == 200
    updated_data = put_resp.json()
    assert updated_data["voice_enabled"] is False
    assert updated_data["speaking_style"] == "expressive"
    assert updated_data["allow_interruptions"] is False
    assert updated_data["personalized_voice_enabled"] is False

    # 3. Verify settings persist on subsequent read
    get_again = await client.get("/voices/settings", headers=auth_headers)
    assert get_again.status_code == 200
    assert get_again.json()["voice_enabled"] is False


@pytest.mark.asyncio
async def test_upload_voice_requires_auth(client: AsyncClient):
    """Test uploading voice sample without authentication is rejected."""
    response = await client.post(
        "/voices/upload",
        data={"voice_name": "My Voice", "consent_confirmed": "true"},
        files={"audio_file": ("test.wav", BytesIO(b"fake audio data"), "audio/wav")},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_voice_requires_consent(client: AsyncClient, auth_headers: dict):
    """Test upload is rejected if consent_confirmed is missing or false."""
    response = await client.post(
        "/voices/upload",
        data={"voice_name": "Sample Without Consent", "consent_confirmed": "false"},
        files={"audio_file": ("sample.wav", BytesIO(b"sample bytes"), "audio/wav")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "Explicit user authorization and consent required" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_voice_rejects_invalid_media_format(client: AsyncClient, auth_headers: dict):
    """Test upload is rejected if file is not an allowed audio or video format."""
    response = await client.post(
        "/voices/upload",
        data={"voice_name": "Invalid File", "consent_confirmed": "true"},
        files={"audio_file": ("script.py", BytesIO(b"print('hello')"), "text/plain")},
        headers=auth_headers,
    )
    assert response.status_code == 400
    assert "authorized audio or video media file" in response.json()["detail"]


@pytest.mark.asyncio
async def test_list_system_voices(client: AsyncClient, auth_headers: dict):
    """Test retrieving system voices list."""
    response = await client.get("/voices/system", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "voices" in data
    assert "total" in data
