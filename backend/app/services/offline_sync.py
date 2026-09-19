"""
Offline Capture Queue Sync Service

Manages capture queue synchronization when mobile device is offline.
Handles conflict resolution, retry logic, and progressive sync.
"""
import time
import hashlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum


class SyncState(Enum):
    PENDING = "pending"
    SYNCING = "syncing"
    SYNCED = "synced"
    CONFLICT = "conflict"
    FAILED = "failed"


class ConflictResolution(Enum):
    KEEP_LOCAL = "keep_local"
    KEEP_REMOTE = "keep_remote"
    MERGE = "merge"
    ASK_USER = "ask_user"


@dataclass
class OfflineCapture:
    """A capture queued while offline."""
    id: str
    user_id: int
    device_id: str
    filename: str
    file_size_bytes: int
    local_path: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    sync_state: SyncState = SyncState.PENDING
    created_at: float = field(default_factory=time.time)
    last_sync_attempt: float = 0.0
    sync_attempts: int = 0
    max_sync_attempts: int = 5
    remote_id: Optional[str] = None
    checksum: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        return time.time() - self.created_at > 86400 * 7  # 7 days

    @property
    def can_retry(self) -> bool:
        return self.sync_attempts < self.max_sync_attempts

    @property
    def file_size_mb(self) -> float:
        return self.file_size_bytes / (1024 * 1024)

    def compute_checksum(self, data: bytes) -> str:
        self.checksum = hashlib.sha256(data).hexdigest()
        return self.checksum


@dataclass
class SyncBatch:
    """A batch of captures to sync."""
    batch_id: str
    captures: List[OfflineCapture]
    created_at: float = field(default_factory=time.time)
    total_size_bytes: int = 0

    @property
    def capture_count(self) -> int:
        return len(self.captures)

    @property
    def synced_count(self) -> int:
        return sum(1 for c in self.captures if c.sync_state == SyncState.SYNCED)


class OfflineSyncManager:
    """Manages offline capture queue synchronization."""

    MAX_QUEUE_SIZE = 100
    MAX_BATCH_SIZE = 10

    def __init__(self):
        self.captures: Dict[str, OfflineCapture] = {}
        self.user_queues: Dict[int, Set[str]] = {}
        self.sync_batches: List[SyncBatch] = []

    def queue_capture(
        self,
        capture_id: str,
        user_id: int,
        device_id: str,
        filename: str,
        file_size_bytes: int,
        local_path: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[OfflineCapture]:
        user_queue = self.user_queues.get(user_id, set())
        if len(user_queue) >= self.MAX_QUEUE_SIZE:
            return None

        capture = OfflineCapture(
            id=capture_id,
            user_id=user_id,
            device_id=device_id,
            filename=filename,
            file_size_bytes=file_size_bytes,
            local_path=local_path,
            metadata=metadata or {},
        )

        self.captures[capture_id] = capture
        self.user_queues.setdefault(user_id, set()).add(capture_id)
        return capture

    def get_pending(self, user_id: int) -> List[OfflineCapture]:
        ids = self.user_queues.get(user_id, set())
        return [
            c for c in (self.captures.get(i) for i in ids)
            if c and c.sync_state == SyncState.PENDING and c.can_retry
        ]

    def create_sync_batch(self, user_id: int) -> Optional[SyncBatch]:
        pending = self.get_pending(user_id)
        if not pending:
            return None

        batch_captures = pending[:self.MAX_BATCH_SIZE]
        total_size = sum(c.file_size_bytes for c in batch_captures)

        batch = SyncBatch(
            batch_id=f"batch_{user_id}_{int(time.time())}",
            captures=batch_captures,
            total_size_bytes=total_size,
        )

        for capture in batch_captures:
            capture.sync_state = SyncState.SYNCING
            capture.last_sync_attempt = time.time()
            capture.sync_attempts += 1

        self.sync_batches.append(batch)
        return batch

    def complete_sync(
        self,
        batch_id: str,
        results: Dict[str, bool],
    ) -> int:
        batch = next((b for b in self.sync_batches if b.batch_id == batch_id), None)
        if not batch:
            return 0

        synced = 0
        for capture in batch.captures:
            success = results.get(capture.id, False)
            if success:
                capture.sync_state = SyncState.SYNCED
                synced += 1
            else:
                capture.sync_state = SyncState.FAILED if not capture.can_retry else SyncState.PENDING
                capture.error_message = "Sync failed"

        return synced

    def resolve_conflict(
        self,
        capture_id: str,
        resolution: ConflictResolution,
    ) -> bool:
        capture = self.captures.get(capture_id)
        if not capture or capture.sync_state != SyncState.CONFLICT:
            return False

        if resolution == ConflictResolution.KEEP_LOCAL:
            capture.sync_state = SyncState.PENDING
        elif resolution == ConflictResolution.KEEP_REMOTE:
            capture.sync_state = SyncState.SYNCED
        elif resolution == ConflictResolution.MERGE:
            capture.sync_state = SyncState.PENDING

        return True

    def get_queue_stats(self, user_id: int) -> Dict[str, Any]:
        ids = self.user_queues.get(user_id, set())
        captures = [self.captures[i] for i in ids if i in self.captures]

        states = {}
        for c in captures:
            states[c.sync_state.value] = states.get(c.sync_state.value, 0) + 1

        total_size = sum(c.file_size_bytes for c in captures)

        return {
            "total_queued": len(captures),
            "by_state": states,
            "total_size_mb": total_size / (1024 * 1024),
            "oldest_pending": min(
                (c.created_at for c in captures if c.sync_state == SyncState.PENDING),
                default=0,
            ),
        }

    def cleanup_expired(self) -> int:
        expired = [cid for cid, c in self.captures.items() if c.is_expired]
        for cid in expired:
            c = self.captures.pop(cid)
            if c.user_id in self.user_queues:
                self.user_queues[c.user_id].discard(cid)
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_captures": len(self.captures),
            "total_users": len(self.user_queues),
            "total_batches": len(self.sync_batches),
        }


# Module-level singleton
offline_sync_manager = OfflineSyncManager()
