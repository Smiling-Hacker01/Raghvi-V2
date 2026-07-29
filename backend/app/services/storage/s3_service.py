"""S3 storage service for voice samples and audio files."""

import logging
from datetime import datetime, timedelta
from io import BytesIO
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class S3Service:
    """Service for managing file uploads to S3."""

    def __init__(self):
        """Initialize S3 client."""
        settings = get_settings()
        self.bucket_name = settings.s3_bucket
        self.voice_prefix = settings.s3_voice_prefix
        self.region = settings.s3_region

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            region_name=self.region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

        logger.info(f"S3 service initialized for bucket: {self.bucket_name}")

    async def upload_voice_sample(
        self,
        user_id: str,
        voice_id: str,
        audio_data: bytes | BinaryIO,
        file_extension: str = "wav",
    ) -> str:
        """
        Upload voice sample to S3.

        Args:
            user_id: User ID
            voice_id: Voice ID
            audio_data: Audio file data (bytes or file-like object)
            file_extension: File extension (wav, mp3, etc.)

        Returns:
            S3 URL of uploaded file
        """
        try:
            # Generate S3 key
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"{self.voice_prefix}{user_id}/{voice_id}_{timestamp}.{file_extension}"

            # Convert bytes to file-like object if needed
            if isinstance(audio_data, bytes):
                audio_data = BytesIO(audio_data)

            # Upload to S3
            self.s3_client.upload_fileobj(
                audio_data,
                self.bucket_name,
                s3_key,
                ExtraArgs={
                    "ContentType": f"audio/{file_extension}",
                    "Metadata": {
                        "user_id": user_id,
                        "voice_id": str(voice_id),
                        "uploaded_at": datetime.utcnow().isoformat(),
                    },
                },
            )

            # Generate URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"

            logger.info(f"Voice sample uploaded: {url}")

            return url

        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise ValueError(f"Failed to upload to S3: {e}") from e

    async def generate_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600,
    ) -> str:
        """
        Generate presigned URL for temporary access.

        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned URL
        """
        try:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )

            logger.info(f"Generated presigned URL for: {s3_key}")

            return url

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise ValueError(f"Failed to generate presigned URL: {e}") from e

    async def delete_voice_sample(self, s3_url: str) -> bool:
        """
        Delete voice sample from S3.

        Args:
            s3_url: Full S3 URL of the file

        Returns:
            True if deleted successfully
        """
        try:
            # Extract key from URL
            s3_key = self._extract_key_from_url(s3_url)

            # Delete from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)

            logger.info(f"Voice sample deleted: {s3_key}")

            return True

        except ClientError as e:
            logger.error(f"S3 delete failed: {e}")
            return False

    def _extract_key_from_url(self, s3_url: str) -> str:
        """Extract S3 key from full URL."""
        # URL format: https://bucket.s3.region.amazonaws.com/key
        parts = s3_url.split(".amazonaws.com/")
        if len(parts) == 2:
            return parts[1]
        raise ValueError(f"Invalid S3 URL format: {s3_url}")

    async def get_file_metadata(self, s3_key: str) -> dict:
        """
        Get file metadata from S3.

        Args:
            s3_key: S3 object key

        Returns:
            Metadata dictionary
        """
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)

            return {
                "content_type": response.get("ContentType"),
                "content_length": response.get("ContentLength"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }

        except ClientError as e:
            logger.error(f"Failed to get file metadata: {e}")
            raise ValueError(f"Failed to get file metadata: {e}") from e


def get_s3_service() -> S3Service:
    """Get S3 service instance."""
    return S3Service()
