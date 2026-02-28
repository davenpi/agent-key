"""Security helpers."""

import hashlib
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

password_hasher = PasswordHasher()


def generate_plaintext_token(prefix: str) -> str:
    """Generate a token for admin or agent auth.

    Parameters
    ----------
    prefix : str
        Human-readable token prefix.

    Returns
    -------
    str
        New opaque token.
    """
    return f"{prefix}_{token_urlsafe(24)}"


def lookup_hash(token: str) -> str:
    """Compute a fast, non-secret hash for DB lookup.

    Parameters
    ----------
    token : str
        Raw token.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
    """Hash a token for storage.

    Parameters
    ----------
    token : str
        Raw token.

    Returns
    -------
    str
        Argon2 token hash.
    """
    return password_hasher.hash(token)


def verify_token(token: str, token_hash: str) -> bool:
    """Verify a token against its hash.

    Parameters
    ----------
    token : str
        Raw token.
    token_hash : str
        Stored token hash.

    Returns
    -------
    bool
        Whether the token matches.
    """
    try:
        return password_hasher.verify(token_hash, token)
    except VerifyMismatchError:
        return False
