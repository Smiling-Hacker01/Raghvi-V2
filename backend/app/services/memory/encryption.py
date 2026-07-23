"""Encryption service for sensitive memory data.

Uses AES-256-GCM (authenticated encryption with associated data).
Key derivation: PBKDF2 from user password + random salt.

Security properties:
- Confidentiality: AES-256 encryption
- Authenticity: GCM authentication tag (prevents tampering)
- Key derivation: PBKDF2 with 480,000 iterations (OWASP 2023)
- Per-record nonce: Unique IV prevents replay attacks
"""

import logging
import os
from base64 import b64decode, b64encode
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EncryptedData:
    """Encrypted content with metadata for decryption.

    Immutable dataclass ensures data integrity.
    """

    ciphertext: bytes
    nonce: bytes
    salt: bytes
    tag: bytes


class EncryptionService:
    """AES-256-GCM encryption with PBKDF2 key derivation.

    Features:
    - Authenticated encryption (AEAD)
    - Per-record nonce (prevents replay)
    - PBKDF2 key derivation (resists brute force)
    - Audit logging

    Thread-safe (no mutable state).
    """

    # OWASP 2023 recommended iterations for PBKDF2-SHA256
    PBKDF2_ITERATIONS = 480_000

    # AES-256 requires 32-byte key
    KEY_SIZE = 32

    # GCM nonce should be 12 bytes (96 bits) for optimal security
    NONCE_SIZE = 12

    # Salt for PBKDF2 should be 16+ bytes
    SALT_SIZE = 16

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2.

        Args:
            password: User password (used as encryption key material)
            salt: Random salt (16+ bytes)

        Returns:
            32-byte AES-256 key

        Note:
            - Uses 480,000 iterations (OWASP 2023 standard)
            - SHA256 hash function
            - High iteration count makes brute force infeasible
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=EncryptionService.KEY_SIZE,
            salt=salt,
            iterations=EncryptionService.PBKDF2_ITERATIONS,
        )

        key = kdf.derive(password.encode("utf-8"))
        logger.debug(
            f"Key derived from password with {EncryptionService.PBKDF2_ITERATIONS} iterations"
        )

        return key

    @classmethod
    def encrypt(cls, plaintext: str, password: str) -> EncryptedData:
        """Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: Content to encrypt (memory text)
            password: Encryption password (user password)

        Returns:
            EncryptedData with ciphertext, nonce, salt, tag

        Raises:
            ValueError: If plaintext or password invalid
        """
        # Validate inputs
        if not plaintext:
            raise ValueError("Plaintext cannot be empty")

        if not password:
            raise ValueError("Password cannot be empty")

        if len(plaintext) > 1_000_000:  # 1 MB limit
            raise ValueError("Plaintext exceeds maximum size (1 MB)")

        # Generate random salt and nonce
        salt = os.urandom(cls.SALT_SIZE)
        nonce = os.urandom(cls.NONCE_SIZE)

        # Derive key from password
        key = cls._derive_key(password, salt)

        # Create cipher
        cipher = AESGCM(key)

        # Encrypt with authenticated data (nonce prevents reuse)
        plaintext_bytes = plaintext.encode("utf-8")

        try:
            ciphertext = cipher.encrypt(nonce, plaintext_bytes, None)
            logger.info(f"Encrypted {len(plaintext_bytes)} bytes")
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError(f"Encryption failed: {e}") from e

        # GCM mode: last 16 bytes of ciphertext are the authentication tag
        # We need to extract and store separately for protocol compliance
        tag = ciphertext[-16:]
        actual_ciphertext = ciphertext[:-16]

        return EncryptedData(
            ciphertext=actual_ciphertext,
            nonce=nonce,
            salt=salt,
            tag=tag,
        )

    @classmethod
    def decrypt(cls, encrypted: EncryptedData, password: str) -> str:
        """Decrypt AES-256-GCM encrypted data.

        Args:
            encrypted: EncryptedData with ciphertext, nonce, salt, tag
            password: Encryption password (must match encryption password)

        Returns:
            Decrypted plaintext (memory text)

        Raises:
            ValueError: If decryption fails (wrong password, tampered data)
        """
        # Validate inputs
        if not password:
            raise ValueError("Password cannot be empty")

        # Derive same key from password and salt
        try:
            key = cls._derive_key(password, encrypted.salt)
        except Exception as e:
            logger.error(f"Key derivation failed: {e}")
            raise ValueError("Failed to derive decryption key") from e

        # Create cipher
        cipher = AESGCM(key)

        # Combine ciphertext and tag (required by cryptography library)
        ciphertext_with_tag = encrypted.ciphertext + encrypted.tag

        # Decrypt and verify authentication tag
        try:
            plaintext_bytes = cipher.decrypt(
                encrypted.nonce,
                ciphertext_with_tag,
                None,
            )
            logger.info(f"Decrypted {len(plaintext_bytes)} bytes")
        except Exception as e:
            logger.error(f"Decryption failed (wrong password or tampered data): {e}")
            raise ValueError("Failed to decrypt: wrong password or data was tampered with") from e

        # Decode to string
        try:
            plaintext = plaintext_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            logger.error(f"Plaintext decode failed: {e}")
            raise ValueError("Failed to decode plaintext") from e

        return plaintext

    @classmethod
    def encrypt_to_storage(cls, plaintext: str, password: str) -> str:
        """Encrypt and encode to storage format (base64).

        Format: base64(salt + nonce + ciphertext + tag)

        Args:
            plaintext: Content to encrypt
            password: Encryption password

        Returns:
            Base64-encoded encrypted data (storable in VARCHAR column)
        """
        encrypted = cls.encrypt(plaintext, password)

        # Pack all components: salt + nonce + ciphertext + tag
        packed = encrypted.salt + encrypted.nonce + encrypted.ciphertext + encrypted.tag

        # Encode to base64 for storage
        encoded = b64encode(packed).decode("ascii")

        logger.debug(f"Encrypted data encoded to storage ({len(encoded)} chars)")

        return encoded

    @classmethod
    def decrypt_from_storage(cls, encoded: str, password: str) -> str:
        """Decrypt from storage format (base64).

        Args:
            encoded: Base64-encoded encrypted data
            password: Decryption password

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If decoding or decryption fails
        """
        # Decode from base64
        try:
            packed = b64decode(encoded)
        except Exception as e:
            logger.error(f"Base64 decode failed: {e}")
            raise ValueError("Invalid encrypted data format") from e

        # Unpack: salt (16) + nonce (12) + ciphertext (variable) + tag (16)
        if len(packed) < 44:  # 16 + 12 + 0 + 16
            raise ValueError("Encrypted data too short")

        salt = packed[:16]
        nonce = packed[16:28]
        tag = packed[-16:]
        ciphertext = packed[28:-16]

        encrypted = EncryptedData(
            ciphertext=ciphertext,
            nonce=nonce,
            salt=salt,
            tag=tag,
        )

        plaintext = cls.decrypt(encrypted, password)

        logger.debug("Decrypted data from storage")

        return plaintext


# Singleton service instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    """Get encryption service (singleton).

    Returns:
        EncryptionService instance
    """
    global _encryption_service

    if not _encryption_service:
        _encryption_service = EncryptionService()

    return _encryption_service
