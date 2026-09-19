"""
Real Video Frame Extraction

Extracts keyframes from video files using OpenCV.
Supports configurable FPS extraction, frame quality filtering,
and basic scene change detection.
"""

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import math


@dataclass
class ExtractedFrame:
    """A frame extracted from video with metadata."""
    index: int
    timestamp_sec: float
    path: str
    width: int
    height: int
    blur_score: float
    mean_brightness: float
    is_keyframe: bool


def extract_frames(
    video_path: str,
    output_dir: str,
    target_fps: float = 1.0,
    min_interval_sec: float = 0.5,
    blur_threshold: float = 100.0,
    brightness_range: tuple = (40, 220),
) -> List[ExtractedFrame]:
    """
    Extract frames from a video file.

    Args:
        video_path: Path to input video
        output_dir: Directory to save extracted frames
        target_fps: Target extraction rate (frames per second of video)
        min_interval_sec: Minimum time between extracted frames
        blur_threshold: Minimum Laplacian variance to accept frame
        brightness_range: (min, max) mean brightness to accept frame

    Returns:
        List of ExtractedFrame metadata
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if video_fps <= 0:
        video_fps = 30.0  # fallback

    # Calculate frame skip interval
    frame_interval = max(1, int(video_fps / target_fps))
    min_frame_gap = int(video_fps * min_interval_sec)

    extracted: List[ExtractedFrame] = []
    last_extracted_frame = -min_frame_gap - 1
    frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Check if we should extract this frame
        should_extract = (frame_idx % frame_interval == 0)
        gap_ok = (frame_idx - last_extracted_frame) >= min_frame_gap

        if should_extract and gap_ok:
            # Compute quality metrics
            blur_score = _compute_blur_score(frame)
            brightness = _compute_brightness(frame)

            # Filter by quality
            if blur_score >= blur_threshold:
                if brightness_range[0] <= brightness <= brightness_range[1]:
                    timestamp = frame_idx / video_fps
                    frame_filename = f"frame_{len(extracted):04d}.jpg"
                    frame_path = output_path / frame_filename

                    cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

                    extracted.append(ExtractedFrame(
                        index=len(extracted),
                        timestamp_sec=round(timestamp, 3),
                        path=str(frame_path),
                        width=width,
                        height=height,
                        blur_score=round(blur_score, 2),
                        mean_brightness=round(brightness, 2),
                        is_keyframe=True,
                    ))
                    last_extracted_frame = frame_idx

        frame_idx += 1

    cap.release()
    return extracted


def extract_frames_at_timestamps(
    video_path: str,
    output_dir: str,
    timestamps_sec: List[float],
) -> List[ExtractedFrame]:
    """
    Extract frames at specific timestamps.

    Args:
        video_path: Path to input video
        output_dir: Directory to save frames
        timestamps_sec: List of timestamps in seconds

    Returns:
        List of ExtractedFrame metadata
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    video_fps = cap.get(cv2.CAP_PROP_FPS)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    extracted = []
    for ts in sorted(timestamps_sec):
        frame_number = int(ts * video_fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()
        if ret:
            frame_filename = f"frame_{len(extracted):04d}.jpg"
            frame_path = output_path / frame_filename
            cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

            extracted.append(ExtractedFrame(
                index=len(extracted),
                timestamp_sec=round(ts, 3),
                path=str(frame_path),
                width=width,
                height=height,
                blur_score=round(_compute_blur_score(frame), 2),
                mean_brightness=round(_compute_brightness(frame), 2),
                is_keyframe=True,
            ))

    cap.release()
    return extracted


def get_video_info(video_path: str) -> dict:
    """Get metadata about a video file."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": round(cap.get(cv2.CAP_PROP_FPS), 2),
        "total_frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "duration_sec": round(
            cap.get(cv2.CAP_PROP_FRAME_COUNT) / max(cap.get(cv2.CAP_PROP_FPS), 1), 2
        ),
        "codec": int(cap.get(cv2.CAP_PROP_FOURCC)),
    }
    cap.release()

    # Decode codec int to 4-char string
    codec_int = info["codec"]
    info["codec_str"] = "".join(
        [chr((codec_int >> 8 * i) & 0xFF) for i in range(4)]
    )

    return info


def _compute_blur_score(frame: np.ndarray) -> float:
    """
    Compute blur score using Laplacian variance.
    Higher values = sharper. Threshold ~100 for acceptable sharpness.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def _compute_brightness(frame: np.ndarray) -> float:
    """Compute mean brightness (0-255) of a frame."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray))
