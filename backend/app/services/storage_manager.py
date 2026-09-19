"""
Storage Lifecycle Management

Manages the lifecycle of uploaded files:
- Temporary storage during upload
- Processing workspace
- Final storage after processing
- Cleanup of old/stale files
- Disk usage tracking
"""

import os
import shutil
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class StorageStats:
    """Storage usage statistics."""
    total_files: int
    total_size_bytes: int
    video_size_bytes: int
    model_size_bytes: int
    thumbnail_size_bytes: int
    temp_size_bytes: int
    oldest_file_age_days: Optional[float]
    newest_file_age_days: Optional[float]

    @property
    def total_size_mb(self) -> float:
        return self.total_size_bytes / (1024 * 1024)

    def to_dict(self) -> dict:
        return {
            "total_files": self.total_files,
            "total_size_bytes": self.total_size_bytes,
            "total_size_mb": round(self.total_size_mb, 2),
            "video_size_mb": round(self.video_size_bytes / 1024 / 1024, 2),
            "model_size_mb": round(self.model_size_bytes / 1024 / 1024, 2),
            "thumbnail_size_mb": round(self.thumbnail_size_bytes / 1024 / 1024, 2),
            "temp_size_mb": round(self.temp_size_bytes / 1024 / 1024, 2),
            "oldest_file_age_days": self.oldest_file_age_days,
            "newest_file_age_days": self.newest_file_age_days,
        }


class StorageManager:
    """Manages file storage lifecycle."""

    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"}
    MODEL_EXTENSIONS = {".obj", ".glb", ".gltf", ".ply", ".stl"}
    THUMBNAIL_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
    TEMP_EXTENSIONS = {".tmp", ".part"}

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir = self.base_dir / "uploads"
        self.processing_dir = self.base_dir / "processing"
        self.models_dir = self.base_dir / "models"
        self.thumbnails_dir = self.base_dir / "thumbnails"
        self.temp_dir = self.base_dir / "temp"

        for d in [self.uploads_dir, self.processing_dir, self.models_dir,
                  self.thumbnails_dir, self.temp_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def get_capture_dir(self, capture_id: int) -> Path:
        """Get the upload directory for a specific capture."""
        d = self.uploads_dir / f"capture_{capture_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_processing_dir(self, capture_id: int) -> Path:
        """Get the processing workspace for a capture."""
        d = self.processing_dir / f"capture_{capture_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_model_path(self, capture_id: int, filename: str = "model.glb") -> Path:
        """Get the final model path for a capture."""
        d = self.models_dir / f"capture_{capture_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d / filename

    def get_thumbnail_path(self, capture_id: int, filename: str = "thumb.jpg") -> Path:
        """Get the thumbnail path for a capture."""
        d = self.thumbnails_dir / f"capture_{capture_id}"
        d.mkdir(parents=True, exist_ok=True)
        return d / filename

    def move_to_processing(self, capture_id: int, file_path: str) -> Path:
        """Move an uploaded file to the processing workspace."""
        src = Path(file_path)
        dst_dir = self.get_processing_dir(capture_id)
        dst = dst_dir / src.name
        shutil.move(str(src), str(dst))
        return dst

    def finalize_capture(
        self,
        capture_id: int,
        model_path: Optional[str] = None,
        texture_path: Optional[str] = None,
        thumbnail_path: Optional[str] = None,
    ) -> dict:
        """
        Move processed files to final storage locations.
        Returns paths of moved files.
        """
        result = {}

        if model_path:
            dst = self.get_model_path(capture_id)
            shutil.copy2(model_path, str(dst))
            result["model_path"] = str(dst)

        if thumbnail_path:
            dst = self.get_thumbnail_path(capture_id)
            shutil.copy2(thumbnail_path, str(dst))
            result["thumbnail_path"] = str(dst)

        return result

    def cleanup_capture(self, capture_id: int, keep_model: bool = True):
        """
        Clean up temporary and processing files for a capture.
        Optionally keeps the final model.
        """
        # Clean processing dir
        proc_dir = self.processing_dir / f"capture_{capture_id}"
        if proc_dir.exists():
            shutil.rmtree(str(proc_dir))

        # Clean temp files
        for tmp_file in self.temp_dir.glob(f"capture_{capture_id}_*"):
            tmp_file.unlink()

        # Optionally clean uploads (keep raw video for reprocessing)
        if not keep_model:
            upload_dir = self.uploads_dir / f"capture_{capture_id}"
            if upload_dir.exists():
                shutil.rmtree(str(upload_dir))

    def cleanup_old_files(self, max_age_days: int = 30, dry_run: bool = True) -> dict:
        """
        Remove files older than max_age_days.

        Args:
            max_age_days: Maximum age in days
            dry_run: If True, only report what would be deleted

        Returns:
            Summary of cleanup actions
        """
        cutoff = time.time() - (max_age_days * 86400)
        files_to_remove = []
        total_size = 0

        for dirpath in [self.temp_dir, self.processing_dir]:
            for f in dirpath.rglob("*"):
                if f.is_file() and f.stat().st_mtime < cutoff:
                    files_to_remove.append(str(f))
                    total_size += f.stat().st_size

        if not dry_run:
            for f in files_to_remove:
                os.remove(f)

        return {
            "files_to_remove": len(files_to_remove),
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "dry_run": dry_run,
            "removed": [] if dry_run else files_to_remove,
        }

    def get_stats(self) -> StorageStats:
        """Get storage usage statistics."""
        total_files = 0
        total_size = 0
        video_size = 0
        model_size = 0
        thumb_size = 0
        temp_size = 0
        oldest_mtime = float("inf")
        newest_mtime = 0

        for f in self.base_dir.rglob("*"):
            if not f.is_file():
                continue

            total_files += 1
            size = f.stat().st_size
            total_size += size
            mtime = f.stat().st_mtime

            if mtime < oldest_mtime:
                oldest_mtime = mtime
            if mtime > newest_mtime:
                newest_mtime = mtime

            ext = f.suffix.lower()
            if ext in self.VIDEO_EXTENSIONS:
                video_size += size
            elif ext in self.MODEL_EXTENSIONS:
                model_size += size
            elif ext in self.THUMBNAIL_EXTENSIONS:
                thumb_size += size
            elif ext in self.TEMP_EXTENSIONS or str(f).startswith(str(self.temp_dir)):
                temp_size += size

        now = time.time()
        oldest_days = (now - oldest_mtime) / 86400 if oldest_mtime < float("inf") else None
        newest_days = (now - newest_mtime) / 86400 if newest_mtime > 0 else None

        return StorageStats(
            total_files=total_files,
            total_size_bytes=total_size,
            video_size_bytes=video_size,
            model_size_bytes=model_size,
            thumbnail_size_bytes=thumb_size,
            temp_size_bytes=temp_size,
            oldest_file_age_days=round(oldest_days, 1) if oldest_days else None,
            newest_file_age_days=round(newest_days, 1) if newest_days else None,
        )

    def ensure_disk_space(self, required_bytes: int) -> bool:
        """Check if there's enough disk space."""
        usage = shutil.disk_usage(str(self.base_dir))
        return usage.free >= required_bytes
