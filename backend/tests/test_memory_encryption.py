"""Tests for encryption service."""

import pytest

from app.services.memory.encryption import (
    EncryptedData,
    EncryptionService,
    get_encryption_service,
)


class TestEncryptionService:
    """Tests for EncryptionService."""

    def test_encrypt_and_decrypt(self):
        """Test basic encrypt/decrypt cycle."""
        service = EncryptionService()
        plaintext = "My SSN: 123-45-6789"
        password = "UserPassword123"

        # Encrypt
        encrypted = service.encrypt(plaintext, password)

        # Decrypt
        decrypted = service.decrypt(encrypted, password)

        assert decrypted == plaintext

    def test_wrong_password_fails(self):
        """Test that wrong password fails decryption."""
        service = EncryptionService()
        plaintext = "Secret data"
        password1 = "Password1"
        password2 = "Password2"

        encrypted = service.encrypt(plaintext, password1)

        with pytest.raises(ValueError, match="wrong password"):
            service.decrypt(encrypted, password2)

    def test_tampered_ciphertext_fails(self):
        """Test that tampered data fails authentication."""
        service = EncryptionService()
        plaintext = "Sensitive"
        password = "MyPassword"

        encrypted = service.encrypt(plaintext, password)

        # Tamper with ciphertext
        tampered = EncryptedData(
            ciphertext=b"\x00" * len(encrypted.ciphertext),
            nonce=encrypted.nonce,
            salt=encrypted.salt,
            tag=encrypted.tag,
        )

        with pytest.raises(ValueError):
            service.decrypt(tampered, password)

    def test_encrypt_to_storage_and_back(self):
        """Test encoding/decoding with storage format."""
        service = EncryptionService()
        plaintext = "My credit card: 4532-1111-2222-3333"
        password = "SecurePassword"

        # Encrypt to storage
        encoded = service.encrypt_to_storage(plaintext, password)

        # Should be base64 (ASCII)
        assert all(
            c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
            for c in encoded
        )

        # Decrypt from storage
        decrypted = service.decrypt_from_storage(encoded, password)

        assert decrypted == plaintext

    def test_empty_plaintext_fails(self):
        """Test that empty plaintext raises error."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="empty"):
            service.encrypt("", "password")

    def test_empty_password_fails(self):
        """Test that empty password raises error."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="empty"):
            service.encrypt("plaintext", "")

    def test_large_plaintext(self):
        """Test encryption of large content."""
        service = EncryptionService()
        plaintext = "x" * 100_000  # 100 KB
        password = "password"

        encrypted = service.encrypt(plaintext, password)
        decrypted = service.decrypt(encrypted, password)

        assert decrypted == plaintext

    def test_plaintextext_too_large_fails(self):
        """Test that oversized plaintext fails."""
        service = EncryptionService()
        plaintext = "x" * 2_000_000  # 2 MB (exceeds 1 MB limit)
        password = "password"

        with pytest.raises(ValueError, match="exceeds maximum"):
            service.encrypt(plaintext, password)

    def test_each_encryption_unique_nonce(self):
        """Test that each encryption produces different ciphertext (different nonce)."""
        service = EncryptionService()
        plaintext = "Same content"
        password = "Same password"

        encrypted1 = service.encrypt(plaintext, password)
        encrypted2 = service.encrypt(plaintext, password)

        # Same plaintext + password but different ciphertexts (different nonce)
        assert encrypted1.ciphertext != encrypted2.ciphertext
        assert encrypted1.nonce != encrypted2.nonce

        # But both decrypt to same plaintext
        assert service.decrypt(encrypted1, password) == plaintext
        assert service.decrypt(encrypted2, password) == plaintext

    def test_unicode_content(self):
        """Test encryption of Unicode content."""
        service = EncryptionService()
        plaintext = "Hello 世界 🔐 مرحبا Привет"
        password = "пароль"

        encrypted = service.encrypt(plaintext, password)
        decrypted = service.decrypt(encrypted, password)

        assert decrypted == plaintext

    def test_singleton_pattern(self):
        """Test that get_encryption_service returns singleton."""
        service1 = get_encryption_service()
        service2 = get_encryption_service()

        assert service1 is service2

    def test_invalid_storage_format_fails(self):
        """Test that invalid storage format fails."""
        service = EncryptionService()

        with pytest.raises(ValueError, match="format"):
            service.decrypt_from_storage("not-valid-base64!!!", "password")

    def test_truncated_storage_fails(self):
        """Test that truncated encrypted data fails."""
        from base64 import b64encode

        service = EncryptionService()

        # Encode a short payload (< 44 bytes) — valid base64 but too short to unpack
        short_payload = b64encode(b"\x00" * 10).decode("ascii")

        with pytest.raises(ValueError, match="too short"):
            service.decrypt_from_storage(short_payload, "password")
