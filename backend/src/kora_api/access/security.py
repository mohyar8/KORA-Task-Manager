"""Credential primitives: username normalization, Argon2id hashing, and opaque tokens."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from kora_api.access.policy import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_PATTERN,
)

_hasher = PasswordHasher()  # Argon2id with library-recommended parameters
# Verified against when the account does not exist, so response timing does not reveal it.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def normalize_username(raw: str) -> str | None:
    """Return the canonical (lowercase) username, or None if it violates the username rules."""
    candidate = raw.strip().lower()
    return candidate if USERNAME_PATTERN.fullmatch(candidate) else None


def is_valid_password(password: str) -> bool:
    return PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Spend the same work as a real verification; used when there is no account to check."""
    verify_password(_DUMMY_HASH, password)


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def generate_temporary_password() -> str:
    return secrets.token_urlsafe(18)  # 24 URL-safe characters, 144 bits


def generate_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def hash_token(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def token_matches(token: str, expected_hash: bytes) -> bool:
    return hmac.compare_digest(hash_token(token), expected_hash)
