"""
Performance Monitoring Service

Tracks CPU, memory, network, and server metrics.
"""

import time
import threading
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
import statistics


@dataclass
class MetricPoint:
    """A single metric measurement."""
    timestamp: str
    value: float
    unit: str = ""


@dataclass
class PerformanceSnapshot:
    """A snapshot of all performance metrics."""
    timestamp: str
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    active_connections: int = 0
    requests_per_second: float = 0.0
    avg_response_time_ms: float = 0.0
    ws_messages_per_second: float = 0.0
    db_query_time_ms: float = 0.0


class PerformanceMonitor:
    """Tracks and reports performance metrics."""

    def __init__(self, history_size: int = 1000):
        self._lock = threading.Lock()
        self._history_size = history_size

        # Metrics history (circular buffers)
        self._cpu_history: deque = deque(maxlen=history_size)
        self._memory_history: deque = deque(maxlen=history_size)
        self._response_times: deque = deque(maxlen=history_size)
        self._ws_messages: deque = deque(maxlen=history_size)
        self._db_query_times: deque = deque(maxlen=history_size)

        # Counters
        self._total_requests = 0
        self._total_ws_messages = 0
        self._active_connections = 0

        # Timing
        self._start_time = time.time()
        self._last_request_time = self._start_time

    def record_cpu(self, percent: float):
        """Record CPU usage."""
        with self._lock:
            self._cpu_history.append(MetricPoint(
                timestamp=datetime.now(timezone.utc).isoformat(),
                value=percent,
                unit="%",
            ))

    def record_memory(self, mb: float, percent: float = 0.0):
        """Record memory usage."""
        with self._lock:
            self._memory_history.append(MetricPoint(
                timestamp=datetime.now(timezone.utc).isoformat(),
                value=mb,
                unit="MB",
            ))

    def record_response_time(self, ms: float):
        """Record API response time."""
        with self._lock:
            self._response_times.append(ms)
            self._total_requests += 1
            self._last_request_time = time.time()

    def record_ws_message(self):
        """Record a WebSocket message."""
        with self._lock:
            self._ws_messages.append(time.time())
            self._total_ws_messages += 1

    def record_db_query(self, ms: float):
        """Record database query time."""
        with self._lock:
            self._db_query_times.append(ms)

    def set_active_connections(self, count: int):
        """Set number of active WebSocket connections."""
        with self._lock:
            self._active_connections = count

    def get_snapshot(self) -> PerformanceSnapshot:
        """Get current performance snapshot."""
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()

            # CPU average
            cpu_values = [p.value for p in self._cpu_history]
            cpu_avg = statistics.mean(cpu_values) if cpu_values else 0.0

            # Memory
            mem_values = [p.value for p in self._memory_history]
            mem_avg = statistics.mean(mem_values) if mem_values else 0.0

            # Response times
            rt_avg = statistics.mean(self._response_times) if self._response_times else 0.0

            # Requests per second (last 10 seconds)
            recent_requests = [t for t in self._ws_messages if t > time.time() - 10]
            rps = len(recent_requests) / 10.0

            # DB query time
            db_avg = statistics.mean(self._db_query_times) if self._db_query_times else 0.0

            return PerformanceSnapshot(
                timestamp=now,
                cpu_percent=cpu_avg,
                memory_mb=mem_avg,
                active_connections=self._active_connections,
                requests_per_second=rps,
                avg_response_time_ms=rt_avg,
                db_query_time_ms=db_avg,
            )

    def get_stats(self) -> Dict:
        """Get performance statistics."""
        with self._lock:
            uptime = time.time() - self._start_time
            return {
                "uptime_seconds": uptime,
                "total_requests": self._total_requests,
                "total_ws_messages": self._total_ws_messages,
                "active_connections": self._active_connections,
                "avg_response_time_ms": statistics.mean(self._response_times) if self._response_times else 0,
                "p95_response_time_ms": self._percentile(self._response_times, 95),
                "p99_response_time_ms": self._percentile(self._response_times, 99),
                "avg_cpu_percent": statistics.mean([p.value for p in self._cpu_history]) if self._cpu_history else 0,
                "avg_memory_mb": statistics.mean([p.value for p in self._memory_history]) if self._memory_history else 0,
                "avg_db_query_ms": statistics.mean(self._db_query_times) if self._db_query_times else 0,
            }

    def check_thresholds(self) -> List[str]:
        """Check if any metrics exceed thresholds."""
        warnings = []
        stats = self.get_stats()

        if stats["avg_cpu_percent"] > 80:
            warnings.append(f"High CPU: {stats['avg_cpu_percent']:.1f}%")
        if stats["avg_memory_mb"] > 500:
            warnings.append(f"High memory: {stats['avg_memory_mb']:.1f}MB")
        if stats["avg_response_time_ms"] > 100:
            warnings.append(f"Slow responses: {stats['avg_response_time_ms']:.1f}ms")
        if stats["active_connections"] > 1000:
            warnings.append(f"Many connections: {stats['active_connections']}")

        return warnings

    def _percentile(self, data: deque, percentile: float) -> float:
        """Calculate percentile."""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# Global monitor instance
performance_monitor = PerformanceMonitor()
