"""
Secure Asset Access

Generates signed URLs and validates asset permissions.
"""

import time
import hashlib
import hmac
import secrets
from typing import Optional, Tuple
from urllib.parse import urlencode


class SecureAssetAccess:
    """Generate and validate signed URLs for asset access."""

    def __init__(self, secret_key: str = "development-secret-key"):
        self._secret = secret_key.encode()

    def generate_signed_url(
        self,
        asset_path: str,
        expires_in_seconds: int = 3600,
        user_id: Optional[int] = None,
    ) -> str:
        """Generate a signed URL for asset access."""
        expires_at = int(time.time()) + expires_in_seconds
        payload = f"{asset_path}:{expires_at}:{user_id or ''}"
        signature = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()[:16]

        params = {
            "path": asset_path,
            "expires": expires_at,
            "user": user_id or "",
            "sig": signature,
        }
        return f"/assets/signed?{urlencode(params)}"

    def validate_signed_url(
        self,
        asset_path: str,
        expires_at: int,
        user_id: Optional[int],
        signature: str,
    ) -> Tuple[bool, str]:
        """Validate a signed URL."""
        # Check expiry
        if time.time() > expires_at:
            return False, "URL expired"

        # Verify signature
        payload = f"{asset_path}:{expires_at}:{user_id or ''}"
        expected = hmac.new(self._secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected):
            return False, "Invalid signature"

        return True, ""

    def generate_api_key(self) -> str:
        """Generate a new API key."""
        return f"rw_{secrets.token_hex(32)}"

    def hash_api_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()


# Global instance
secure_assets = SecureAssetAccess()
