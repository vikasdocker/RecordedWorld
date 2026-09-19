"""
Media Service

File upload, validation, and thumbnail management.
"""

import os
import uuid
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timezone

from app.core.config import settings


class MediaService:
    """Handles media file operations."""

    @staticmethod
    def get_upload_path(filename: str, user_id: int) -> Path:
        """Get the upload path for a file."""
        upload_dir = settings.UPLOAD_DIR / "captures" / str(user_id)
        upload_dir.mkdir(parents=True, exist_ok=True)
        return upload_dir / filename

    @staticmethod
    def validate_video(filepath: Path) -> Tuple[bool, str]:
        """Validate a video file."""
        if not filepath.exists():
            return False, "File does not exist"

        size_mb = filepath.stat().st_size / (1024 * 1024)
        if size_mb > 500:
            return False, f"File too large: {size_mb:.1f}MB (max 500MB)"

        ext = filepath.suffix.lower()
        if ext not in {".mp4", ".mov", ".avi", ".webm"}:
            return False, f"Unsupported format: {ext}"

        return True, "OK"

    @staticmethod
    def generate_thumbnail_path(video_path: Path, frame_number: int = 0) -> Path:
        """Generate thumbnail path for a video frame."""
        thumb_dir = settings.UPLOAD_DIR / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)
        thumb_name = f"{video_path.stem}_frame{frame_number}.jpg"
        return thumb_dir / thumb_name

    @staticmethod
    def get_file_hash(filepath: Path) -> str:
        """Compute SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def get_file_info(filepath: Path) -> dict:
        """Get file metadata."""
        stat = filepath.stat()
        return {
            "name": filepath.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "extension": filepath.suffix.lower(),
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }

    @staticmethod
    def cleanup_old_files(max_age_days: int = 30) -> int:
        """Remove files older than max_age_days. Returns count removed."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_days * 86400)
        removed = 0
        for root, dirs, files in os.walk(settings.UPLOAD_DIR):
            for f in files:
                filepath = Path(root) / f
                if filepath.stat().st_mtime < cutoff:
                    filepath.unlink()
                    removed += 1
        return removed
