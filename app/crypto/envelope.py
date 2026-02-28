"""Envelope encryption helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet


@dataclass(slots=True)
class EnvelopeCiphertext:
    """Encrypted secret and wrapped data key."""

    encrypted_secret: bytes
    wrapped_data_key: bytes


class EnvelopeEncryptor:
    """Small local envelope-encryption helper.

    Parameters
    ----------
    master_key_path : Path
        File containing the master wrapping key.
    """

    def __init__(self, master_key_path: Path) -> None:
        self.master_key_path = master_key_path
        self.master_key = self._load_or_create_master_key(master_key_path)
        self.master_fernet = Fernet(self.master_key)

    def encrypt(self, plaintext: str) -> EnvelopeCiphertext:
        """Encrypt a provider secret.

        Parameters
        ----------
        plaintext : str
            Secret value to encrypt.

        Returns
        -------
        EnvelopeCiphertext
            Ciphertext payload and wrapped data key.
        """
        data_key = Fernet.generate_key()
        data_fernet = Fernet(data_key)
        encrypted_secret = data_fernet.encrypt(plaintext.encode("utf-8"))
        wrapped_data_key = self.master_fernet.encrypt(data_key)
        return EnvelopeCiphertext(
            encrypted_secret=encrypted_secret,
            wrapped_data_key=wrapped_data_key,
        )

    def decrypt(self, encrypted_secret: bytes, wrapped_data_key: bytes) -> str:
        """Decrypt a provider secret.

        Parameters
        ----------
        encrypted_secret : bytes
            Ciphertext bytes.
        wrapped_data_key : bytes
            Wrapped per-secret data key.

        Returns
        -------
        str
            Decrypted secret.
        """
        data_key = self.master_fernet.decrypt(wrapped_data_key)
        data_fernet = Fernet(data_key)
        return data_fernet.decrypt(encrypted_secret).decode("utf-8")

    @staticmethod
    def _load_or_create_master_key(master_key_path: Path) -> bytes:
        """Load the local master key.

        Parameters
        ----------
        master_key_path : Path
            File path for the master key.

        Returns
        -------
        bytes
            Symmetric master key.
        """
        if master_key_path.exists():
            return master_key_path.read_bytes()
        key = Fernet.generate_key()
        master_key_path.write_bytes(key)
        return key
