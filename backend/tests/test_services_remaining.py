"""Tests for Phase 21 remaining services: world, media, reconstruction, asset, multiplayer, notification."""

import pytest
import tempfile
from pathlib import Path

from app.core.geospatial import WGS84Coordinate
from app.services.world_service import WorldService
from app.services.media_service import MediaService
from app.services.reconstruction_service import ReconstructionService
from app.services.asset_service import AssetService
from app.services.multiplayer_service import MultiplayerService
from app.services.notification_service import NotificationService


class TestWorldService:
    def test_initialize(self):
        """Can initialize world with origin."""
        WorldService.initialize(WGS84Coordinate(40.785, -73.968))
        assert WorldService.get_manager() is not None

    def test_register_unregister_location(self):
        """Can register and unregister locations."""
        WorldService.initialize(WGS84Coordinate(0, 0))
        WorldService.register_location(1, WGS84Coordinate(0.001, 0.001), {"title": "Test"})
        assert WorldService.get_location_count() >= 1
        WorldService.unregister_location(1)

    def test_register_unregister_player(self):
        """Can register and unregister players."""
        WorldService.register_player(100, {"name": "Player1"})
        assert WorldService.get_player_count() >= 1
        WorldService.unregister_player(100)

    def test_update_player_position(self):
        """Can update player position."""
        WorldService.register_player(200, {"name": "Player2"})
        WorldService.update_player_position(200, {"x": 10, "y": 0, "z": 20})
        WorldService.unregister_player(200)

    def test_get_state(self):
        """Can get world state."""
        state = WorldService.get_state()
        assert hasattr(state, "locations")
        assert hasattr(state, "players")


class TestMediaService:
    def test_validate_video_nonexistent(self):
        """Validation fails for nonexistent file."""
        valid, msg = MediaService.validate_video(Path("/nonexistent.mp4"))
        assert not valid

    def test_validate_video_bad_extension(self):
        """Validation fails for bad extension."""
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            path = Path(f.name)
        try:
            valid, msg = MediaService.validate_video(path)
            assert not valid
            assert "Unsupported" in msg
        finally:
            path.unlink()

    def test_get_file_hash(self):
        """Can compute file hash."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            path = Path(f.name)
        try:
            h = MediaService.get_file_hash(path)
            assert len(h) == 64  # SHA256
        finally:
            path.unlink()

    def test_get_file_info(self):
        """Can get file info."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
            f.write(b"test")
            path = Path(f.name)
        try:
            info = MediaService.get_file_info(path)
            assert "size_bytes" in info
            assert info["extension"] == ".mp4"
        finally:
            path.unlink()


class TestReconstructionService:
    def test_create_job(self):
        """Can create a reconstruction job."""
        job = ReconstructionService.create_job(capture_id=1, user_id=1)
        assert job.job_id is not None
        assert job.status == "queued"

    def test_get_job(self):
        """Can get a job by ID."""
        job = ReconstructionService.create_job(capture_id=2, user_id=2)
        found = ReconstructionService.get_job(job.job_id)
        assert found is not None
        assert found.capture_id == 2

    def test_update_job_status(self):
        """Can update job status."""
        job = ReconstructionService.create_job(capture_id=3, user_id=3)
        updated = ReconstructionService.update_job_status(
            job.job_id, "processing", progress=50
        )
        assert updated.status == "processing"
        assert updated.progress == 50

    def test_complete_job(self):
        """Can complete a job."""
        job = ReconstructionService.create_job(capture_id=4, user_id=4)
        completed = ReconstructionService.update_job_status(
            job.job_id, "completed", result_asset_id="asset_123"
        )
        assert completed.status == "completed"
        assert completed.completed_at is not None

    def test_cancel_job(self):
        """Can cancel a queued job."""
        job = ReconstructionService.create_job(capture_id=5, user_id=5)
        assert ReconstructionService.cancel_job(job.job_id)
        assert job.status == "cancelled"

    def test_get_user_jobs(self):
        """Can get jobs for a user."""
        ReconstructionService.create_job(capture_id=6, user_id=999)
        jobs = ReconstructionService.get_user_jobs(999)
        assert len(jobs) >= 1


