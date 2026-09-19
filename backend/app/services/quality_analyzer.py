"""
Video Frame Quality Analysis

Analyzes individual frames and video segments for:
- Blur detection (Laplacian, Tenengrad, Brenner)
- Exposure analysis (histogram, clipping)
- Contrast measurement
- Noise estimation
- Overall quality scoring

Used to filter frames before 3D reconstruction.
"""

import cv2
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple


class QualityGrade(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECTED = "rejected"


@dataclass
class FrameQuality:
    """Quality metrics for a single frame."""
    blur_score: float
    blur_method: str
    exposure_ok: bool
    contrast_score: float
    noise_estimate: float
    overall_score: float  # 0.0 to 1.0
    grade: QualityGrade
    issues: List[str]


@dataclass
class VideoQualityReport:
    """Aggregate quality report for a video or set of frames."""
    total_frames: int
    accepted_frames: int
    rejected_frames: int
    mean_blur: float
    mean_exposure: float
    mean_contrast: float
    quality_distribution: dict  # grade -> count
    recommended_fps: float
    issues: List[str]


def analyze_frame(frame: np.ndarray) -> FrameQuality:
    """
    Comprehensive quality analysis of a single frame.

    Args:
        frame: BGR image (HxWx3 numpy array)

    Returns:
        FrameQuality with all metrics
    """
    issues = []

    # Blur detection (Laplacian variance)
    blur_score = detect_blur_laplacian(frame)
    blur_ok = blur_score >= 100.0
    if not blur_ok:
        issues.append(f"blurry (score={blur_score:.1f})")

    # Exposure analysis
    exposure_ok, clipped_pct = analyze_exposure(frame)
    if not exposure_ok:
        issues.append(f"poor exposure ({clipped_pct:.1f}% clipped)")

    # Contrast
    contrast = measure_contrast(frame)
    if contrast < 30.0:
        issues.append(f"low contrast ({contrast:.1f})")

    # Noise estimation
    noise = estimate_noise(frame)
    if noise > 25.0:
        issues.append(f"high noise ({noise:.1f})")

    # Overall score (weighted combination)
    blur_norm = min(blur_score / 500.0, 1.0)  # normalize to 0-1
    contrast_norm = min(contrast / 100.0, 1.0)
    exposure_norm = 1.0 if exposure_ok else 0.3
    noise_norm = max(0, 1.0 - noise / 50.0)

    overall = (
        0.35 * blur_norm
        + 0.25 * exposure_norm
        + 0.20 * contrast_norm
        + 0.20 * noise_norm
    )

    # Grade
    if overall >= 0.7:
        grade = QualityGrade.HIGH
    elif overall >= 0.45:
        grade = QualityGrade.MEDIUM
    elif overall >= 0.25:
        grade = QualityGrade.LOW
    else:
        grade = QualityGrade.REJECTED

    return FrameQuality(
        blur_score=round(blur_score, 2),
        blur_method="laplacian",
        exposure_ok=exposure_ok,
        contrast_score=round(contrast, 2),
        noise_estimate=round(noise, 2),
        overall_score=round(overall, 4),
        grade=grade,
        issues=issues,
    )


def analyze_video_quality(
    video_path: str,
    sample_count: int = 30,
) -> VideoQualityReport:
    """
    Analyze quality across a video by sampling frames.

    Args:
        video_path: Path to video file
        sample_count: Number of frames to sample

    Returns:
        VideoQualityReport with aggregate metrics
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames == 0:
        cap.release()
        return VideoQualityReport(
            total_frames=0, accepted_frames=0, rejected_frames=0,
            mean_blur=0, mean_exposure=0, mean_contrast=0,
            quality_distribution={}, recommended_fps=1.0, issues=["empty video"],
        )

    # Sample frames evenly
    sample_indices = np.linspace(0, total_frames - 1, min(sample_count, total_frames), dtype=int)

    qualities = []
    for idx in sample_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret:
            qualities.append(analyze_frame(frame))

    cap.release()

    if not qualities:
        return VideoQualityReport(
            total_frames=total_frames, accepted_frames=0, rejected_frames=0,
            mean_blur=0, mean_exposure=0, mean_contrast=0,
            quality_distribution={}, recommended_fps=1.0, issues=["could not read frames"],
        )

    blur_scores = [q.blur_score for q in qualities]
    contrasts = [q.contrast_score for q in qualities]
    accepted = sum(1 for q in qualities if q.grade in (QualityGrade.HIGH, QualityGrade.MEDIUM))
    rejected = len(qualities) - accepted

    # Quality distribution
    dist = {}
    for q in qualities:
        dist[q.grade.value] = dist.get(q.grade.value, 0) + 1

    # Estimate recommended FPS based on quality
    high_quality_ratio = dist.get("high", 0) / len(qualities)
    if high_quality_ratio > 0.7:
        recommended_fps = 2.0
    elif high_quality_ratio > 0.4:
        recommended_fps = 1.0
    else:
        recommended_fps = 0.5

    issues = []
    mean_blur = float(np.mean(blur_scores))
    if mean_blur < 150:
        issues.append("video is generally blurry")

    mean_contrast = float(np.mean(contrasts))
    if mean_contrast < 40:
        issues.append("video has low contrast")

    return VideoQualityReport(
        total_frames=total_frames,
        accepted_frames=accepted,
        rejected_frames=rejected,
        mean_blur=round(mean_blur, 2),
        mean_exposure=round(float(np.mean([1.0 if q.exposure_ok else 0.0 for q in qualities])), 2),
        mean_contrast=round(mean_contrast, 2),
        quality_distribution=dist,
        recommended_fps=round(recommended_fps, 1),
        issues=issues,
    )


def detect_blur_laplacian(frame: np.ndarray) -> float:
    """Laplacian variance blur detection. Higher = sharper."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def detect_blur_tenengrad(frame: np.ndarray) -> float:
    """Tenengrad (gradient magnitude) blur detection. Higher = sharper."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float64)
    gx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    return float(np.mean(gx ** 2 + gy ** 2))


def analyze_exposure(
    frame: np.ndarray,
    clip_threshold: float = 0.01,
) -> Tuple[bool, float]:
    """
    Analyze exposure quality.

    Returns:
        (is_ok, clipped_percentage)
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    total_pixels = gray.size

    overexposed = np.sum(gray >= 250) / total_pixels
    underexposed = np.sum(gray <= 5) / total_pixels
    clipped = overexposed + underexposed

    return clipped < clip_threshold, float(clipped * 100)


def measure_contrast(frame: np.ndarray) -> float:
    """Measure contrast as standard deviation of grayscale intensities."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray))


def estimate_noise(frame: np.ndarray) -> float:
    """
    Estimate noise level using the Median Absolute Deviation method.
    Returns estimated noise standard deviation.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float64)

    # High-pass filter to isolate noise
    h, w = gray.shape
    # Use a simple difference-based estimator
    noise_map = np.abs(gray[1:-1, 1:-1] - 0.25 * (
        gray[:-2, 1:-1] + gray[2:, 1:-1] +
        gray[1:-1, :-2] + gray[1:-1, 2:]
    ))

    return float(np.median(noise_map) * 1.4826)  # MAD to std conversion
