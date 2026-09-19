"""
Audit Logging Service

Tracks security-relevant actions for compliance and forensics.
"""

import time
import json
import threading
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: str
    event_type: str
    user_id: Optional[int]
    ip_address: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    success: bool = True


class AuditLogger:
    """In-memory audit logger (replace with persistent storage in production)."""

    def __init__(self, max_entries: int = 10000):
        self._entries: deque = deque(maxlen=max_entries)
        self._lock = threading.Lock()

    def log(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        details: Optional[Dict] = None,
        success: bool = True,
    ):
        """Log an audit event."""
        entry = AuditEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {},
            success=success,
        )
        with self._lock:
            self._entries.append(entry)

    def query(
        self,
        event_type: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries."""
        with self._lock:
            results = list(self._entries)
            if event_type:
                results = [e for e in results if e.event_type == event_type]
            if user_id:
                results = [e for e in results if e.user_id == user_id]
            return results[-limit:]

    def get_stats(self) -> Dict:
        """Get audit log statistics."""
        with self._lock:
            event_counts = {}
            for entry in self._entries:
                event_counts[entry.event_type] = event_counts.get(entry.event_type, 0) + 1
            return {
                "total_entries": len(self._entries),
                "event_types": event_counts,
            }


# Pre-defined event types
class AuditEvents:
    AUTH_LOGIN = "auth.login"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REGISTER = "auth.register"
    AUTH_PASSWORD_CHANGE = "auth.password_change"

    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"

    LOCATION_CREATE = "location.create"
    LOCATION_UPDATE = "location.update"
    LOCATION_DELETE = "location.delete"
    LOCATION_MODERATE = "location.moderate"

    FRIEND_REQUEST = "friend.request"
    FRIEND_ACCEPT = "friend.accept"
    FRIEND_REJECT = "friend.reject"
    FRIEND_REMOVE = "friend.remove"
    BLOCK_USER = "user.block"

    REPORT_SUBMIT = "report.submit"
    REPORT_RESOLVE = "report.resolve"

    ASSET_ACCESS = "asset.access"
    ASSET_UPLOAD = "asset.upload"


# Global logger
audit_logger = AuditLogger()
