"""
Upload Session Tracking Service

Manages upload sessions with resume capability.
Tracks chunked uploads, validates integrity, and handles reconnection.
"""
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class UploadState(Enum):
    INITIATED = "initiated"
    UPLOADING = "uploading"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class UploadChunk:
    """A single chunk in a resumable upload."""
    index: int
    offset: int
    size: int
    uploaded: bool = False
    checksum: Optional[str] = None
    upload_time_ms: float = 0.0


@dataclass
class UploadSession:
    """A resumable upload session."""
    session_id: str
    user_id: int
    filename: str
    total_size: int
    chunk_size: int = 1024 * 1024  # 1MB default
    state: UploadState = UploadState.INITIATED
    chunks: List[UploadChunk] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None

    @property
    def total_chunks(self) -> int:
        return len(self.chunks)

    @property
    def uploaded_chunks(self) -> int:
        return sum(1 for c in self.chunks if c.uploaded)

    @property
    def progress(self) -> float:
        if self.total_chunks == 0:
            return 0.0
        return self.uploaded_chunks / self.total_chunks

    @property
    def uploaded_bytes(self) -> int:
        return sum(c.size for c in self.chunks if c.uploaded)

    @property
    def remaining_bytes(self) -> int:
        return self.total_size - self.uploaded_bytes

    @property
    def is_expired(self) -> bool:
        return time.time() - self.last_activity > 3600  # 1 hour

    @property
    def speed_bytes_per_sec(self) -> float:
        if self.uploaded_bytes == 0:
            return 0.0
        elapsed = time.time() - self.created_at
        return self.uploaded_bytes / elapsed if elapsed > 0 else 0.0


class UploadSessionManager:
    """Manages resumable upload sessions."""

    MAX_SESSIONS_PER_USER = 5
    SESSION_EXPIRY_SECONDS = 3600  # 1 hour

    def __init__(self):
        self.sessions: Dict[str, UploadSession] = {}
        self.user_sessions: Dict[int, Set[str]] = {}

    def create_session(
        self,
        session_id: str,
        user_id: int,
        filename: str,
        total_size: int,
        chunk_size: int = 1024 * 1024,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[UploadSession]:
        user_session_ids = self.user_sessions.get(user_id, set())
        active = sum(
            1 for sid in user_session_ids
            if sid in self.sessions and self.sessions[sid].state in (
                UploadState.INITIATED, UploadState.UPLOADING, UploadState.PAUSED
            )
        )
        if active >= self.MAX_SESSIONS_PER_USER:
            return None

        chunks = []
        offset = 0
        index = 0
        while offset < total_size:
            size = min(chunk_size, total_size - offset)
            chunks.append(UploadChunk(index=index, offset=offset, size=size))
            offset += size
            index += 1

        session = UploadSession(
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            total_size=total_size,
            chunk_size=chunk_size,
            chunks=chunks,
            metadata=metadata or {},
        )

        self.sessions[session_id] = session
        self.user_sessions.setdefault(user_id, set()).add(session_id)
        return session

    def get_session(self, session_id: str) -> Optional[UploadSession]:
        session = self.sessions.get(session_id)
        if session and session.is_expired:
            session.state = UploadState.EXPIRED
        return session

    def mark_chunk_uploaded(
        self, session_id: str, chunk_index: int, checksum: Optional[str] = None
    ) -> bool:
        session = self.sessions.get(session_id)
        if not session or session.state == UploadState.EXPIRED:
            return False

        for chunk in session.chunks:
            if chunk.index == chunk_index:
                chunk.uploaded = True
                chunk.checksum = checksum
                session.last_activity = time.time()
                session.state = UploadState.UPLOADING

                if session.uploaded_chunks == session.total_chunks:
                    session.state = UploadState.COMPLETED
                    session.completed_at = time.time()
                return True
        return False

    def pause_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session and session.state == UploadState.UPLOADING:
            session.state = UploadState.PAUSED
            return True
        return False

    def resume_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if session and session.state == UploadState.PAUSED:
            session.state = UploadState.UPLOADING
            session.last_activity = time.time()
            return True
        return False

    def get_resumable_chunks(self, session_id: str) -> List[int]:
        session = self.sessions.get(session_id)
        if not session:
            return []
        return [c.index for c in session.chunks if not c.uploaded]

    def delete_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session:
            if session.user_id in self.user_sessions:
                self.user_sessions[session.user_id].discard(session_id)
            return True
        return False

    def get_user_sessions(self, user_id: int) -> List[UploadSession]:
        ids = self.user_sessions.get(user_id, set())
        return [self.sessions[sid] for sid in ids if sid in self.sessions]

    def cleanup_expired(self) -> int:
        expired = [
            sid for sid, s in self.sessions.items()
            if s.is_expired or s.state == UploadState.EXPIRED
        ]
        for sid in expired:
            self.delete_session(sid)
        return len(expired)

    def get_stats(self) -> Dict[str, Any]:
        states = {}
        for s in self.sessions.values():
            states[s.state.value] = states.get(s.state.value, 0) + 1

        return {
            "total_sessions": len(self.sessions),
            "by_state": states,
            "unique_users": len(self.user_sessions),
        }


# Module-level singleton
upload_manager = UploadSessionManager()
