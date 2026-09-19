"""Additional unit tests for services — coverage expansion."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import user, capture, game_world, location, friendship, category, tag, reconstruction_job, gameplay  # noqa: F401
from app.models.user import User


@pytest.fixture(scope="module")
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(
        id=200,
        username="unit_test_user",
        email="unit@test.com",
        password_hash="salt:hash",
    )
    session.add(user)
    session.commit()
    yield session
    session.close()


class TestAuthService:
    def test_create_user(self, db):
        """Can create user via auth service."""
        from app.services.auth_service import AuthService
        user = AuthService.create_user(db, "newuser2", "new2@test.com", "password123")
        assert user is not None

    def test_authenticate(self, db):
        """Can authenticate user."""
        from app.services.auth_service import AuthService
        result = AuthService.authenticate(db, "newuser2", "password123")
        assert result is not None


class TestPlayerService:
    def test_set_online(self):
        """Can set player online."""
        from app.services.player_service import PlayerService
        PlayerService.set_online(999, "ws_123")
        assert PlayerService.is_online(999)

    def test_set_offline(self):
        """Can set player offline."""
        from app.services.player_service import PlayerService
        PlayerService.set_online(999, "ws_123")
        PlayerService.set_offline(999)
        assert not PlayerService.is_online(999)

    def test_get_online_count(self):
        """Can get online count."""
        from app.services.player_service import PlayerService
        count = PlayerService.get_online_count()
        assert isinstance(count, int)


class TestFriendshipService:
    def test_send_request(self, db):
        """Can send friend request."""
        from app.services.friendship_service import FriendshipService
        friendship = FriendshipService.send_request(db, 200, 201)
        assert friendship is not None

    def test_get_friends(self, db):
        """Can get friends list."""
        from app.services.friendship_service import FriendshipService
        friends = FriendshipService.get_friends(db, 200)
        assert isinstance(friends, list)


class TestNotificationService:
    def test_create_notification(self):
        """Can create notification."""
        from app.services.notification_service import NotificationService
        notif = NotificationService.create(200, "info", "Title", "Test notification")
        assert notif is not None

    def test_get_notifications(self):
        """Can get notifications."""
        from app.services.notification_service import NotificationService
        notifs = NotificationService.get_notifications(200)
        assert isinstance(notifs, list)


class TestAssetService:
    def test_get_asset_count(self):
        """Can get asset count."""
        from app.services.asset_service import AssetService
        count = AssetService.get_asset_count()
        assert isinstance(count, int)

    def test_get_total_size(self):
        """Can get total size."""
        from app.services.asset_service import AssetService
        size = AssetService.get_total_size()
        assert isinstance(size, int)


class TestMediaService:
    def test_get_file_hash(self, tmp_path):
        """Can get file hash."""
        from app.services.media_service import MediaService
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        hash_val = MediaService.get_file_hash(test_file)
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256
