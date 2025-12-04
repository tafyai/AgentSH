"""Tests for cryptographic utilities module."""

import base64
from pathlib import Path

import pytest

from agentsh.utils.crypto import (
    EncryptedData,
    EncryptionAlgorithm,
    EncryptionError,
    Encryptor,
    KeyDerivationError,
    SecureStore,
    generate_key,
    generate_key_from_password,
    generate_token,
    hash_secret,
    secure_compare,
    verify_secret,
    CRYPTO_AVAILABLE,
)


class TestGenerateKey:
    """Tests for key generation."""

    def test_generate_key_returns_bytes(self) -> None:
        """Should return bytes."""
        key = generate_key()
        assert isinstance(key, bytes)

    def test_generate_key_length(self) -> None:
        """Should return 32 bytes."""
        key = generate_key()
        assert len(key) == 32

    def test_generate_key_unique(self) -> None:
        """Should generate unique keys."""
        key1 = generate_key()
        key2 = generate_key()
        assert key1 != key2


class TestGenerateKeyFromPassword:
    """Tests for password-based key derivation."""

    def test_derive_key_from_password(self) -> None:
        """Should derive key from password."""
        key, salt = generate_key_from_password("password123")

        assert isinstance(key, bytes)
        assert len(key) == 32
        assert isinstance(salt, bytes)
        assert len(salt) == 16

    def test_same_password_different_salt_different_key(self) -> None:
        """Should produce different keys with different salts."""
        key1, salt1 = generate_key_from_password("password")
        key2, salt2 = generate_key_from_password("password")

        assert key1 != key2  # Different random salts

    def test_same_password_same_salt_same_key(self) -> None:
        """Should produce same key with same salt."""
        _, salt = generate_key_from_password("password")
        key1, _ = generate_key_from_password("password", salt=salt)
        key2, _ = generate_key_from_password("password", salt=salt)

        assert key1 == key2

    def test_different_passwords_different_keys(self) -> None:
        """Should produce different keys for different passwords."""
        _, salt = generate_key_from_password("password")
        key1, _ = generate_key_from_password("password1", salt=salt)
        key2, _ = generate_key_from_password("password2", salt=salt)

        assert key1 != key2


class TestEncryptedData:
    """Tests for EncryptedData dataclass."""

    def test_create_encrypted_data(self) -> None:
        """Should create encrypted data."""
        data = EncryptedData(
            ciphertext="abc123",
            algorithm=EncryptionAlgorithm.FERNET,
        )

        assert data.ciphertext == "abc123"
        assert data.algorithm == EncryptionAlgorithm.FERNET
        assert data.salt is None
        assert data.version == 1

    def test_to_dict(self) -> None:
        """Should convert to dict."""
        data = EncryptedData(
            ciphertext="abc123",
            algorithm=EncryptionAlgorithm.FERNET,
            salt="salt123",
        )

        d = data.to_dict()

        assert d["ciphertext"] == "abc123"
        assert d["algorithm"] == "fernet"
        assert d["salt"] == "salt123"
        assert d["version"] == 1

    def test_from_dict(self) -> None:
        """Should create from dict."""
        d = {
            "ciphertext": "abc123",
            "algorithm": "fernet",
            "salt": "salt123",
        }

        data = EncryptedData.from_dict(d)

        assert data.ciphertext == "abc123"
        assert data.algorithm == EncryptionAlgorithm.FERNET
        assert data.salt == "salt123"

    def test_roundtrip(self) -> None:
        """Should roundtrip through dict."""
        original = EncryptedData(
            ciphertext="abc123",
            algorithm=EncryptionAlgorithm.FERNET,
            salt="salt123",
            version=1,
        )

        restored = EncryptedData.from_dict(original.to_dict())

        assert restored.ciphertext == original.ciphertext
        assert restored.algorithm == original.algorithm
        assert restored.salt == original.salt


class TestEncryptor:
    """Tests for Encryptor class."""

    def test_encrypt_with_password(self) -> None:
        """Should encrypt with password."""
        encryptor = Encryptor("my-secret-password")
        encrypted = encryptor.encrypt("hello world")

        assert encrypted.ciphertext
        assert encrypted.salt is not None

    def test_encrypt_with_key(self) -> None:
        """Should encrypt with raw key."""
        key = generate_key()
        encryptor = Encryptor(key)
        encrypted = encryptor.encrypt("hello world")

        assert encrypted.ciphertext

    def test_decrypt_recovers_original(self) -> None:
        """Should decrypt to original data."""
        encryptor = Encryptor("password123")
        original = "secret message"

        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt_string(encrypted)

        assert decrypted == original

    def test_decrypt_bytes(self) -> None:
        """Should decrypt to bytes."""
        encryptor = Encryptor("password123")
        original = b"binary data"

        encrypted = encryptor.encrypt(original)
        decrypted = encryptor.decrypt(encrypted)

        assert decrypted == original

    def test_encrypt_without_key_fails(self) -> None:
        """Should fail without key."""
        encryptor = Encryptor()

        with pytest.raises(EncryptionError):
            encryptor.encrypt("data")

    def test_decrypt_without_key_fails(self) -> None:
        """Should fail without key."""
        encryptor = Encryptor()
        encrypted = EncryptedData(
            ciphertext="abc",
            algorithm=EncryptionAlgorithm.FERNET,
        )

        with pytest.raises(EncryptionError):
            encryptor.decrypt(encrypted)

    def test_wrong_password_fails(self) -> None:
        """Should fail with wrong password."""
        encryptor1 = Encryptor("password1")
        encryptor2 = Encryptor("password2")

        encrypted = encryptor1.encrypt("secret")

        # Create new encryptor with different password for decryption
        with pytest.raises(EncryptionError):
            encryptor2.decrypt(encrypted)

    def test_xor_fallback(self) -> None:
        """Should use XOR fallback when specified."""
        encryptor = Encryptor("password", algorithm=EncryptionAlgorithm.XOR_SIMPLE)
        original = "test data"

        encrypted = encryptor.encrypt(original)
        assert encrypted.algorithm == EncryptionAlgorithm.XOR_SIMPLE

        decrypted = encryptor.decrypt_string(encrypted)
        assert decrypted == original


