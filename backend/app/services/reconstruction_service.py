"""
Reconstruction Service

3D reconstruction pipeline coordination.
"""

from typing import Optional, List, Dict
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone


@dataclass
class ReconstructionJob:
    """A 3D reconstruction job."""
    job_id: str
    capture_id: int
    user_id: int
    status: str  # queued, processing, completed, failed
    progress: float = 0.0  # 0-100
    result_asset_id: Optional[str] = None
    error: Optional[str] = None
    created_at: str = ""
    completed_at: Optional[str] = None


class ReconstructionService:
    """Manages 3D reconstruction pipeline."""

    _jobs: Dict[str, ReconstructionJob] = {}

    @classmethod
    def create_job(cls, capture_id: int, user_id: int) -> ReconstructionJob:
        """Create a new reconstruction job."""
        import uuid
        job_id = str(uuid.uuid4())[:12]
        job = ReconstructionJob(
            job_id=job_id,
            capture_id=capture_id,
            user_id=user_id,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        cls._jobs[job_id] = job
        return job

    @classmethod
    def get_job(cls, job_id: str) -> Optional[ReconstructionJob]:
        """Get a reconstruction job by ID."""
        return cls._jobs.get(job_id)

    @classmethod
    def update_job_status(
        cls,
        job_id: str,
        status: str,
        progress: float = 0,
        result_asset_id: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[ReconstructionJob]:
        """Update job status."""
        job = cls._jobs.get(job_id)
        if not job:
            return None
        job.status = status
        job.progress = progress
        if result_asset_id:
            job.result_asset_id = result_asset_id
        if error:
            job.error = error
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc).isoformat()
        return job

    @classmethod
    def get_user_jobs(cls, user_id: int) -> List[ReconstructionJob]:
        """Get all jobs for a user."""
        return [j for j in cls._jobs.values() if j.user_id == user_id]

    @classmethod
    def get_queue_length(cls) -> int:
        """Get number of queued jobs."""
        return sum(1 for j in cls._jobs.values() if j.status == "queued")

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        """Cancel a queued job."""
        job = cls._jobs.get(job_id)
        if not job or job.status != "queued":
            return False
        job.status = "cancelled"
        job.completed_at = datetime.now(timezone.utc).isoformat()
        return True
