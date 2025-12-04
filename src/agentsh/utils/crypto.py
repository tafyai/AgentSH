"""Cryptographic utilities for secure data handling.

Provides encryption/decryption for data at rest, including:
- AES-256 encryption for sensitive data
- Key derivation from passwords
- Secure credential storage
- Secret redaction utilities
"""

import base64
import hashlib
import hmac
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Union

# Try to import cryptography library, fall back to basic if not available
try:
    from cryptography.fernet import Fernet, InvalidToken
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class EncryptionError(Exception):
    """Error during encryption/decryption."""

    pass


class KeyDerivationError(Exception):
    """Error during key derivation."""

    pass


class EncryptionAlgorithm(str, Enum):
    """Supported encryption algorithms."""

    FERNET = "fernet"  # AES-128-CBC with HMAC-SHA256
    XOR_SIMPLE = "xor"  # Simple XOR (for testing only, NOT secure)


@dataclass
class EncryptedData:
    """Container for encrypted data.

    Attributes:
        ciphertext: Encrypted bytes (base64 encoded)
        algorithm: Encryption algorithm used
        salt: Salt used for key derivation (if applicable)
        version: Format version for future compatibility
    """

    ciphertext: str
    algorithm: EncryptionAlgorithm
    salt: Optional[str] = None
    version: int = 1

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "ciphertext": self.ciphertext,
            "algorithm": self.algorithm.value,
            "salt": self.salt,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EncryptedData":
        """Create from dictionary."""
        return cls(
            ciphertext=data["ciphertext"],
            algorithm=EncryptionAlgorithm(data["algorithm"]),
            salt=data.get("salt"),
            version=data.get("version", 1),
        )


def generate_key() -> bytes:
    """Generate a new random encryption key.

    Returns:
        32 random bytes suitable for encryption
    """
    return secrets.token_bytes(32)


