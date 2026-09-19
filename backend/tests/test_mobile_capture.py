"""
Tests for Phase 4: Mobile Capture services.
"""
import pytest
import math
from app.services.capture_metadata import (
    CaptureMetadataValidator, CaptureMetadata, ValidationSeverity, capture_validator
)
from app.services.device_orientation import (
    DeviceOrientationProcessor, OrientationSample, EulerAngles, orientation_processor
)
from app.services.upload_session import (
    UploadSessionManager, UploadSession, UploadState, UploadChunk, upload_manager
)


# --- Capture Metadata ---

class TestCaptureMetadata:
    def test_validate_valid_metadata(self):
        validator = CaptureMetadataValidator()
        raw = {
            "duration_seconds": 15.0,
            "resolution": "1920x1080",
            "fps": 30,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "gps_accuracy_m": 5.0,
        }
        meta, issues = validator.validate(raw)
        assert isinstance(meta, CaptureMetadata)
        assert meta.duration_seconds == 15.0
        assert meta.resolution_width == 1920
        assert meta.latitude == 40.7128

    def test_validate_missing_duration(self):
        validator = CaptureMetadataValidator()
        raw = {"resolution": "1920x1080", "fps": 30}
        meta, issues = validator.validate(raw)
        assert any(i.field == "duration_seconds" for i in issues)

    def test_validate_invalid_resolution(self):
        validator = CaptureMetadataValidator()
        raw = {"duration_seconds": 10, "resolution": "invalid", "fps": 30}
        meta, issues = validator.validate(raw)
        assert meta.resolution_width == 1920  # defaults

    def test_validate_invalid_coordinate(self):
        validator = CaptureMetadataValidator()
        raw = {"duration_seconds": 10, "latitude": 100.0, "longitude": -74.0}
        meta, issues = validator.validate(raw)
        assert meta.latitude is None

    def test_validate_fps(self):
        validator = CaptureMetadataValidator()
        raw = {"duration_seconds": 10, "fps": 60}
        meta, issues = validator.validate(raw)
        assert meta.fps == 60.0

    def test_quality_score(self):
        validator = CaptureMetadataValidator()
        meta = CaptureMetadata(
            duration_seconds=15.0,
            resolution_width=1920, resolution_height=1080,
            gps_accuracy_m=3.0, latitude=40.0,
        )
        score = validator.get_quality_score(meta)
        assert 0 <= score <= 100

    def test_resolution_string(self):
        meta = CaptureMetadata(resolution_width=1920, resolution_height=1080)
        assert meta.resolution_string == "1920x1080"

    def test_aspect_ratio(self):
        meta = CaptureMetadata(resolution_width=1920, resolution_height=1080)
        assert meta.aspect_ratio == pytest.approx(16/9, abs=0.01)

    def test_to_dict(self):
        meta = CaptureMetadata(
            duration_seconds=10.0,
            resolution_width=1920, resolution_height=1080,
        )
        d = meta.to_dict()
        assert "duration_seconds" in d
        assert "resolution" in d

    def test_heading_wraparound(self):
        validator = CaptureMetadataValidator()
        raw = {"duration_seconds": 10, "heading": 400.0}
        meta, issues = validator.validate(raw)
        assert meta.heading == 40.0


# --- Device Orientation ---

