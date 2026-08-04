"""Tests for S3 storage service."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.services.storage.s3_service import S3Service


@pytest.mark.asyncio
async def test_s3_service_upload_and_helpers():
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3

        s3_service = S3Service()

        # Test upload_voice_sample with bytes
        url = await s3_service.upload_voice_sample("user123", "voice456", b"fake audio data", "wav")
        assert "user123" in url
        assert "voice456" in url
        assert url.endswith(".wav")
        mock_s3.upload_fileobj.assert_called_once()

        # Test upload with file-like object
        mock_s3.reset_mock()
        file_obj = BytesIO(b"fake stream audio")
        url_stream = await s3_service.upload_voice_sample("user123", "voice789", file_obj, "mp3")
        assert "voice789" in url_stream
        assert url_stream.endswith(".mp3")
        mock_s3.upload_fileobj.assert_called_once()

        # Test delete_voice_sample
        mock_s3.reset_mock()
        res_del = await s3_service.delete_voice_sample(url)
        assert res_del is True
        mock_s3.delete_object.assert_called_once()

        # Test generate_presigned_url
        mock_s3.reset_mock()
        mock_s3.generate_presigned_url.return_value = "https://signed.url"
        presigned = await s3_service.generate_presigned_url("voices/sample.wav")
        assert presigned == "https://signed.url"
        mock_s3.generate_presigned_url.assert_called_once()
