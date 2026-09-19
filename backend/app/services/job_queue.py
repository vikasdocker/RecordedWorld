"""
Reconstruction Job Queue

In-memory job queue with async-ready architecture.
Replace with Redis/Celery for production.
"""

import asyncio
import uuid
from typing import Optional, List, Dict, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class JobStatus(str, Enum):
    CREATED = "created"
    QUEUED = "queued"
    PROCESSING = "processing"
    RECONSTRUCTING = "reconstructing"
    ALIGNING = "aligning"
    OPTIMIZING = "optimizing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"
    CANCELLED = "cancelled"


# Valid state transitions
VALID_TRANSITIONS = {
    JobStatus.CREATED: [JobStatus.QUEUED, JobStatus.CANCELLED],
    JobStatus.QUEUED: [JobStatus.PROCESSING, JobStatus.CANCELLED],
    JobStatus.PROCESSING: [JobStatus.RECONSTRUCTING, JobStatus.FAILED],
    JobStatus.RECONSTRUCTING: [JobStatus.ALIGNING, JobStatus.FAILED],
    JobStatus.ALIGNING: [JobStatus.OPTIMIZING, JobStatus.FAILED],
    JobStatus.OPTIMIZING: [JobStatus.VALIDATING, JobStatus.FAILED],
    JobStatus.VALIDATING: [JobStatus.COMPLETED, JobStatus.NEEDS_REVIEW, JobStatus.FAILED],
    JobStatus.COMPLETED: [],
    JobStatus.FAILED: [JobStatus.QUEUED],  # retry
    JobStatus.NEEDS_REVIEW: [JobStatus.QUEUED, JobStatus.CANCELLED],
    JobStatus.CANCELLED: [],
}


@dataclass
class Job:
    """A reconstruction job."""
    job_id: str
    user_id: int
    capture_id: Optional[int] = None
    status: JobStatus = JobStatus.CREATED
    progress: float = 0.0
    result_asset_id: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "user_id": self.user_id,
            "capture_id": self.capture_id,
            "status": self.status.value,
            "progress": self.progress,
            "result_asset_id": self.result_asset_id,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class JobPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_ORDER = {
    JobPriority.CRITICAL: 0,
    JobPriority.HIGH: 1,
    JobPriority.NORMAL: 2,
    JobPriority.LOW: 3,
}


