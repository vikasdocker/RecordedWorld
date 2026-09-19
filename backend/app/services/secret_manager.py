"""
Secret management for Recorded World.
Handles JWT tokens, API keys, and signed URLs.
"""
import hashlib
import hmac
import secrets
import time
from typing import Optional
from datetime import datetime, timedelta, timezone


class SecretManager:
    """Manages secrets, tokens, and signed URLs."""

    def __init__(self, secret_key: str, api_key_prefix: str = "rw_"):
        self.secret_key = secret_key
        self.api_key_prefix = api_key_prefix

    # =========================================================================
    # JWT Token Management
    # =========================================================================

    def create_access_token(
        self,
        user_id: int,
        username: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT-like access token."""
        if expires_delta is None:
            expires_delta = timedelta(hours=24)

        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id),
            "username": username,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
        }
        return self._encode_payload(payload)

    def verify_access_token(self, token: str) -> Optional[dict]:
        """Verify and decode an access token."""
        try:
            payload = self._decode_payload(token)
            if payload is None:
                return None

            # Check expiration
            exp = payload.get("exp", 0)
            if exp < time.time():
                return None

            return payload
        except Exception:
            return None

    def _encode_payload(self, payload: dict) -> str:
        """Encode a payload into a token string."""
        import json
        import base64

        # Simple HMAC-based token (not full JWT, but secure)
        payload_json = json.dumps(payload, sort_keys=True)
        payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

        signature = hmac.new(
            self.secret_key.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()

        return f"{payload_b64}.{signature}"

    def _decode_payload(self, token: str) -> Optional[dict]:
        """Decode a token string into a payload."""
        import json
        import base64

        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None

            payload_b64, signature = parts

            # Verify signature
            expected_sig = hmac.new(
                self.secret_key.encode(),
                payload_b64.encode(),
                hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return None

            # Decode payload
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_json = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload_json)
        except Exception:
            return None

    # =========================================================================
    # API Key Management
    # =========================================================================

    def generate_api_key(self) -> str:
        """Generate a new API key."""
        random_part = secrets.token_hex(self.api_key_length if hasattr(self, 'api_key_length') else 16)
        return f"{self.api_key_prefix}{random_part}"

    def validate_api_key(self, api_key: str) -> bool:
        """Validate an API key format."""
        if not api_key.startswith(self.api_key_prefix):
            return False
        key_part = api_key[len(self.api_key_prefix):]
        return len(key_part) == 32 and all(c in '0123456789abcdef' for c in key_part)

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    # =========================================================================
    # Signed URL Management
    # =========================================================================

    def create_signed_url(
        self,
        resource_path: str,
        expires_in_seconds: int = 3600
    ) -> str:
        """Create a signed URL for secure resource access."""
        expires_at = int(time.time()) + expires_in_seconds
        payload = f"{resource_path}:{expires_at}"

        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()

        return f"{resource_path}?expires={expires_at}&signature={signature}"

    def verify_signed_url(self, signed_url: str) -> bool:
        """Verify a signed URL is valid and not expired."""
        try:
            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(signed_url)
            params = parse_qs(parsed.query)

            if "expires" not in params or "signature" not in params:
                return False

            expires_at = int(params["expires"][0])
            signature = params["signature"][0]

            # Check expiration
            if expires_at < time.time():
                return False

            # Verify signature
            resource_path = parsed.path
            payload = f"{resource_path}:{expires_at}"

            expected_sig = hmac.new(
                self.secret_key.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()

            return hmac.compare_digest(signature, expected_sig)
        except Exception:
            return False

    # =========================================================================
    # Password Hashing (simple, for dev only - use bcrypt in production)
    # =========================================================================

    def hash_password(self, password: str) -> str:
        """Hash a password using SHA-256 with salt."""
        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
        return f"{salt}:{password_hash}"

    def verify_password(self, password: str, stored_hash: str) -> bool:
        """Verify a password against its hash."""
        try:
            salt, password_hash = stored_hash.split(":", 1)
            computed_hash = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
            return hmac.compare_digest(password_hash, computed_hash)
        except Exception:
            return False


# Singleton instance
_secret_manager: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    """Get or create the secret manager singleton."""
    global _secret_manager
    if _secret_manager is None:
        from app.core.config import settings
        _secret_manager = SecretManager(
            secret_key=settings.JWT_SECRET_KEY,
            api_key_prefix=settings.API_KEY_PREFIX
        )
    return _secret_manager
