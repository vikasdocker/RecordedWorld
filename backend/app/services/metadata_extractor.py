"""
Video Metadata Extraction

Extracts metadata from video files using OpenCV:
- Resolution, FPS, codec, duration
- Frame count, bitrate estimation
- File hash for deduplication
- Content analysis (average brightness, motion)
"""

import cv2
import numpy as np
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List
import os
import struct


@dataclass
class VideoMetadata:
    """Complete metadata for a video file."""
    # Basic info
    file_path: str
    file_size_bytes: int
    file_hash_sha256: str

    # Video properties
    width: int
    height: int
    fps: float
    total_frames: int
    duration_seconds: float
    codec_str: str
    codec_fourcc: int

    # Computed properties
    resolution_mp: float
    bitrate_estimate_kbps: Optional[float] = None
    megapixels_per_second: float = 0.0

    # Content analysis
    mean_brightness: float = 0.0
    mean_sharpness: float = 0.0
    has_audio_track: bool = False

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "file_hash_sha256": self.file_hash_sha256,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration_seconds,
            "codec": self.codec_str,
            "resolution_mp": round(self.resolution_mp, 2),
            "bitrate_estimate_kbps": self.bitrate_estimate_kbps,
            "megapixels_per_second": round(self.megapixels_per_second, 2),
            "mean_brightness": round(self.mean_brightness, 2),
            "mean_sharpness": round(self.mean_sharpness, 2),
        }


def extract_video_metadata(file_path: str, sample_frames: int = 10) -> VideoMetadata:
    """
    Extract complete metadata from a video file.

    Args:
        file_path: Path to video file
        sample_frames: Number of frames to sample for content analysis

    Returns:
        VideoMetadata with all extracted properties
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size = path.stat().st_size
    file_hash = _compute_file_hash(file_path)

    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {file_path}")

    # Basic properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))

    if fps <= 0:
        fps = 30.0

    duration = total_frames / fps
    codec_str = _decode_fourcc(fourcc)
    resolution_mp = (width * height) / 1_000_000
    mp_per_sec = resolution_mp * fps if fps > 0 else 0

    # Bitrate estimation
    bitrate = None
    if duration > 0:
        bitrate = (file_size * 8) / (duration * 1000)  # kbps

    # Content analysis (sample frames)
    brightnesses = []
    sharpnesses = []
    sample_interval = max(1, total_frames // max(sample_frames, 1))

    for i in range(0, total_frames, sample_interval):
        if len(brightnesses) >= sample_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightnesses.append(float(np.mean(gray)))
            sharpnesses.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))

    cap.release()

    return VideoMetadata(
        file_path=str(path.absolute()),
        file_size_bytes=file_size,
        file_hash_sha256=file_hash,
        width=width,
        height=height,
        fps=round(fps, 2),
        total_frames=total_frames,
        duration_seconds=round(duration, 2),
        codec_str=codec_str,
        codec_fourcc=fourcc,
        resolution_mp=round(resolution_mp, 2),
        bitrate_estimate_kbps=round(bitrate, 0) if bitrate else None,
        megapixels_per_second=round(mp_per_sec, 2),
        mean_brightness=round(float(np.mean(brightnesses)), 2) if brightnesses else 0,
        mean_sharpness=round(float(np.mean(sharpnesses)), 2) if sharpnesses else 0,
    )


def extract_metadata_batch(file_paths: List[str]) -> List[VideoMetadata]:
    """Extract metadata from multiple video files."""
    results = []
    for path in file_paths:
        try:
            results.append(extract_video_metadata(path))
        except Exception as e:
            results.append(VideoMetadata(
                file_path=path, file_size_bytes=0, file_hash_sha256="",
                width=0, height=0, fps=0, total_frames=0, duration_seconds=0,
                codec_str="ERROR", codec_fourcc=0, resolution_mp=0,
            ))
    return results


def _compute_file_hash(file_path: str, chunk_size: int = 8192) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def _decode_fourcc(fourcc_int: int) -> str:
    """Decode OpenCV FOURCC integer to string."""
    try:
        return "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])
    except Exception:
        return "UNKNOWN"


def compare_video_metadata(meta1: VideoMetadata, meta2: VideoMetadata) -> dict:
    """
    Compare two video metadata entries.
    Returns a similarity report.
    """
    same_codec = meta1.codec_str == meta2.codec_str
    same_resolution = meta1.width == meta2.width and meta1.height == meta2.height
    similar_fps = abs(meta1.fps - meta2.fps) < 1.0
    same_hash = meta1.file_hash_sha256 == meta2.file_hash_sha256
    similar_duration = abs(meta1.duration_seconds - meta2.duration_seconds) < 2.0

    return {
        "identical_file": same_hash,
        "same_codec": same_codec,
        "same_resolution": same_resolution,
        "similar_fps": similar_fps,
        "similar_duration": similar_duration,
        "likely_duplicate": same_hash or (same_resolution and similar_fps and similar_duration),
    }