class TestDeviceOrientation:
    def test_process_samples(self):
        processor = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_x=0, accel_y=0, accel_z=9.81),
            OrientationSample(timestamp_ms=10, accel_x=0, accel_y=0, accel_z=9.81),
        ]
        result = processor.process_samples(samples)
        assert result is not None
        assert result.is_upright
        assert result.confidence > 0.5

    def test_process_empty(self):
        processor = DeviceOrientationProcessor()
        result = processor.process_samples([])
        assert result is None

    def test_euler_to_quaternion(self):
        euler = EulerAngles(heading=0, pitch=0, roll=0)
        quat = euler.to_quaternion()
        assert len(quat) == 4
        assert abs(quat[0] - 1.0) < 0.01  # w should be ~1 for identity

    def test_euler_to_rotation_matrix(self):
        euler = EulerAngles(heading=0, pitch=0, roll=0)
        mat = euler.to_rotation_matrix()
        assert mat.shape == (3, 3)
        # Identity matrix check
        assert abs(mat[0][0] - 1.0) < 0.01
        assert abs(mat[1][1] - 1.0) < 0.01
        assert abs(mat[2][2] - 1.0) < 0.01

    def test_get_capture_orientation(self):
        processor = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_x=0, accel_y=0, accel_z=9.81),
            OrientationSample(timestamp_ms=10, accel_x=0, accel_y=0, accel_z=9.81),
        ]
        heading, pitch, roll = processor.get_capture_orientation(samples)
        assert isinstance(heading, float)
        assert isinstance(pitch, float)
        assert isinstance(roll, float)

    def test_gravity_estimation(self):
        processor = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_x=1.0, accel_y=2.0, accel_z=9.81),
        ]
        result = processor.process_samples(samples)
        assert result is not None
        # Gravity should converge toward [0, 0, 9.81]
        gz = result.gravity_vector[2]
        assert gz > 0

    def test_gyro_integration(self):
        processor = DeviceOrientationProcessor()
        samples = [
            OrientationSample(timestamp_ms=0, accel_z=9.81, gyro_z=0.1),
            OrientationSample(timestamp_ms=100, accel_z=9.81, gyro_z=0.1),
        ]
        result = processor.process_samples(samples)
        assert result is not None
        assert result.euler.heading >= 0

    def test_smooth_orientation(self):
        processor = DeviceOrientationProcessor()
        for _ in range(5):
            processor.orientation_history.append(
                processor.process_samples([
                    OrientationSample(timestamp_ms=0, accel_z=9.81)
                ])
            )
        smoothed = processor.smooth_orientation(3)
        assert smoothed is not None


# --- Upload Session ---

class TestUploadSession:
    def test_create_session(self):
        mgr = UploadSessionManager()
        session = mgr.create_session(
            "s1", user_id=1, filename="video.mp4",
            total_size=5 * 1024 * 1024, chunk_size=1024 * 1024,
        )
        assert isinstance(session, UploadSession)
        assert session.total_chunks == 5

    def test_get_session(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1024)
        session = mgr.get_session("s1")
        assert session is not None

    def test_mark_chunk_uploaded(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=2048)
        assert mgr.mark_chunk_uploaded("s1", 0)
        session = mgr.get_session("s1")
        assert session.uploaded_chunks == 1

    def test_complete_upload(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1024)
        mgr.mark_chunk_uploaded("s1", 0)
        session = mgr.get_session("s1")
        assert session.state == UploadState.COMPLETED

    def test_pause_resume(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=2048, chunk_size=1024)
        mgr.mark_chunk_uploaded("s1", 0)
        assert mgr.pause_session("s1")
        session = mgr.get_session("s1")
        assert session.state == UploadState.PAUSED
        assert mgr.resume_session("s1")
        assert session.state == UploadState.UPLOADING

    def test_get_resumable_chunks(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=3072, chunk_size=1024)
        mgr.mark_chunk_uploaded("s1", 0)
        resumable = mgr.get_resumable_chunks("s1")
        assert 0 not in resumable
        assert 1 in resumable

    def test_delete_session(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1024)
        assert mgr.delete_session("s1")
        assert mgr.get_session("s1") is None

    def test_max_sessions_per_user(self):
        mgr = UploadSessionManager()
        for i in range(5):
            mgr.create_session(f"s{i}", user_id=1, filename="v.mp4", total_size=1024)
        result = mgr.create_session("s5", user_id=1, filename="v.mp4", total_size=1024)
        assert result is None

    def test_progress(self):
        mgr = UploadSessionManager()
        session = mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=4096, chunk_size=1024)
        mgr.mark_chunk_uploaded("s1", 0)
        mgr.mark_chunk_uploaded("s1", 1)
        assert session.progress == pytest.approx(0.5, abs=0.01)

    def test_get_stats(self):
        mgr = UploadSessionManager()
        mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1024)
        stats = mgr.get_stats()
        assert stats["total_sessions"] == 1

    def test_cleanup_expired(self):
        mgr = UploadSessionManager()
        session = mgr.create_session("s1", user_id=1, filename="v.mp4", total_size=1024)
        session.last_activity = 0  # force expired
        removed = mgr.cleanup_expired()
        assert removed == 1
