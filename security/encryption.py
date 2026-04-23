"""
PII encryption and phone hashing utilities.

Fernet (symmetric encryption) protects phone numbers and Signal usernames at rest.
Argon2id (memory-hard KDF) is used for the phone dedup hash — not SHA-256, which
is trivially brute-forceable over the small phone number space (~10B possibilities).
"""

import argon2
from argon2 import PasswordHasher
from cryptography.fernet import Fernet, MultiFernet
from django.conf import settings

# Argon2id hasher tuned to ~200ms per hash on a typical VPS.
# This makes brute-forcing the 10B phone number space take ~63 years per core.
_phone_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=2,
    hash_len=32,
    type=argon2.Type.ID,
)


def _get_fernet() -> MultiFernet:
    """Build a MultiFernet from ENCRYPTION_KEYS (newest key first)."""
    keys = settings.ENCRYPTION_KEYS
    return MultiFernet([Fernet(k.encode() if isinstance(k, str) else k) for k in keys])


def encrypt(plaintext: str) -> bytes:
    """Encrypt a string. Returns bytes suitable for BinaryField storage."""
    return _get_fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str:
    """Decrypt bytes back to a string."""
    return _get_fernet().decrypt(ciphertext).decode("utf-8")


def hash_phone(phone: str) -> str:
    """
    Produce an Argon2id hash of a normalized phone number for dedup lookups.

    The salt includes PHONE_HASH_SALT from settings so the hash is useless
    without both the database and the secret. The Argon2 hash itself embeds
    a random salt, making it resistant to rainbow tables.
    """
    normalized = _normalize_phone(phone)
    if not normalized:
        return ""
    secret_salt = settings.PHONE_HASH_SALT
    return _phone_hasher.hash(f"{secret_salt}:{normalized}")


def verify_phone_hash(phone: str, stored_hash: str) -> bool:
    """Check if phone matches a stored Argon2id hash."""
    normalized = _normalize_phone(phone)
    if not normalized or not stored_hash:
        return False
    secret_salt = settings.PHONE_HASH_SALT
    try:
        return _phone_hasher.verify(stored_hash, f"{secret_salt}:{normalized}")
    except argon2.exceptions.VerifyMismatchError:
        return False


def _normalize_phone(phone: str) -> str:
    """Strip all non-digit characters. Returns empty string if too short."""
    digits = "".join(c for c in phone if c.isdigit())
    return digits if len(digits) >= 7 else ""