class TestAssetService:
    def test_register_asset(self):
        """Can register an asset."""
        asset = AssetService.register_asset(
            "test_asset_1", Path("/tmp/test.glb"), format="glb",
            vertex_count=100, face_count=50, file_size_bytes=1024
        )
        assert asset["id"] == "test_asset_1"

    def test_get_asset(self):
        """Can get asset by ID."""
        AssetService.register_asset("test_asset_2", Path("/tmp/test2.glb"))
        found = AssetService.get_asset("test_asset_2")
        assert found is not None

    def test_get_asset_url(self):
        """Can get asset URL."""
        AssetService.register_asset("abc123", Path("/tmp/abc.glb"))
        url = AssetService.get_asset_url("abc123")
        assert url.startswith("/assets/")
        assert "abc123" in url

    def test_delete_asset(self):
        """Can delete an asset."""
        AssetService.register_asset("delete_me", Path("/tmp/delete.glb"))
        assert AssetService.delete_asset("delete_me")
        assert AssetService.get_asset("delete_me") is None

    def test_get_asset_count(self):
        """Can get asset count."""
        count = AssetService.get_asset_count()
        assert count >= 0


class TestMultiplayerService:
    def test_connect_disconnect(self):
        """Can connect and disconnect players."""
        conn = MultiplayerService.connect(1, "player1", "ws_001")
        assert conn.player_id == 1
        assert MultiplayerService.get_connection_count() >= 1

        disconnected = MultiplayerService.disconnect("ws_001")
        assert disconnected is not None

    def test_update_position(self):
        """Can update player position."""
        MultiplayerService.connect(2, "player2", "ws_002")
        MultiplayerService.update_position("ws_002", {"x": 10, "y": 0, "z": 5})
        conn = MultiplayerService.get_connection("ws_002")
        assert conn.position["x"] == 10
        MultiplayerService.disconnect("ws_002")

    def test_set_color(self):
        """Can set player color."""
        MultiplayerService.connect(3, "player3", "ws_003")
        MultiplayerService.set_color("ws_003", "#ff0000")
        conn = MultiplayerService.get_connection("ws_003")
        assert conn.color == "#ff0000"
        # Color persists in cache
        assert MultiplayerService.get_player_color("player3") == "#ff0000"
        MultiplayerService.disconnect("ws_003")

    def test_set_visibility(self):
        """Can set player visibility."""
        MultiplayerService.connect(4, "player4", "ws_004")
        MultiplayerService.set_visibility("ws_004", "hidden")
        conn = MultiplayerService.get_connection("ws_004")
        assert conn.visibility == "hidden"
        MultiplayerService.disconnect("ws_004")

    def test_color_persists_across_reconnect(self):
        """Color persists across disconnect/reconnect."""
        MultiplayerService.connect(5, "player5", "ws_005")
        MultiplayerService.set_color("ws_005", "#aabbcc")
        MultiplayerService.disconnect("ws_005")

        conn = MultiplayerService.connect(5, "player5", "ws_006")
        assert conn.color == "#aabbcc"
        MultiplayerService.disconnect("ws_006")


class TestNotificationService:
    def test_create_notification(self):
        """Can create a notification."""
        notif = NotificationService.create(
            user_id=1, type="friend_request",
            title="New Request", message="User2 wants to be friends"
        )
        assert notif.id is not None
        assert not notif.read

    def test_get_notifications(self):
        """Can get notifications."""
        NotificationService.create(
            user_id=2, type="system", title="Welcome", message="Hello!"
        )
        notifs = NotificationService.get_notifications(2)
        assert len(notifs) >= 1

    def test_mark_read(self):
        """Can mark notification as read."""
        notif = NotificationService.create(
            user_id=3, type="system", title="Test", message="Test"
        )
        assert NotificationService.mark_read(3, notif.id)
        notifs = NotificationService.get_notifications(3, unread_only=True)
        assert all(n.id != notif.id for n in notifs)

    def test_mark_all_read(self):
        """Can mark all as read."""
        NotificationService.create(user_id=4, type="system", title="A", message="A")
        NotificationService.create(user_id=4, type="system", title="B", message="B")
        count = NotificationService.mark_all_read(4)
        assert count >= 2

    def test_get_unread_count(self):
        """Can get unread count."""
        NotificationService.create(user_id=5, type="system", title="C", message="C")
        unread = NotificationService.get_unread_count(5)
        assert unread >= 1

    def test_delete_notification(self):
        """Can delete a notification."""
        notif = NotificationService.create(
            user_id=6, type="system", title="D", message="D"
        )
        assert NotificationService.delete_notification(6, notif.id)

    def test_clear_all(self):
        """Can clear all notifications."""
        NotificationService.create(user_id=7, type="system", title="E", message="E")
        count = NotificationService.clear_all(7)
        assert count >= 1
