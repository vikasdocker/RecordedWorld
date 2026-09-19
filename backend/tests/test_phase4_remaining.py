"""
Tests for Phase 4 remaining: Camera intrinsics, video quality, offline sync.
"""
import pytest
from app.services.camera_intrinsics import (
    CameraIntrinsicsService, CameraIntrinsics, DEVICE_INTRINSICS_DB,
    camera_intrinsics_service
)
from app.services.video_quality import (
    VideoQualityService, QualityPreset, QualityProfile, DeviceCapabilities,
    video_quality_service
)
from app.services.offline_sync import (
    OfflineSyncManager, OfflineCapture, SyncState, ConflictResolution,
    SyncBatch, offline_sync_manager
)


# --- Camera Intrinsics ---

class TestCameraIntrinsics:
    def test_get_known_device(self):
        service = CameraIntrinsicsService()
        intr = service.get_intrinsics("iphone_15_pro")
        assert intr is not None
        assert intr.focal_length_mm > 0

    def test_focal_length_px(self):
        intr = CameraIntrinsics(
            device_id="test", focal_length_mm=4.0,
            sensor_width_mm=6.17, sensor_height_mm=4.63,
            image_width_px=1920, image_height_px=1080,
        )
        assert intr.focal_length_x_px > 0
        assert intr.focal_length_y_px > 0

    def test_fov(self):
        intr = CameraIntrinsics(
            device_id="test", focal_length_mm=4.0,
            sensor_width_mm=6.17, sensor_height_mm=4.63,
        )
        assert intr.fov_horizontal_deg > 0
        assert intr.fov_vertical_deg > 0

    def test_projection_matrix(self):
        intr = CameraIntrinsics(
            device_id="test", focal_length_mm=4.0,
            sensor_width_mm=6.17, sensor_height_mm=4.63,
            image_width_px=1920, image_height_px=1080,
        )
        mat = intr.projection_matrix
        assert len(mat) == 3
        assert len(mat[0]) == 3

    def test_register_device(self):
        service = CameraIntrinsicsService()
        intr = CameraIntrinsics(
            device_id="custom_device", focal_length_mm=5.0,
            sensor_width_mm=6.0, sensor_height_mm=4.0,
        )
        service.register_device(intr)
        assert service.get_intrinsics("custom_device") is not None

    def test_estimate_from_metadata(self):
        service = CameraIntrinsicsService()
        intr = service.estimate_from_metadata(
            device_make="Apple", device_model="iPhone 15",
            image_width=4032, image_height=3024,
            focal_length_35mm=26.0,
        )
        assert intr.focal_length_mm > 0

    def test_undistort_no_distortion(self):
        service = CameraIntrinsicsService()
        intr = CameraIntrinsics(
            device_id="test", focal_length_mm=4.0,
            sensor_width_mm=6.0, sensor_height_mm=4.0,
            image_width_px=1920, image_height_px=1080,
        )
        x, y = service.undistort_point(960, 540, intr)
        assert x == 960
        assert y == 540

    def test_to_dict(self):
        intr = CameraIntrinsics(
            device_id="test", focal_length_mm=4.0,
            sensor_width_mm=6.0, sensor_height_mm=4.0,
        )
        d = intr.to_dict()
        assert "focal_length_mm" in d
        assert "fov_h_deg" in d

    def test_stats(self):
        service = CameraIntrinsicsService()
        stats = service.get_stats()
        assert stats["registered_devices"] > 0


# --- Video Quality ---

