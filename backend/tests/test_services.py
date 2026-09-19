"""Tests for Phase 21: Backend Architecture — service layer tests."""

import pytest
import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.player_service import PlayerService
from app.services.social_service import SocialService
from app.services.moderation_service import ModerationService


def unique_name(prefix: str = "svc") -> str:
    """Generate a unique username."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


class TestAuthService:
    def test_create_user(self, db):
        """Can create a new user."""
        name = unique_name("auth")
        user = AuthService.create_user(
            db, username=name, email=f"{name}@test.com", password="secret123"
        )
        assert user.username == name
        assert user.id is not None

    def test_create_duplicate_username(self, db):
        """Cannot create user with duplicate username."""
        name = unique_name("dup")
        AuthService.create_user(db, name, f"{name}@test.com", "pass")
        with pytest.raises(ValueError, match="Username already taken"):
            AuthService.create_user(db, name, f"{name}2@test.com", "pass")

    def test_authenticate_success(self, db):
        """Can authenticate with correct credentials."""
        name = unique_name("login")
        user = AuthService.create_user(db, name, f"{name}@test.com", "mypass")
        result = AuthService.authenticate(db, name, "mypass")
        assert result is not None
        assert result.id == user.id

    def test_authenticate_wrong_password(self, db):
        """Authentication fails with wrong password."""
        name = unique_name("wrong")
        AuthService.create_user(db, name, f"{name}@test.com", "correct")
        result = AuthService.authenticate(db, name, "incorrect")
        assert result is None

    def test_authenticate_nonexistent(self, db):
        """Authentication fails for nonexistent user."""
        result = AuthService.authenticate(db, "nonexistent_user_xyz_99999", "pass")
        assert result is None

    def test_update_profile(self, db):
        """Can update user profile."""
        name = unique_name("prof")
        user = AuthService.create_user(db, name, f"{name}@test.com", "pass")
        updated = AuthService.update_profile(
            db, user.id, display_name="New Name", location_sharing=False
        )
        assert updated.display_name == "New Name"
        assert updated.location_sharing is False


class TestPlayerService:
    def test_set_online_offline(self):
        """Player can be set online and offline."""
        PlayerService.set_online(999, "ws_123")
        assert PlayerService.is_online(999)
        PlayerService.set_offline(999)
        assert not PlayerService.is_online(999)

    def test_online_count(self):
        """Online count tracks players."""
        before = PlayerService.get_online_count()
        PlayerService.set_online(998, "ws_456")
        assert PlayerService.get_online_count() == before + 1
        PlayerService.set_offline(998)

    def test_visibility(self):
        """Player visibility can be set and retrieved."""
        PlayerService.set_visibility(997, "friends_only")
        assert PlayerService.get_visibility(997) == "friends_only"
        # Default is public
        assert PlayerService.get_visibility(99999) == "public"

    def test_invalid_visibility(self, db):
        """Invalid visibility raises error."""
        with pytest.raises(ValueError):
            PlayerService.set_visibility(1, "invalid_vis")

    def test_can_see_player(self):
        """Visibility rules are enforced."""
        PlayerService.set_visibility(100, "hidden")
        assert not PlayerService.can_see_player(200, 100, are_friends=False)
        assert PlayerService.can_see_player(100, 100, are_friends=False)  # self

        PlayerService.set_visibility(101, "friends_only")
        assert not PlayerService.can_see_player(200, 101, are_friends=False)
        assert PlayerService.can_see_player(200, 101, are_friends=True)

        PlayerService.set_visibility(102, "public")
        assert PlayerService.can_see_player(200, 102, are_friends=False)


class TestSocialService:
    def test_create_report(self, db):
        """Can create a report."""
        report = SocialService.create_report(
            target_type="location", target_id=1, reason="spam"
        )
        assert report["target_type"] == "location"
        assert report["reason"] == "spam"
        assert report["status"] == "pending"

    def test_create_invalid_report(self, db):
        """Invalid report reason raises error."""
        with pytest.raises(ValueError):
            SocialService.create_report("location", 1, "invalid_reason")

    def test_get_reports(self, db):
        """Can get reports."""
        SocialService.create_report("player", 42, "harassment")
        reports = SocialService.get_reports()
        assert len(reports) > 0

    def test_update_report_status(self, db):
        """Can update report status."""
        report = SocialService.create_report("location", 99, "spam")
        updated = SocialService.update_report_status(report["id"], "resolved")
        assert updated["status"] == "resolved"


class TestModerationService:
    def test_content_policy_clean(self):
        """Clean content passes policy."""
        violations = ModerationService.check_content_policy(
            "Beautiful Park", "A nice park for walking"
        )
        assert len(violations) == 0

    def test_content_policy_blocked_word(self):
        """Blocked word triggers violation."""
        violations = ModerationService.check_content_policy("spam location")
        assert any("spam" in v for v in violations)

    def test_content_policy_title_too_short(self):
        """Short title triggers violation."""
        violations = ModerationService.check_content_policy("Hi")
        assert any("too short" in v for v in violations)

    def test_content_policy_url(self):
        """URL in title triggers violation."""
        violations = ModerationService.check_content_policy("Visit http://bit.ly/abc")
        assert any("Blocked pattern" in v for v in violations)