class TestSecureStore:
    """Tests for SecureStore class."""

    @pytest.fixture
    def store(self, tmp_path: Path) -> SecureStore:
        """Create secure store in temp directory."""
        return SecureStore(tmp_path, password="test-password")

    def test_set_and_get(self, store: SecureStore) -> None:
        """Should store and retrieve secrets."""
        store.set("api_key", "sk-secret-123")
        retrieved = store.get("api_key")

        assert retrieved == "sk-secret-123"

    def test_get_nonexistent_returns_none(self, store: SecureStore) -> None:
        """Should return None for missing secrets."""
        assert store.get("nonexistent") is None

    def test_delete(self, store: SecureStore) -> None:
        """Should delete secrets."""
        store.set("temp", "value")
        assert store.exists("temp")

        result = store.delete("temp")

        assert result is True
        assert not store.exists("temp")

    def test_delete_nonexistent(self, store: SecureStore) -> None:
        """Should return False for missing secret."""
        result = store.delete("nonexistent")
        assert result is False

    def test_list_secrets(self, store: SecureStore) -> None:
        """Should list secret names."""
        store.set("key1", "value1")
        store.set("key2", "value2")

        secrets = store.list()

        assert "key1" in secrets
        assert "key2" in secrets

    def test_exists(self, store: SecureStore) -> None:
        """Should check existence."""
        store.set("exists", "value")

        assert store.exists("exists")
        assert not store.exists("not_exists")

    def test_overwrite_secret(self, store: SecureStore) -> None:
        """Should overwrite existing secret."""
        store.set("key", "value1")
        store.set("key", "value2")

        assert store.get("key") == "value2"

    def test_store_with_raw_key(self, tmp_path: Path) -> None:
        """Should work with raw key."""
        key = generate_key()
        store = SecureStore(tmp_path / "keystore", key=key)

        store.set("test", "value")
        assert store.get("test") == "value"

    def test_creates_directory(self, tmp_path: Path) -> None:
        """Should create store directory."""
        new_path = tmp_path / "new" / "dir"
        store = SecureStore(new_path, password="pass")

        assert new_path.exists()


class TestSecureCompare:
    """Tests for secure_compare function."""

    def test_equal_strings(self) -> None:
        """Should return True for equal strings."""
        assert secure_compare("secret", "secret") is True

    def test_unequal_strings(self) -> None:
        """Should return False for unequal strings."""
        assert secure_compare("secret1", "secret2") is False

    def test_equal_bytes(self) -> None:
        """Should return True for equal bytes."""
        assert secure_compare(b"secret", b"secret") is True

    def test_mixed_types(self) -> None:
        """Should handle mixed string/bytes."""
        assert secure_compare("secret", b"secret") is True

    def test_empty_strings(self) -> None:
        """Should handle empty strings."""
        assert secure_compare("", "") is True
        assert secure_compare("", "a") is False


class TestGenerateToken:
    """Tests for generate_token function."""

    def test_returns_string(self) -> None:
        """Should return string."""
        token = generate_token()
        assert isinstance(token, str)

    def test_default_length(self) -> None:
        """Should have reasonable length for 32 bytes."""
        token = generate_token(32)
        # URL-safe base64 encoding: ~43 chars for 32 bytes
        assert len(token) > 30

    def test_custom_length(self) -> None:
        """Should respect length parameter."""
        token16 = generate_token(16)
        token64 = generate_token(64)
        assert len(token64) > len(token16)

    def test_unique_tokens(self) -> None:
        """Should generate unique tokens."""
        tokens = [generate_token() for _ in range(100)]
        assert len(set(tokens)) == 100


class TestHashSecret:
    """Tests for hash_secret function."""

    def test_returns_hash_and_salt(self) -> None:
        """Should return hash and salt."""
        hash_val, salt = hash_secret("password")

        assert hash_val
        assert salt
        # Should be base64 encoded
        base64.b64decode(hash_val)
        base64.b64decode(salt)

    def test_same_password_different_salt(self) -> None:
        """Should produce different hashes without salt."""
        hash1, _ = hash_secret("password")
        hash2, _ = hash_secret("password")

        assert hash1 != hash2

    def test_same_password_same_salt(self) -> None:
        """Should produce same hash with same salt."""
        _, salt = hash_secret("password")
        hash1, _ = hash_secret("password", salt)
        hash2, _ = hash_secret("password", salt)

        assert hash1 == hash2


class TestVerifySecret:
    """Tests for verify_secret function."""

    def test_verify_correct_password(self) -> None:
        """Should verify correct password."""
        hash_val, salt = hash_secret("password123")

        assert verify_secret("password123", hash_val, salt) is True

    def test_verify_wrong_password(self) -> None:
        """Should reject wrong password."""
        hash_val, salt = hash_secret("password123")

        assert verify_secret("wrong", hash_val, salt) is False

    def test_verify_different_salt_fails(self) -> None:
        """Should fail with different salt."""
        hash_val, _ = hash_secret("password")
        _, other_salt = hash_secret("other")

        assert verify_secret("password", hash_val, other_salt) is False
