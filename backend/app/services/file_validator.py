"""
File Validation

Validates uploaded video files for:
- Format verification (magic bytes + extension)
- File size limits
- Video integrity (OpenCV can decode)
- Duration limits
- Resolution limits
"""

import os
import cv2
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple


ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
ALLOWED_MIME_TYPES = {
    "video/mp4", "video/quicktime", "video/x-msvideo",
    "video/x-matroska", "video/webm", "video/3gpp",
}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
MIN_FILE_SIZE_BYTES = 1024  # 1 KB
MAX_DURATION_SECONDS = 600  # 10 minutes
MIN_DURATION_SECONDS = 1.0  # 1 second
MAX_RESOLUTION_MP = 20.0  # 20 megapixels
MIN_FPS = 5.0
MAX_FPS = 240.0

# Magic bytes for common video formats
MAGIC_BYTES = {
    b"\x00\x00\x00\x1c\x66\x74\x79\x70": "mp4",
    b"\x00\x00\x00\x18\x66\x74\x79\x70": "mp4",
    b"\x00\x00\x00\x14\x66\x74\x79\x70": "mp4",
    b"\x00\x00\x00\x20\x66\x74\x79\x70": "mp4",
    b"\x52\x49\x46\x46": "avi",
    b"\x1a\x45\xdf\xa3": "mkv",
    b"\x52\x61\x6e\x64": "mov",
}


@dataclass
class ValidationResult:
    """Result of file validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    file_size_bytes: int
    detected_format: Optional[str]


def validate_video_file(
    file_path: str,
    max_size_bytes: int = MAX_FILE_SIZE_BYTES,
    max_duration_seconds: int = MAX_DURATION_SECONDS,
    max_resolution_mp: float = MAX_RESOLUTION_MP,
) -> ValidationResult:
    """
    Validate a video file.

    Args:
        file_path: Path to the video file
        max_size_bytes: Maximum allowed file size
        max_duration_seconds: Maximum allowed duration
        max_resolution_mp: Maximum resolution in megapixels

    Returns:
        ValidationResult with errors/warnings
    """
    errors = []
    warnings = []
    path = Path(file_path)

    # Check file exists
    if not path.exists():
        return ValidationResult(
            valid=False, errors=["File does not exist"], warnings=[],
            file_size_bytes=0, detected_format=None,
        )

    # File size check
    file_size = path.stat().st_size
    if file_size < MIN_FILE_SIZE_BYTES:
        errors.append(f"File too small: {file_size} bytes (minimum {MIN_FILE_SIZE_BYTES})")
    elif file_size > max_size_bytes:
        errors.append(f"File too large: {file_size / 1024 / 1024:.1f} MB (maximum {max_size_bytes / 1024 / 1024:.0f} MB)")

    # Extension check
    ext = path.suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported format: {ext} (allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))})")

    # Magic bytes check
    detected_format = _detect_format(file_path)
    if detected_format and ext.lstrip(".") not in detected_format:
        warnings.append(f"Extension {ext} doesn't match detected format: {detected_format}")

    # OpenCV integrity check
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        errors.append("File is not a valid video (OpenCV cannot open)")
        cap.release()
        return ValidationResult(
            valid=len(errors) == 0, errors=errors, warnings=warnings,
            file_size_bytes=file_size, detected_format=detected_format,
        )

    # Duration check
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / max(fps, 1)

    if duration < MIN_DURATION_SECONDS:
        errors.append(f"Video too short: {duration:.1f}s (minimum {MIN_DURATION_SECONDS}s)")
    elif duration > max_duration_seconds:
        errors.append(f"Video too long: {duration:.1f}s (maximum {max_duration_seconds}s)")

    # Resolution check
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    resolution_mp = (width * height) / 1_000_000

    if resolution_mp > max_resolution_mp:
        errors.append(f"Resolution too high: {resolution_mp:.1f}MP (maximum {max_resolution_mp:.0f}MP)")

    if fps > 0 and fps < MIN_FPS:
        warnings.append(f"Low FPS: {fps:.1f} (recommended >= {MIN_FPS})")
    elif fps > MAX_FPS:
        warnings.append(f"Very high FPS: {fps:.1f}")

    # Frame count check
    if total_frames == 0:
        errors.append("Video has no frames")

    cap.release()

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        file_size_bytes=file_size,
        detected_format=detected_format,
    )


def validate_image_file(file_path: str) -> ValidationResult:
    """Validate an image file."""
    errors = []
    warnings = []
    path = Path(file_path)

    if not path.exists():
        return ValidationResult(
            valid=False, errors=["File does not exist"], warnings=[],
            file_size_bytes=0, detected_format=None,
        )

    file_size = path.stat().st_size
    if file_size < 100:
        errors.append("File too small")

    img = cv2.imread(file_path)
    if img is None:
        errors.append("Not a valid image file")
    else:
        h, w = img.shape[:2]
        if w < 64 or h < 64:
            warnings.append(f"Very small image: {w}x{h}")

    return ValidationResult(
        valid=len(errors) == 0, errors=errors, warnings=warnings,
        file_size_bytes=file_size, detected_format=path.suffix.lstrip("."),
    )


def check_file_integrity(file_path: str) -> Tuple[bool, str]:
    """
    Quick integrity check - can OpenCV read the file.
    Returns (is_valid, message).
    """
    cap = cv2.VideoCapture(file_path)
    if not cap.isOpened():
        return False, "Cannot open file"

    ret, frame = cap.read()
    cap.release()

    if not ret:
        return False, "Cannot read frames"

    return True, "OK"


def _detect_format(file_path: str) -> Optional[str]:
    """Detect video format from magic bytes."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(16)
        for magic, fmt in MAGIC_BYTES.items():
            if header[:len(magic)] == magic:
                return fmt
    except Exception:
        pass
    return None
