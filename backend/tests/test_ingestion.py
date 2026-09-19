import pytest
import cv2
import numpy as np
import os
import tempfile
import time
from pathlib import Path

from app.services.file_validator import (
    validate_video_file, validate_image_file, check_file_integrity,
    ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_DURATION_SECONDS,
)
from app.services.metadata_extractor import (
    extract_video_metadata, _compute_file_hash, _decode_fourcc, compare_video_metadata,
)
from app.services.storage_manager import StorageManager


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_test_video(path: str, num_frames: int = 30, fps: float = 10.0,
                        width: int = 320, height: int = 240):
    """Create a synthetic test video."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        x = int(50 + (i * 3) % 200)
        cv2.rectangle(frame, (x, 50), (x + 80, 190), (255, 128, 64), -1)
        cv2.putText(frame, f"F{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        out.write(frame)
    out.release()


def _create_test_image(path: str, width: int = 320, height: int = 240):
    """Create a test image."""
    img = np.zeros((height, width, 3), dtype=np.uint8)
    cv2.rectangle(img, (50, 50), (270, 190), (255, 128, 64), -1)
    cv2.putText(img, "TEST", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    cv2.imwrite(path, img)


# --- File Validator Tests ---

class TestFileValidator:
    def test_valid_video(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path)

        result = validate_video_file(video_path)

        assert result.valid is True
        assert len(result.errors) == 0

    def test_nonexistent_file(self, temp_dir):
        result = validate_video_file(os.path.join(temp_dir, "nope.mp4"))
        assert result.valid is False
        assert "does not exist" in result.errors[0]

    def test_wrong_extension(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.txt")
        _create_test_video(video_path)

        result = validate_video_file(video_path)
        # Extension mismatch but OpenCV can still read it
        assert any("Unsupported format" in e for e in result.errors)

    def test_too_short_video(self, temp_dir):
        video_path = os.path.join(temp_dir, "short.mp4")
        _create_test_video(video_path, num_frames=5, fps=10.0)  # 0.5s

        result = validate_video_file(video_path, max_duration_seconds=10)
        assert result.valid is False
        assert any("too short" in e for e in result.errors)

    def test_invalid_file(self, temp_dir):
        bad_path = os.path.join(temp_dir, "bad.mp4")
        with open(bad_path, "w") as f:
            f.write("not a video")

        result = validate_video_file(bad_path)
        assert result.valid is False

    def test_image_validation(self, temp_dir):
        img_path = os.path.join(temp_dir, "test.jpg")
        _create_test_image(img_path)

        result = validate_image_file(img_path)
        assert result.valid is True

    def test_invalid_image(self, temp_dir):
        img_path = os.path.join(temp_dir, "bad.jpg")
        with open(img_path, "w") as f:
            f.write("not an image")

        result = validate_image_file(img_path)
        assert result.valid is False

    def test_integrity_check(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path)

        ok, msg = check_file_integrity(video_path)
        assert ok is True
        assert msg == "OK"

    def test_integrity_bad_file(self, temp_dir):
        bad_path = os.path.join(temp_dir, "bad.mp4")
        with open(bad_path, "w") as f:
            f.write("garbage")

        ok, msg = check_file_integrity(bad_path)
        assert ok is False


# --- Metadata Extractor Tests ---

class TestMetadataExtractor:
    def test_extract_metadata(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path, num_frames=30, fps=15.0, width=640, height=480)

        meta = extract_video_metadata(video_path)

        assert meta.width == 640
        assert meta.height == 480
        assert abs(meta.fps - 15.0) < 1.0
        assert meta.total_frames == 30
        assert meta.duration_seconds > 0
        assert meta.resolution_mp > 0
        assert meta.file_size_bytes > 0
        assert len(meta.file_hash_sha256) == 64  # SHA-256

    def test_file_hash_deterministic(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path)

        hash1 = _compute_file_hash(video_path)
        hash2 = _compute_file_hash(video_path)
        assert hash1 == hash2

    def test_different_files_different_hashes(self, temp_dir):
        v1 = os.path.join(temp_dir, "v1.mp4")
        v2 = os.path.join(temp_dir, "v2.mp4")
        _create_test_video(v1, num_frames=10)
        _create_test_video(v2, num_frames=20)

        assert _compute_file_hash(v1) != _compute_file_hash(v2)

    def test_decode_fourcc(self):
        # MP4V
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        result = _decode_fourcc(fourcc)
        assert result == "mp4v"

    def test_metadata_to_dict(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path)

        meta = extract_video_metadata(video_path)
        d = meta.to_dict()

        assert "width" in d
        assert "height" in d
        assert "fps" in d
        assert "file_hash_sha256" in d

    def test_compare_same_video(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path)

        meta1 = extract_video_metadata(video_path)
        meta2 = extract_video_metadata(video_path)

        comparison = compare_video_metadata(meta1, meta2)
        assert comparison["identical_file"] is True
        assert comparison["likely_duplicate"] is True

    def test_compare_different_videos(self, temp_dir):
        v1 = os.path.join(temp_dir, "v1.mp4")
        v2 = os.path.join(temp_dir, "v2.mp4")
        _create_test_video(v1, num_frames=10, width=320, height=240)
        _create_test_video(v2, num_frames=60, width=1920, height=1080)

        meta1 = extract_video_metadata(v1)
        meta2 = extract_video_metadata(v2)

        comparison = compare_video_metadata(meta1, meta2)
        assert comparison["identical_file"] is False
        assert comparison["same_resolution"] is False

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            extract_video_metadata("nonexistent.mp4")


# --- Storage Manager Tests ---

class TestStorageManager:
    def test_initialization(self, temp_dir):
        sm = StorageManager(temp_dir)
        assert sm.base_dir.exists()
        assert sm.uploads_dir.exists()
        assert sm.models_dir.exists()

    def test_get_capture_dir(self, temp_dir):
        sm = StorageManager(temp_dir)
        d = sm.get_capture_dir(42)
        assert d.exists()
        assert "capture_42" in str(d)

    def test_get_model_path(self, temp_dir):
        sm = StorageManager(temp_dir)
        p = sm.get_model_path(1, "scene.glb")
        assert p.name == "scene.glb"
        assert p.parent.exists()

    def test_move_to_processing(self, temp_dir):
        sm = StorageManager(temp_dir)
        src = os.path.join(temp_dir, "video.mp4")
        _create_test_video(src)

        dst = sm.move_to_processing(1, src)
        assert dst.exists()
        assert not os.path.exists(src)

    def test_finalize_capture(self, temp_dir):
        sm = StorageManager(temp_dir)
        model_src = os.path.join(temp_dir, "model.obj")
        with open(model_src, "w") as f:
            f.write("v 0 0 0\n")

        result = sm.finalize_capture(1, model_path=model_src)
        assert "model_path" in result
        assert os.path.exists(result["model_path"])

    def test_cleanup_capture(self, temp_dir):
        sm = StorageManager(temp_dir)
        proc_dir = sm.get_processing_dir(1)
        (proc_dir / "temp.txt").touch()

        sm.cleanup_capture(1)
        assert not proc_dir.exists()

    def test_cleanup_old_files(self, temp_dir):
        sm = StorageManager(temp_dir)
        old_file = sm.temp_dir / "old.tmp"
        old_file.touch()
        # Set modification time to 60 days ago
        os.utime(str(old_file), (time.time() - 60 * 86400,) * 2)

        result = sm.cleanup_old_files(max_age_days=30, dry_run=True)
        assert result["files_to_remove"] == 1

    def test_get_stats(self, temp_dir):
        sm = StorageManager(temp_dir)
        # Create some files
        (sm.uploads_dir / "test.mp4").touch()
        (sm.models_dir / "model.glb").touch()

        stats = sm.get_stats()
        assert stats.total_files >= 2

    def test_ensure_disk_space(self, temp_dir):
        sm = StorageManager(temp_dir)
        assert sm.ensure_disk_space(1) is True
        assert sm.ensure_disk_space(999999999999999) is False
