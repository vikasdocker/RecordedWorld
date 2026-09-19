"""Tests for Phase 26: Security — rate limiting, validation, audit, signed URLs."""

import time
import pytest
from app.services.rate_limiter import RateLimiter, api_limiter
from app.services.input_validation import (
    sanitize_string, validate_username, validate_email, validate_hex_color,
    validate_title, validate_description, validate_latitude, validate_longitude,
    validate_search_query, validate_moderation_state, validate_visibility,
)
from app.services.audit_service import AuditLogger, AuditEvents, audit_logger
from app.services.secure_assets import SecureAssetAccess, secure_assets


class TestRateLimiter:
    def test_allows_requests(self):
        """Allows requests under limit."""
        limiter = RateLimiter(window_seconds=60, max_requests=5)
        allowed, info = limiter.is_allowed("user1")
        assert allowed is True
        assert info["remaining"] == 4

    def test_blocks_when_exceeded(self):
        """Blocks when limit exceeded."""
        limiter = RateLimiter(window_seconds=60, max_requests=3)
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        allowed, info = limiter.is_allowed("user1")
        assert allowed is False
        assert info["remaining"] == 0

    def test_different_keys_independent(self):
        """Different keys have independent limits."""
        limiter = RateLimiter(window_seconds=60, max_requests=2)
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        allowed, _ = limiter.is_allowed("user2")
        assert allowed is True

    def test_get_usage(self):
        """Can get usage stats."""
        limiter = RateLimiter(window_seconds=60, max_requests=10)
        limiter.is_allowed("user1")
        usage = limiter.get_usage("user1")
        assert usage["count"] == 1
        assert usage["remaining"] == 9

    def test_reset(self):
        """Can reset rate limit."""
        limiter = RateLimiter(window_seconds=60, max_requests=2)
        limiter.is_allowed("user1")
        limiter.is_allowed("user1")
        limiter.reset("user1")
        allowed, _ = limiter.is_allowed("user1")
        assert allowed is True

    def test_get_stats(self):
        """Can get global stats."""
        limiter = RateLimiter()
        stats = limiter.get_stats()
        assert "tracked_keys" in stats

    def test_global_limiters_exist(self):
        """Pre-configured limiters exist."""
        assert api_limiter is not None


class TestInputValidation:
    def test_sanitize_string(self):
        """Sanitize removes HTML and truncates."""
        result = sanitize_string("<script>alert('xss')</script>", max_length=10)
        assert "<script>" not in result
        assert len(result) <= 10

    def test_validate_username_valid(self):
        """Valid username passes."""
        ok, err = validate_username("player1")
        assert ok is True

    def test_validate_username_too_short(self):
        """Short username fails."""
        ok, err = validate_username("ab")
        assert ok is False

    def test_validate_username_invalid_chars(self):
        """Username with invalid chars fails."""
        ok, err = validate_username("user name!")
        assert ok is False

    def test_validate_email_valid(self):
        """Valid email passes."""
        ok, err = validate_email("test@example.com")
        assert ok is True

    def test_validate_email_invalid(self):
        """Invalid email fails."""
        ok, err = validate_email("not-an-email")
        assert ok is False

    def test_validate_hex_color_valid(self):
        """Valid hex color passes."""
        ok, err = validate_hex_color("#FF5733")
        assert ok is True

    def test_validate_hex_color_invalid(self):
        """Invalid hex color fails."""
        ok, err = validate_hex_color("red")
        assert ok is False

    def test_validate_title(self):
        """Valid title passes."""
        ok, err = validate_title("My Location")
        assert ok is True

    def test_validate_latitude(self):
        """Valid latitude passes."""
        ok, err = validate_latitude(45.0)
        assert ok is True

    def test_validate_latitude_invalid(self):
        """Invalid latitude fails."""
        ok, err = validate_latitude(100.0)
        assert ok is False

    def test_validate_longitude(self):
        """Valid longitude passes."""
        ok, err = validate_longitude(-73.0)
        assert ok is True

    def test_validate_longitude_invalid(self):
        """Invalid longitude fails."""
        ok, err = validate_longitude(200.0)
        assert ok is False

    def test_validate_search_query(self):
        """Valid search passes."""
        ok, err = validate_search_query("coffee shop")
        assert ok is True

    def test_validate_moderation_state(self):
        """Valid state passes."""
        ok, err = validate_moderation_state("approved")
        assert ok is True

    def test_validate_moderation_state_invalid(self):
        """Invalid state fails."""
        ok, err = validate_moderation_state("invalid")
        assert ok is False

    def test_validate_visibility(self):
        """Valid visibility passes."""
        ok, err = validate_visibility("public")
        assert ok is True

    def test_validate_visibility_invalid(self):
        """Invalid visibility fails."""
        ok, err = validate_visibility("visible")
        assert ok is False


