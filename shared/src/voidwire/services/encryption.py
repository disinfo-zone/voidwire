"""API key encryption/decryption using Fernet symmetric encryption."""

from __future__ import annotations

from cryptography.fernet import Fernet

from voidwire.config import get_settings

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    """Get or create Fernet instance from settings."""
    global _fernet
    if _fernet is None:
        settings = get_settings()
        key = settings.encryption_key
        if not key:
            raise ValueError(
                "ENCRYPTION_KEY not set. Generate one with: "
                "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value, returning base64-encoded ciphertext."""
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a base64-encoded ciphertext, returning plaintext."""
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def reset_fernet() -> None:
    """Reset the cached Fernet instance (for testing)."""
    global _fernet
    _fernet = None
