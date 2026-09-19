"""
Observability Service

Distributed tracing, error tracking, and operational metrics.
"""

import time
import uuid
import threading
import traceback
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
from enum import Enum


class TraceStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"


@dataclass
class Span:
    """A single trace span."""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation: str
    service: str
    start_time: float
    end_time: Optional[float] = None
    status: TraceStatus = TraceStatus.OK
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0.0

    def finish(self, status: TraceStatus = TraceStatus.OK):
        self.end_time = time.time()
        self.status = status

    def add_event(self, name: str, attributes: Optional[Dict] = None):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {},
        })


class Tracer:
    """Distributed tracing."""

    def __init__(self, history_size: int = 5000):
        self._spans: deque = deque(maxlen=history_size)
        self._lock = threading.Lock()

    def start_span(
        self,
        operation: str,
        service: str = "backend",
        parent_span_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> Span:
        """Start a new span."""
        if not trace_id:
            trace_id = uuid.uuid4().hex[:16]
        span = Span(
            trace_id=trace_id,
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=parent_span_id,
            operation=operation,
            service=service,
            start_time=time.time(),
        )
        return span

    def finish_span(self, span: Span):
        """Finish and record a span."""
        span.finish()
        with self._lock:
            self._spans.append(span)

    def get_trace(self, trace_id: str) -> List[Span]:
        """Get all spans for a trace."""
        with self._lock:
            return [s for s in self._spans if s.trace_id == trace_id]

    def get_recent_spans(self, limit: int = 100) -> List[Span]:
        """Get recent spans."""
        with self._lock:
            return list(self._spans)[-limit:]

    def get_slow_queries(self, threshold_ms: float = 100) -> List[Span]:
        """Get spans slower than threshold."""
        with self._lock:
            return [s for s in self._spans if s.duration_ms > threshold_ms]

    def get_error_spans(self) -> List[Span]:
        """Get spans with errors."""
        with self._lock:
            return [s for s in self._spans if s.status == TraceStatus.ERROR]

    def get_stats(self) -> Dict:
        """Get tracing statistics."""
        with self._lock:
            total = len(self._spans)
            errors = sum(1 for s in self._spans if s.status == TraceStatus.ERROR)
            durations = [s.duration_ms for s in self._spans if s.duration_ms > 0]
            return {
                "total_spans": total,
                "error_spans": errors,
                "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                "max_duration_ms": max(durations) if durations else 0,
            }


class ErrorTracker:
    """Track and report errors."""

    def __init__(self, max_errors: int = 1000):
        self._errors: deque = deque(maxlen=max_errors)
        self._lock = threading.Lock()

    def capture_exception(
        self,
        exception: Exception,
        context: Optional[Dict] = None,
        service: str = "backend",
    ) -> str:
        """Capture an exception. Returns error ID."""
        error_id = uuid.uuid4().hex[:12]
        error = {
            "id": error_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": type(exception).__name__,
            "message": str(exception),
            "traceback": traceback.format_exc(),
            "service": service,
            "context": context or {},
        }
        with self._lock:
            self._errors.append(error)
        return error_id

    def capture_message(
        self,
        message: str,
        level: str = "error",
        context: Optional[Dict] = None,
        service: str = "backend",
    ) -> str:
        """Capture a message. Returns error ID."""
        error_id = uuid.uuid4().hex[:12]
        error = {
            "id": error_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "message",
            "message": message,
            "level": level,
            "service": service,
            "context": context or {},
        }
        with self._lock:
            self._errors.append(error)
        return error_id

    def get_errors(self, limit: int = 100) -> List[Dict]:
        """Get recent errors."""
        with self._lock:
            return list(self._errors)[-limit:]

    def get_error_count(self) -> int:
        """Get total error count."""
        with self._lock:
            return len(self._errors)

    def get_stats(self) -> Dict:
        """Get error statistics."""
        with self._lock:
            by_type = {}
            for e in self._errors:
                t = e.get("type", "unknown")
                by_type[t] = by_type.get(t, 0) + 1
            return {
                "total_errors": len(self._errors),
                "by_type": by_type,
            }


# Global instances
tracer = Tracer()
error_tracker = ErrorTracker()