class TestAuditLogger:
    def test_log_event(self):
        """Can log an event."""
        logger = AuditLogger()
        logger.log("test.event", user_id=1, ip_address="127.0.0.1")
        stats = logger.get_stats()
        assert stats["total_entries"] == 1

    def test_query_events(self):
        """Can query events."""
        logger = AuditLogger()
        logger.log("event.a", user_id=1)
        logger.log("event.b", user_id=2)
        logger.log("event.a", user_id=3)
        results = logger.query(event_type="event.a")
        assert len(results) == 2

    def test_query_by_user(self):
        """Can query by user."""
        logger = AuditLogger()
        logger.log("event.x", user_id=1)
        logger.log("event.y", user_id=2)
        results = logger.query(user_id=1)
        assert len(results) == 1

    def test_log_with_details(self):
        """Can log with details."""
        logger = AuditLogger()
        logger.log("test", details={"key": "value"})
        results = logger.query()
        assert results[0].details["key"] == "value"

    def test_log_failure(self):
        """Can log failures."""
        logger = AuditLogger()
        logger.log("test", success=False)
        results = logger.query()
        assert results[0].success is False

    def test_audit_events_constants(self):
        """Audit event constants exist."""
        assert AuditEvents.AUTH_LOGIN == "auth.login"
        assert AuditEvents.LOCATION_CREATE == "location.create"

    def test_global_logger(self):
        """Global logger exists."""
        assert audit_logger is not None


class TestSecureAssets:
    def test_generate_signed_url(self):
        """Can generate signed URL."""
        sa = SecureAssetAccess()
        url = sa.generate_signed_url("/assets/model.glb", expires_in_seconds=3600, user_id=1)
        assert "sig=" in url
        assert "expires=" in url

    def test_validate_signed_url(self):
        """Valid signed URL passes."""
        sa = SecureAssetAccess()
        import hashlib
        expires = int(time.time()) + 3600
        payload = f"/assets/model.glb:{expires}:1"
        import hmac as h
        sig = h.new(sa._secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
        ok, err = sa.validate_signed_url("/assets/model.glb", expires, 1, sig)
        assert ok is True

    def test_validate_expired_url(self):
        """Expired signed URL fails."""
        sa = SecureAssetAccess()
        import hashlib
        expires = int(time.time()) - 100  # expired
        payload = f"/assets/model.glb:{expires}:1"
        import hmac as h
        sig = h.new(sa._secret, payload.encode(), hashlib.sha256).hexdigest()[:16]
        ok, err = sa.validate_signed_url("/assets/model.glb", expires, 1, sig)
        assert ok is False
        assert "expired" in err.lower()

    def test_validate_bad_signature(self):
        """Bad signature fails."""
        sa = SecureAssetAccess()
        expires = int(time.time()) + 3600
        ok, err = sa.validate_signed_url("/assets/model.glb", expires, 1, "bad_sig")
        assert ok is False

    def test_generate_api_key(self):
        """Can generate API key."""
        sa = SecureAssetAccess()
        key = sa.generate_api_key()
        assert key.startswith("rw_")

    def test_hash_api_key(self):
        """Can hash API key."""
        sa = SecureAssetAccess()
        key = sa.generate_api_key()
        hashed = sa.hash_api_key(key)
        assert len(hashed) == 64  # SHA256 hex

    def test_global_instance(self):
        """Global instance exists."""
        assert secure_assets is not None
