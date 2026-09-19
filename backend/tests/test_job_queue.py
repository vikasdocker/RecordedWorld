"""Tests for Phase 23: Reconstruction Job System."""

import time
import pytest
from app.services.job_queue import (
    JobQueue, Job, JobStatus, JobPriority, job_queue, VALID_TRANSITIONS
)


class TestJobCreation:
    def test_create_job(self):
        """Can create a job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        assert job.job_id.startswith("job_")
        assert job.user_id == 1
        assert job.status == JobStatus.CREATED

    def test_create_job_with_capture(self):
        """Can create a job with capture_id."""
        q = JobQueue()
        job = q.create_job(user_id=1, capture_id=42)
        assert job.capture_id == 42

    def test_job_to_dict(self):
        """Job serialization works."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        d = job.to_dict()
        assert "job_id" in d
        assert d["status"] == "created"


class TestJobQueue:
    def test_enqueue(self):
        """Can enqueue a job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        assert job.status == JobStatus.QUEUED

    def test_dequeue(self):
        """Can dequeue a job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        dequeued = q.dequeue()
        assert dequeued is not None
        assert dequeued.status == JobStatus.PROCESSING
        assert dequeued.started_at is not None

    def test_dequeue_empty(self):
        """Dequeue returns None when empty."""
        q = JobQueue()
        assert q.dequeue() is None

    def test_queue_order(self):
        """Jobs are dequeued in FIFO order."""
        q = JobQueue()
        j1 = q.create_job(user_id=1)
        j2 = q.create_job(user_id=2)
        q.enqueue(j1.job_id)
        q.enqueue(j2.job_id)
        assert q.dequeue().job_id == j1.job_id
        assert q.dequeue().job_id == j2.job_id

    def test_queue_length(self):
        """Queue length is correct."""
        q = JobQueue()
        q.create_job(user_id=1)
        assert q.get_queue_length() == 0  # not enqueued yet
        j = q.create_job(user_id=2)
        q.enqueue(j.job_id)
        assert q.get_queue_length() == 1


class TestProgress:
    def test_update_progress(self):
        """Can update job progress."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.update_progress(job.job_id, 50.0)
        assert job.progress == 50.0

    def test_progress_clamped(self):
        """Progress is clamped to 0-100."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.update_progress(job.job_id, 150)
        assert job.progress == 100
        q.update_progress(job.job_id, -10)
        assert job.progress == 0


class TestCompletion:
    def test_complete_job(self):
        """Can complete a job (goes through full pipeline)."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()
        q.update_progress(job.job_id, 100, JobStatus.RECONSTRUCTING)
        q.update_progress(job.job_id, 100, JobStatus.ALIGNING)
        q.update_progress(job.job_id, 100, JobStatus.OPTIMIZING)
        q.update_progress(job.job_id, 100, JobStatus.VALIDATING)
        q.complete_job(job.job_id, asset_id="asset_abc")
        assert job.status == JobStatus.COMPLETED
        assert job.result_asset_id == "asset_abc"
        assert job.progress == 100
        assert job.completed_at is not None


class TestFailure:
    def test_fail_job(self):
        """Can fail a job (at processing stage)."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error: OOM")
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Error: OOM"


