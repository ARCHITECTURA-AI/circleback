"""Fernet-based token encryption for OAuth refresh tokens at rest.

Implements the security requirement from §10: OAuth refresh tokens encrypted
at rest, never logged, minimally scoped.
"""

from __future__ import annotations

import logging
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


def get_cipher(key: str) -> Fernet:
    """Create a Fernet cipher from the provided key.

    If no key is configured, raises a clear error at call time.
    """
    if not key:
        raise ValueError(
            "TOKEN_ENCRYPTION_KEY is not configured. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str, key: str) -> str:
    """Encrypt a token string using Fernet symmetric encryption.

    Returns the encrypted token as a URL-safe base64 string.
    """
    cipher = get_cipher(key)
    return cipher.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str, key: str) -> str:
    """Decrypt an encrypted token string.

    Returns the original plaintext token.
    Raises InvalidToken if the key is wrong or data is corrupted.
    """
    cipher = get_cipher(key)
    try:
        return cipher.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt token — key mismatch or data corruption")
        raise