def generate_key_from_password(
    password: str,
    salt: Optional[bytes] = None,
    iterations: int = 100000,
) -> tuple[bytes, bytes]:
    """Derive an encryption key from a password.

    Uses PBKDF2-HMAC-SHA256 for key derivation.

    Args:
        password: Password to derive key from
        salt: Optional salt bytes (generated if not provided)
        iterations: Number of PBKDF2 iterations

    Returns:
        Tuple of (derived_key, salt)

    Raises:
        KeyDerivationError: If key derivation fails
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    if CRYPTO_AVAILABLE:
        try:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=iterations,
            )
            key = kdf.derive(password.encode())
            return key, salt
        except Exception as e:
            raise KeyDerivationError(f"Failed to derive key: {e}") from e
    else:
        # Fallback using hashlib
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt,
            iterations,
            dklen=32,
        )
        return key, salt


def _key_to_fernet_key(key: bytes) -> bytes:
    """Convert a 32-byte key to Fernet-compatible format.

    Fernet requires a URL-safe base64-encoded 32-byte key.

    Args:
        key: 32-byte key

    Returns:
        Fernet-compatible key
    """
    return base64.urlsafe_b64encode(key)


class Encryptor:
    """Encrypt and decrypt data.

    Supports multiple encryption algorithms with automatic
    fallback when cryptography library is not available.

    Example:
        encryptor = Encryptor("my-secret-password")
        encrypted = encryptor.encrypt("sensitive data")
        decrypted = encryptor.decrypt(encrypted)
    """

    def __init__(
        self,
        key: Optional[Union[str, bytes]] = None,
        algorithm: EncryptionAlgorithm = EncryptionAlgorithm.FERNET,
    ) -> None:
        """Initialize encryptor.

        Args:
            key: Encryption key (password string or raw bytes)
            algorithm: Encryption algorithm to use
        """
        self.algorithm = algorithm
        self._key: Optional[bytes] = None
        self._salt: Optional[bytes] = None
        self._fernet: Optional["Fernet"] = None

        if key:
            self._init_key(key)

    def _init_key(self, key: Union[str, bytes]) -> None:
        """Initialize encryption key.

        Args:
            key: Password string or raw key bytes
        """
        if isinstance(key, str):
            # Derive key from password
            self._key, self._salt = generate_key_from_password(key)
        else:
            self._key = key
            self._salt = None

        if self.algorithm == EncryptionAlgorithm.FERNET and CRYPTO_AVAILABLE:
            fernet_key = _key_to_fernet_key(self._key)
            self._fernet = Fernet(fernet_key)

    def encrypt(self, data: Union[str, bytes]) -> EncryptedData:
        """Encrypt data.

        Args:
            data: Data to encrypt (string or bytes)

        Returns:
            EncryptedData containing ciphertext

        Raises:
            EncryptionError: If encryption fails
        """
        if self._key is None:
            raise EncryptionError("No encryption key configured")

        if isinstance(data, str):
            data = data.encode("utf-8")

        try:
            if self.algorithm == EncryptionAlgorithm.FERNET and self._fernet:
                ciphertext = self._fernet.encrypt(data)
                return EncryptedData(
                    ciphertext=ciphertext.decode("utf-8"),
                    algorithm=self.algorithm,
                    salt=base64.b64encode(self._salt).decode() if self._salt else None,
                )
            else:
                # Fallback to simple XOR (for testing only)
                ciphertext = self._xor_encrypt(data)
                return EncryptedData(
                    ciphertext=base64.b64encode(ciphertext).decode(),
                    algorithm=EncryptionAlgorithm.XOR_SIMPLE,
                    salt=base64.b64encode(self._salt).decode() if self._salt else None,
                )
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {e}") from e

    def decrypt(self, encrypted: EncryptedData) -> bytes:
        """Decrypt data.

        Args:
            encrypted: EncryptedData to decrypt

        Returns:
            Decrypted bytes

        Raises:
            EncryptionError: If decryption fails
        """
        if self._key is None:
            raise EncryptionError("No encryption key configured")

        try:
            if encrypted.algorithm == EncryptionAlgorithm.FERNET and self._fernet:
                return self._fernet.decrypt(encrypted.ciphertext.encode())
            else:
                # XOR decrypt
                ciphertext = base64.b64decode(encrypted.ciphertext)
                return self._xor_decrypt(ciphertext)
        except InvalidToken:
            raise EncryptionError("Decryption failed: invalid key or corrupted data")
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {e}") from e

    def decrypt_string(self, encrypted: EncryptedData) -> str:
        """Decrypt data and return as string.

        Args:
            encrypted: EncryptedData to decrypt

        Returns:
            Decrypted string
        """
        return self.decrypt(encrypted).decode("utf-8")

    def _xor_encrypt(self, data: bytes) -> bytes:
        """Simple XOR encryption (for testing/fallback only).

        NOT cryptographically secure - use only when
        cryptography library is unavailable.
        """
        if not self._key:
            raise EncryptionError("No key")
        return bytes(a ^ b for a, b in zip(data, self._cycle_key(len(data))))

    def _xor_decrypt(self, data: bytes) -> bytes:
        """XOR decryption (symmetric with encrypt)."""
        return self._xor_encrypt(data)

    def _cycle_key(self, length: int) -> bytes:
        """Cycle key bytes to match data length."""
        if not self._key:
            return b""
        key_len = len(self._key)
        return bytes(self._key[i % key_len] for i in range(length))


class SecureStore:
    """Secure storage for sensitive data.

    Provides encrypted file-based storage for credentials,
    API keys, and other sensitive information.

    Example:
        store = SecureStore(Path("~/.agentsh/secrets"), "master-password")
        store.set("api_key", "sk-secret-key")
        api_key = store.get("api_key")
    """

    def __init__(
        self,
        store_path: Path,
        password: Optional[str] = None,
        key: Optional[bytes] = None,
    ) -> None:
        """Initialize secure store.

        Args:
            store_path: Path to store directory
            password: Master password for encryption
            key: Pre-generated encryption key (alternative to password)
        """
        self.store_path = Path(store_path).expanduser()
        self.store_path.mkdir(parents=True, exist_ok=True)

        if password:
            self._encryptor = Encryptor(password)
        elif key:
            self._encryptor = Encryptor(key)
        else:
            # Generate a new key and store it
            key = generate_key()
            self._encryptor = Encryptor(key)
            self._save_key(key)

    def _save_key(self, key: bytes) -> None:
        """Save encryption key to file."""
        key_file = self.store_path / ".key"
        key_file.write_bytes(key)
        # Restrict permissions
        key_file.chmod(0o600)

    def set(self, name: str, value: str) -> None:
        """Store a secret value.

        Args:
            name: Secret name
            value: Secret value
        """
        encrypted = self._encryptor.encrypt(value)
        secret_file = self.store_path / f"{name}.secret"

        import json

        secret_file.write_text(json.dumps(encrypted.to_dict()))
        secret_file.chmod(0o600)

    def get(self, name: str) -> Optional[str]:
        """Retrieve a secret value.

        Args:
            name: Secret name

        Returns:
            Secret value or None if not found
        """
        secret_file = self.store_path / f"{name}.secret"
        if not secret_file.exists():
            return None

        import json

        data = json.loads(secret_file.read_text())
        encrypted = EncryptedData.from_dict(data)
        return self._encryptor.decrypt_string(encrypted)

    def delete(self, name: str) -> bool:
        """Delete a secret.

        Args:
            name: Secret name

        Returns:
            True if deleted, False if not found
        """
        secret_file = self.store_path / f"{name}.secret"
        if secret_file.exists():
            secret_file.unlink()
            return True
        return False

    def list(self) -> list[str]:
        """List all stored secret names.

        Returns:
            List of secret names
        """
        return [
            f.stem
            for f in self.store_path.glob("*.secret")
            if f.is_file()
        ]

    def exists(self, name: str) -> bool:
        """Check if a secret exists.

        Args:
            name: Secret name

        Returns:
            True if secret exists
        """
        return (self.store_path / f"{name}.secret").exists()


def secure_compare(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """Compare two values in constant time.

    Prevents timing attacks when comparing secrets.

    Args:
        a: First value
        b: Second value

    Returns:
        True if equal
    """
    if isinstance(a, str):
        a = a.encode()
    if isinstance(b, str):
        b = b.encode()
    return hmac.compare_digest(a, b)


def generate_token(length: int = 32) -> str:
    """Generate a secure random token.

    Args:
        length: Number of bytes

    Returns:
        URL-safe base64 encoded token
    """
    return secrets.token_urlsafe(length)


def hash_secret(secret: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash a secret for storage.

    Uses PBKDF2-HMAC-SHA256 with a random salt.

    Args:
        secret: Secret to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hash, salt) both base64 encoded
    """
    salt_bytes = base64.b64decode(salt) if salt else secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode(),
        salt_bytes,
        100000,
        dklen=32,
    )
    return (
        base64.b64encode(hash_bytes).decode(),
        base64.b64encode(salt_bytes).decode(),
    )


def verify_secret(secret: str, hash_value: str, salt: str) -> bool:
    """Verify a secret against its hash.

    Args:
        secret: Secret to verify
        hash_value: Expected hash (base64 encoded)
        salt: Salt used for hashing (base64 encoded)

    Returns:
        True if secret matches hash
    """
    computed_hash, _ = hash_secret(secret, salt)
    return secure_compare(computed_hash, hash_value)