class JobQueue:
    """In-memory job queue with state machine, priority, and dead letter support."""

    def __init__(self, max_retries: int = 3, dead_letter_max: int = 100):
        self._jobs: Dict[str, Job] = {}
        self._queue: List[str] = []  # job_ids in priority order
        self._workers: Dict[str, Callable] = {}
        self._processing: Optional[str] = None
        self._dead_letter: List[str] = []
        self._dead_letter_max = dead_letter_max
        self._max_retries = max_retries
        self._scheduled: Dict[str, float] = {}  # job_id -> run_after timestamp
        self._job_priorities: Dict[str, JobPriority] = {}

    def create_job(
        self,
        user_id: int,
        capture_id: Optional[int] = None,
        priority: JobPriority = JobPriority.NORMAL,
    ) -> Job:
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job = Job(job_id=job_id, user_id=user_id, capture_id=capture_id)
        self._jobs[job_id] = job
        self._job_priorities[job_id] = priority
        return job

    def enqueue(self, job_id: str) -> Job:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        self._transition(job, JobStatus.QUEUED)
        self._queue.append(job_id)
        self._sort_queue()
        return job

    def schedule(self, job_id: str, run_after: float) -> Job:
        """Schedule a job to run after a timestamp."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        self._scheduled[job_id] = run_after
        return job

    def dequeue(self) -> Optional[Job]:
        now = __import__("time").time()
        for jid in list(self._scheduled):
            if self._scheduled[jid] <= now:
                del self._scheduled[jid]
                if jid in self._jobs and self._jobs[jid].status == JobStatus.CREATED:
                    self.enqueue(jid)

        if not self._queue:
            return None
        job_id = self._queue.pop(0)
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.QUEUED:
            self._transition(job, JobStatus.PROCESSING)
            job.started_at = datetime.now(timezone.utc).isoformat()
            self._processing = job_id
            return job
        return None

    def update_progress(self, job_id: str, progress: float, status: Optional[JobStatus] = None):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.progress = min(100, max(0, progress))
        if status and status in VALID_TRANSITIONS.get(job.status, []):
            self._transition(job, status)

    def complete_job(self, job_id: str, asset_id: Optional[str] = None):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.result_asset_id = asset_id
        job.progress = 100
        self._transition(job, JobStatus.COMPLETED)
        job.completed_at = datetime.now(timezone.utc).isoformat()
        if self._processing == job_id:
            self._processing = None

    def fail_job(self, job_id: str, error: str):
        job = self._jobs.get(job_id)
        if not job:
            return
        job.error_message = error
        self._transition(job, JobStatus.FAILED)
        job.completed_at = datetime.now(timezone.utc).isoformat()
        if self._processing == job_id:
            self._processing = None

    def retry_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.FAILED:
            return False
        if job.retry_count >= job.max_retries:
            self._send_to_dead_letter(job_id)
            return False
        job.retry_count += 1
        job.error_message = None
        job.progress = 0
        self._transition(job, JobStatus.QUEUED)
        self._queue.append(job_id)
        self._sort_queue()
        return True

    def cancel_job(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED):
            return False
        self._transition(job, JobStatus.CANCELLED)
        job.completed_at = datetime.now(timezone.utc).isoformat()
        if job_id in self._queue:
            self._queue.remove(job_id)
        if self._processing == job_id:
            self._processing = None
        self._scheduled.pop(job_id, None)
        return True

    def _send_to_dead_letter(self, job_id: str):
        self._dead_letter.append(job_id)
        if len(self._dead_letter) > self._dead_letter_max:
            self._dead_letter.pop(0)

    def get_dead_letter(self) -> List[Job]:
        return [self._jobs[jid] for jid in self._dead_letter if jid in self._jobs]

    def replay_dead_letter(self, job_id: str) -> bool:
        if job_id not in self._dead_letter:
            return False
        self._dead_letter.remove(job_id)
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.retry_count = 0
        job.error_message = None
        job.progress = 0
        self._transition(job, JobStatus.QUEUED)
        self._queue.append(job_id)
        self._sort_queue()
        return True

    def _sort_queue(self):
        self._queue.sort(
            key=lambda jid: PRIORITY_ORDER.get(
                self._job_priorities.get(jid, JobPriority.NORMAL), 2
            )
        )

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_user_jobs(self, user_id: int) -> List[Job]:
        return [j for j in self._jobs.values() if j.user_id == user_id]

    def get_queue_length(self) -> int:
        return len(self._queue)

    def get_priority(self, job_id: str) -> JobPriority:
        return self._job_priorities.get(job_id, JobPriority.NORMAL)

    def get_stats(self) -> dict:
        statuses = {}
        for job in self._jobs.values():
            s = job.status.value
            statuses[s] = statuses.get(s, 0) + 1
        priorities = {}
        for p in self._job_priorities.values():
            priorities[p.value] = priorities.get(p.value, 0) + 1
        return {
            "total": len(self._jobs),
            "queued": len(self._queue),
            "processing": 1 if self._processing else 0,
            "dead_letter": len(self._dead_letter),
            "scheduled": len(self._scheduled),
            "by_status": statuses,
            "by_priority": priorities,
        }

    def _transition(self, job: Job, new_status: JobStatus):
        valid = VALID_TRANSITIONS.get(job.status, [])
        if new_status not in valid:
            raise ValueError(
                f"Invalid transition: {job.status.value} → {new_status.value}. "
                f"Valid: {[s.value for s in valid]}"
            )
        job.status = new_status


# Global queue instance
job_queue = JobQueue()