class TestRetry:
    def test_retry_failed_job(self):
        """Can retry a failed job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error")
        assert q.retry_job(job.job_id) is True
        assert job.status == JobStatus.QUEUED
        assert job.retry_count == 1

    def test_retry_max_limit(self):
        """Cannot retry beyond max_retries."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        job.max_retries = 2
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error")
        q.retry_job(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error")
        q.retry_job(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error")
        assert q.retry_job(job.job_id) is False

    def test_retry_non_failed(self):
        """Cannot retry non-failed job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        assert q.retry_job(job.job_id) is False


class TestCancel:
    def test_cancel_queued_job(self):
        """Can cancel a queued job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        assert q.cancel_job(job.job_id) is True
        assert job.status == JobStatus.CANCELLED

    def test_cancel_completed(self):
        """Cannot cancel completed job."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.dequeue()
        q.update_progress(job.job_id, 100, JobStatus.RECONSTRUCTING)
        q.update_progress(job.job_id, 100, JobStatus.ALIGNING)
        q.update_progress(job.job_id, 100, JobStatus.OPTIMIZING)
        q.update_progress(job.job_id, 100, JobStatus.VALIDATING)
        q.complete_job(job.job_id)
        assert q.cancel_job(job.job_id) is False

    def test_cancel_removes_from_queue(self):
        """Cancel removes job from queue."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.enqueue(job.job_id)
        q.cancel_job(job.job_id)
        assert q.get_queue_length() == 0


class TestQueries:
    def test_get_user_jobs(self):
        """Can get user's jobs."""
        q = JobQueue()
        q.create_job(user_id=1)
        q.create_job(user_id=1)
        q.create_job(user_id=2)
        assert len(q.get_user_jobs(1)) == 2
        assert len(q.get_user_jobs(2)) == 1

    def test_get_stats(self):
        """Stats are correct."""
        q = JobQueue()
        j1 = q.create_job(user_id=1)
        j2 = q.create_job(user_id=2)
        q.enqueue(j1.job_id)
        stats = q.get_stats()
        assert stats["total"] == 2
        assert stats["queued"] == 1


class TestTransitions:
    def test_valid_transitions(self):
        """All valid transitions are defined."""
        assert len(VALID_TRANSITIONS) == len(JobStatus)
        for status in JobStatus:
            assert status in VALID_TRANSITIONS

    def test_invalid_transition(self):
        """Invalid transition raises error."""
        q = JobQueue()
        job = q.create_job(user_id=1)
        with pytest.raises(ValueError):
            q._transition(job, JobStatus.COMPLETED)  # CREATED -> COMPLETED is invalid


class TestGlobalQueue:
    def test_global_queue_exists(self):
        """Global queue instance exists."""
        assert job_queue is not None
        assert isinstance(job_queue, JobQueue)


class TestPriority:
    def test_create_with_priority(self):
        q = JobQueue()
        job = q.create_job(user_id=1, priority=JobPriority.HIGH)
        assert q.get_priority(job.job_id) == JobPriority.HIGH

    def test_priority_ordering(self):
        q = JobQueue()
        low = q.create_job(user_id=1, priority=JobPriority.LOW)
        critical = q.create_job(user_id=2, priority=JobPriority.CRITICAL)
        normal = q.create_job(user_id=3, priority=JobPriority.NORMAL)
        high = q.create_job(user_id=4, priority=JobPriority.HIGH)

        q.enqueue(low.job_id)
        q.enqueue(critical.job_id)
        q.enqueue(normal.job_id)
        q.enqueue(high.job_id)

        assert q.dequeue().job_id == critical.job_id
        assert q.dequeue().job_id == high.job_id
        assert q.dequeue().job_id == normal.job_id
        assert q.dequeue().job_id == low.job_id

    def test_default_priority(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        assert q.get_priority(job.job_id) == JobPriority.NORMAL


class TestDeadLetter:
    def test_dead_letter_on_max_retries(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        job.max_retries = 1
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error 1")
        q.retry_job(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error 2")
        result = q.retry_job(job.job_id)
        assert result is False
        assert len(q.get_dead_letter()) == 1

    def test_replay_dead_letter(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        job.max_retries = 0
        q.enqueue(job.job_id)
        q.dequeue()
        q.fail_job(job.job_id, "Error")
        q.retry_job(job.job_id)
        assert len(q.get_dead_letter()) == 1
        assert q.replay_dead_letter(job.job_id)
        assert len(q.get_dead_letter()) == 0
        assert job.status == JobStatus.QUEUED

    def test_replay_nonexistent(self):
        q = JobQueue()
        assert q.replay_dead_letter("nonexistent") is False

    def test_stats_include_dead_letter(self):
        q = JobQueue()
        stats = q.get_stats()
        assert "dead_letter" in stats


class TestSchedule:
    def test_schedule_job(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.schedule(job.job_id, time.time() - 1)  # past time
        dequeued = q.dequeue()
        assert dequeued is not None

    def test_stats_include_scheduled(self):
        q = JobQueue()
        stats = q.get_stats()
        assert "scheduled" in stats

    def test_cancel_removes_schedule(self):
        q = JobQueue()
        job = q.create_job(user_id=1)
        q.schedule(job.job_id, time.time() + 3600)
        q.cancel_job(job.job_id)
        assert job.job_id not in q._scheduled