class TestVideoQuality:
    def test_get_profile(self):
        service = VideoQualityService()
        profile = service.get_profile(QualityPreset.HIGH)
        assert profile is not None
        assert profile.resolution_width == 3840

    def test_get_all_profiles(self):
        service = VideoQualityService()
        profiles = service.get_all_profiles()
        assert len(profiles) == 5

    def test_select_optimal_no_caps(self):
        service = VideoQualityService()
        profile = service.select_optimal_quality("unknown_device")
        assert profile.preset == QualityPreset.MEDIUM

    def test_select_optimal_4k_device(self):
        service = VideoQualityService()
        service.register_device(DeviceCapabilities(
            device_id="good_phone",
            max_resolution_width=3840,
            max_resolution_height=2160,
            max_fps=60.0,
            supports_hdr=True,
            supports_4k=True,
            storage_free_mb=50000.0,
        ))
        profile = service.select_optimal_quality("good_phone")
        assert profile.preset in (QualityPreset.ULTRA, QualityPreset.HIGH)

    def test_select_optimal_low_storage(self):
        service = VideoQualityService()
        service.register_device(DeviceCapabilities(
            device_id="low_storage",
            max_resolution_width=3840,
            max_resolution_height=2160,
            max_fps=60.0,
            storage_free_mb=100.0,
        ))
        profile = service.select_optimal_quality("low_storage", duration_minutes=60)
        assert profile.preset in (QualityPreset.LOW, QualityPreset.MINIMAL)

    def test_storage_estimate(self):
        service = VideoQualityService()
        est = service.get_storage_estimate(QualityPreset.HIGH, 5.0)
        assert est > 0

    def test_recommended_for_3d(self):
        service = VideoQualityService()
        profile = service.get_recommended_for_3d()
        assert profile.preset == QualityPreset.HIGH

    def test_profile_to_dict(self):
        profile = QualityProfile(
            preset=QualityPreset.MEDIUM,
            resolution_width=1920, resolution_height=1080,
            fps=30.0, bitrate_mbps=20.0,
        )
        d = profile.to_dict()
        assert "resolution" in d
        assert "fps" in d

    def test_mb_per_minute(self):
        profile = QualityProfile(
            preset=QualityPreset.HIGH,
            resolution_width=3840, resolution_height=2160,
            fps=30.0, bitrate_mbps=50.0,
        )
        assert profile.estimated_mb_per_minute == 375.0

    def test_stats(self):
        service = VideoQualityService()
        stats = service.get_stats()
        assert stats["total_profiles"] == 5


# --- Offline Sync ---

class TestOfflineSync:
    def test_queue_capture(self):
        mgr = OfflineSyncManager()
        cap = mgr.queue_capture(
            "c1", user_id=1, device_id="phone",
            filename="v.mp4", file_size_bytes=1024,
            local_path="/storage/c1.mp4",
        )
        assert isinstance(cap, OfflineCapture)
        assert cap.sync_state == SyncState.PENDING

    def test_queue_max_limit(self):
        mgr = OfflineSyncManager()
        mgr.MAX_QUEUE_SIZE = 2
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        mgr.queue_capture("c2", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c2")
        result = mgr.queue_capture("c3", user_id=1, device_id="phone",
                                   filename="v.mp4", file_size_bytes=1024, local_path="/c3")
        assert result is None

    def test_get_pending(self):
        mgr = OfflineSyncManager()
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        pending = mgr.get_pending(1)
        assert len(pending) == 1

    def test_create_sync_batch(self):
        mgr = OfflineSyncManager()
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        batch = mgr.create_sync_batch(1)
        assert isinstance(batch, SyncBatch)
        assert batch.capture_count == 1

    def test_complete_sync(self):
        mgr = OfflineSyncManager()
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        batch = mgr.create_sync_batch(1)
        synced = mgr.complete_sync(batch.batch_id, {"c1": True})
        assert synced == 1
        cap = mgr.captures["c1"]
        assert cap.sync_state == SyncState.SYNCED

    def test_complete_sync_partial_failure(self):
        mgr = OfflineSyncManager()
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        mgr.queue_capture("c2", user_id=1, device_id="phone",
                          filename="v2.mp4", file_size_bytes=2048, local_path="/c2")
        batch = mgr.create_sync_batch(1)
        synced = mgr.complete_sync(batch.batch_id, {"c1": True, "c2": False})
        assert synced == 1

    def test_resolve_conflict(self):
        mgr = OfflineSyncManager()
        cap = mgr.queue_capture("c1", user_id=1, device_id="phone",
                                filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        cap.sync_state = SyncState.CONFLICT
        assert mgr.resolve_conflict("c1", ConflictResolution.KEEP_LOCAL)
        assert cap.sync_state == SyncState.PENDING

    def test_cleanup_expired(self):
        mgr = OfflineSyncManager()
        cap = mgr.queue_capture("c1", user_id=1, device_id="phone",
                                filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        cap.created_at = 0  # force expired
        removed = mgr.cleanup_expired()
        assert removed == 1

    def test_queue_stats(self):
        mgr = OfflineSyncManager()
        mgr.queue_capture("c1", user_id=1, device_id="phone",
                          filename="v.mp4", file_size_bytes=1024, local_path="/c1")
        stats = mgr.get_queue_stats(1)
        assert stats["total_queued"] == 1

    def test_capture_properties(self):
        cap = OfflineCapture(
            id="c1", user_id=1, device_id="phone",
            filename="v.mp4", file_size_bytes=1024*1024, local_path="/c1",
        )
        assert cap.file_size_mb == 1.0
        assert cap.can_retry

    def test_stats(self):
        mgr = OfflineSyncManager()
        stats = mgr.get_stats()
        assert "total_captures" in stats
