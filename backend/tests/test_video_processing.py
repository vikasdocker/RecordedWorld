import pytest
import cv2
import numpy as np
import os
import tempfile
from pathlib import Path

from app.services.frame_extractor import (
    extract_frames, get_video_info, _compute_blur_score, _compute_brightness
)
from app.services.quality_analyzer import (
    analyze_frame, detect_blur_laplacian, detect_blur_tenengrad,
    analyze_exposure, measure_contrast, estimate_noise, QualityGrade
)
from app.services.frame_deduplicator import (
    deduplicate_frames, _compute_ssim, _compute_hist_similarity
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def _create_test_video(path: str, num_frames: int = 30, fps: float = 10.0,
                        scene_change_at: int = None):
    """Create a synthetic test video with known properties."""
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, fps, (width, height))

    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        if scene_change_at and i >= scene_change_at:
            # Different scene - red instead of blue
            frame[:, :, 0] = 200  # B
            frame[:, :, 2] = 50   # R
        else:
            # Moving rectangle to create frame-to-frame variation
            x = int(50 + (i * 3) % 200)
            cv2.rectangle(frame, (x, 50), (x + 80, 190), (255, 128, 64), -1)
            # Add text for feature richness
            cv2.putText(frame, f"F{i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        out.write(frame)
    out.release()


def _create_blurry_video(path: str, num_frames: int = 10):
    """Create a blurry test video."""
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(path, fourcc, 10.0, (width, height))

    for i in range(num_frames):
        frame = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        # Heavy Gaussian blur
        frame = cv2.GaussianBlur(frame, (51, 51), 30)
        out.write(frame)
    out.release()


# --- Frame Extractor Tests ---

class TestFrameExtractor:
    def test_extract_frames_creates_files(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        output_dir = os.path.join(temp_dir, "frames")
        _create_test_video(video_path, num_frames=60)

        frames = extract_frames(
            video_path, output_dir, target_fps=2.0,
            blur_threshold=50.0, brightness_range=(10, 250),
        )

        assert len(frames) > 0
        for f in frames:
            assert os.path.exists(f.path)

    def test_extract_frames_metadata(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        output_dir = os.path.join(temp_dir, "frames")
        _create_test_video(video_path, num_frames=60)

        frames = extract_frames(video_path, output_dir, target_fps=1.0)

        for f in frames:
            assert f.width == 320
            assert f.height == 240
            assert f.timestamp_sec >= 0
            assert f.blur_score > 0

    def test_get_video_info(self, temp_dir):
        video_path = os.path.join(temp_dir, "test.mp4")
        _create_test_video(video_path, num_frames=30, fps=15.0)

        info = get_video_info(video_path)

        assert info["width"] == 320
        assert info["height"] == 240
        assert info["total_frames"] == 30
        assert info["fps"] > 0

    def test_blur_score_sharp_vs_blurry(self, temp_dir):
        # Sharp frame
        sharp = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(sharp, (10, 10), (90, 90), (255, 255, 255), 2)
        cv2.putText(sharp, "SHARP", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

        # Blurry frame
        blurry = cv2.GaussianBlur(sharp, (51, 51), 30)

        assert _compute_blur_score(sharp) > _compute_blur_score(blurry)

    def test_brightness_calculation(self):
        dark = np.zeros((100, 100, 3), dtype=np.uint8)
        bright = np.ones((100, 100, 3), dtype=np.uint8) * 255

        assert _compute_brightness(dark) < 10
        assert _compute_brightness(bright) > 245

    def test_invalid_video_raises(self, temp_dir):
        with pytest.raises(ValueError):
            extract_frames("nonexistent.mp4", temp_dir)


# --- Quality Analyzer Tests ---

class TestQualityAnalyzer:
    def test_analyze_sharp_frame(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.rectangle(frame, (50, 50), (270, 190), (255, 128, 64), -1)
        cv2.putText(frame, "TEST", (100, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)

        quality = analyze_frame(frame)

        assert quality.blur_score > 100
        assert quality.grade in (QualityGrade.HIGH, QualityGrade.MEDIUM)
        assert quality.overall_score > 0.3

    def test_analyze_blurry_frame(self):
        frame = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
        frame = cv2.GaussianBlur(frame, (51, 51), 30)

        quality = analyze_frame(frame)

        assert quality.blur_score < 100
        assert "blurry" in " ".join(quality.issues).lower() or quality.grade in (QualityGrade.LOW, QualityGrade.REJECTED)

    def test_blur_detection_methods(self):
        sharp = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(sharp, (10, 10), (90, 90), (255, 255, 255), 2)

        blurry = cv2.GaussianBlur(sharp, (51, 51), 30)

        lap_sharp = detect_blur_laplacian(sharp)
        lap_blurry = detect_blur_laplacian(blurry)
        ten_sharp = detect_blur_tenengrad(sharp)
        ten_blurry = detect_blur_tenengrad(blurry)

        assert lap_sharp > lap_blurry
        assert ten_sharp > ten_blurry

    def test_exposure_analysis(self):
        # Well-exposed frame
        good = np.ones((100, 100, 3), dtype=np.uint8) * 128
        is_ok, clipped = analyze_exposure(good)
        assert is_ok == True
        assert clipped < 1.0

        # Overexposed frame
        over = np.ones((100, 100, 3), dtype=np.uint8) * 255
        is_ok, clipped = analyze_exposure(over)
        assert is_ok == False

    def test_contrast_measurement(self):
        # High contrast
        high = np.zeros((100, 100, 3), dtype=np.uint8)
        high[:50, :, :] = 255

        # Low contrast
        low = np.ones((100, 100, 3), dtype=np.uint8) * 128

        assert measure_contrast(high) > measure_contrast(low)

    def test_noise_estimation(self):
        # Clean frame
        clean = np.ones((100, 100, 3), dtype=np.uint8) * 128

        # Noisy frame
        noisy = np.clip(
            np.ones((100, 100, 3), dtype=np.float64) * 128 + np.random.randn(100, 100, 3) * 50,
            0, 255
        ).astype(np.uint8)

        assert estimate_noise(clean) < estimate_noise(noisy)


# --- Frame Deduplicator Tests ---

class TestFrameDeduplicator:
    def test_identical_frames_detected(self, temp_dir):
        # Create two identical images
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.rectangle(img, (10, 10), (90, 90), (255, 128, 64), -1)

        path1 = os.path.join(temp_dir, "frame1.jpg")
        path2 = os.path.join(temp_dir, "frame2.jpg")
        cv2.imwrite(path1, img)
        cv2.imwrite(path2, img)

        result = deduplicate_frames([path1, path2], ssim_threshold=0.85)

        assert result.kept_count == 1
        assert result.removed_count == 1

    def test_different_frames_kept(self, temp_dir):
        # Create two different images
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.ones((100, 100, 3), dtype=np.uint8) * 255

        path1 = os.path.join(temp_dir, "frame1.jpg")
        path2 = os.path.join(temp_dir, "frame2.jpg")
        cv2.imwrite(path1, img1)
        cv2.imwrite(path2, img2)

        result = deduplicate_frames([path1, path2], ssim_threshold=0.85)

        assert result.kept_count == 2
        assert result.removed_count == 0

    def test_ssim_identical(self):
        img = np.random.randint(0, 255, (100, 100), dtype=np.uint8)
        assert _compute_ssim(img, img) > 0.99

    def test_ssim_different(self):
        img1 = np.zeros((100, 100), dtype=np.uint8)
        img2 = np.ones((100, 100), dtype=np.uint8) * 255
        assert _compute_ssim(img1, img2) < 0.5

    def test_hist_similarity_identical(self):
        # Use solid color images for reliable histogram comparison
        img = np.ones((100, 100, 3), dtype=np.uint8) * 128
        assert _compute_hist_similarity(img, img) > 0.99

    def test_hist_similarity_different(self):
        img1 = np.zeros((100, 100, 3), dtype=np.uint8)
        img2 = np.ones((100, 100, 3), dtype=np.uint8) * 255
        assert _compute_hist_similarity(img1, img2) < 0.5

    def test_empty_input(self):
        result = deduplicate_frames([])
        assert result.kept_count == 0
        assert result.removed_count == 0

    def test_single_frame(self):
        result = deduplicate_frames(["frame1.jpg"])
        assert result.kept_count == 1
        assert result.removed_count == 0
