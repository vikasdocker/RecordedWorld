"""
Tests for Secret Manager service.
"""
import pytest
from app.services.secret_manager import SecretManager


@pytest.fixture
def secret_manager():
    return SecretManager(secret_key="test-secret-key-for-testing", api_key_prefix="test_")


class TestJWTTokens:
    def test_create_access_token(self, secret_manager):
        token = secret_manager.create_access_token(
            user_id=1,
            username="testuser"
        )
        assert token is not None
        assert len(token) > 0
        assert "." in token

    def test_verify_access_token(self, secret_manager):
        token = secret_manager.create_access_token(
            user_id=1,
            username="testuser"
        )
        payload = secret_manager.verify_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_invalid_token(self, secret_manager):
        payload = secret_manager.verify_access_token("invalid.token.here")
        assert payload is None

    def test_verify_tampered_token(self, secret_manager):
        token = secret_manager.create_access_token(
            user_id=1,
            username="testuser"
        )
        # Tamper with the token
        parts = token.split(".")
        tampered = f"{parts[0]}.tampered"
        payload = secret_manager.verify_access_token(tampered)
        assert payload is None

    def test_token_expiration(self, secret_manager):
        from datetime import timedelta
        token = secret_manager.create_access_token(
            user_id=1,
            username="testuser",
            expires_delta=timedelta(seconds=-1)  # Already expired
        )
        payload = secret_manager.verify_access_token(token)
        assert payload is None


class TestAPIKeys:
    def test_generate_api_key(self, secret_manager):
        api_key = secret_manager.generate_api_key()
        assert api_key.startswith("test_")
        # "test_" + 32 hex chars = 37 total (token_hex(16) = 32 hex chars)
        assert len(api_key) == 37

    def test_validate_api_key(self, secret_manager):
        api_key = secret_manager.generate_api_key()
        assert secret_manager.validate_api_key(api_key) is True

    def test_validate_invalid_api_key(self, secret_manager):
        assert secret_manager.validate_api_key("invalid_key") is False
        assert secret_manager.validate_api_key("test_short") is False

    def test_hash_api_key(self, secret_manager):
        api_key = secret_manager.generate_api_key()
        hashed = secret_manager.hash_api_key(api_key)
        assert len(hashed) == 64  # SHA-256 hex digest
        assert hashed != api_key


class TestSignedURLs:
    def test_create_signed_url(self, secret_manager):
        url = secret_manager.create_signed_url("/api/assets/model.glb")
        assert url.startswith("/api/assets/model.glb?")
        assert "expires=" in url
        assert "signature=" in url

    def test_verify_signed_url(self, secret_manager):
        url = secret_manager.create_signed_url("/api/assets/model.glb")
        assert secret_manager.verify_signed_url(url) is True

    def test_verify_expired_signed_url(self, secret_manager):
        url = secret_manager.create_signed_url("/api/assets/model.glb", expires_in_seconds=-1)
        assert secret_manager.verify_signed_url(url) is False

    def test_verify_tampered_signed_url(self, secret_manager):
        url = secret_manager.create_signed_url("/api/assets/model.glb")
        # Tamper with the URL
        tampered = url.replace("signature=", "signature=tampered")
        assert secret_manager.verify_signed_url(tampered) is False


class TestPasswordHashing:
    def test_hash_password(self, secret_manager):
        password_hash = secret_manager.hash_password("mypassword")
        assert ":" in password_hash
        parts = password_hash.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 32  # Salt
        assert len(parts[1]) == 64  # Hash

    def test_verify_password(self, secret_manager):
        password_hash = secret_manager.hash_password("mypassword")
        assert secret_manager.verify_password("mypassword", password_hash) is True

    def test_verify_wrong_password(self, secret_manager):
        password_hash = secret_manager.hash_password("mypassword")
        assert secret_manager.verify_password("wrongpassword", password_hash) is False

    def test_verify_invalid_hash_format(self, secret_manager):
        assert secret_manager.verify_password("password", "invalid") is False
