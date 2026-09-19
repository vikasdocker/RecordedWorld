"""
Network-Aware Streaming Service

Adapts streaming behavior based on network conditions:
  - Bandwidth estimation
  - Latency monitoring
  - Quality adaptation
  - Retry logic
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum


class NetworkQuality(Enum):
    EXCELLENT = "excellent"  # > 10 Mbps, < 50ms
    GOOD = "good"  # 5-10 Mbps, < 100ms
    FAIR = "fair"  # 2-5 Mbps, < 200ms
    POOR = "poor"  # < 2 Mbps, > 200ms
    OFFLINE = "offline"


@dataclass
class NetworkMetrics:
    """Current network conditions."""
    bandwidth_mbps: float = 10.0
    latency_ms: float = 50.0
    packet_loss: float = 0.0
    quality: NetworkQuality = NetworkQuality.GOOD
    last_measured: float = field(default_factory=time.time)

    @property
    def is_stale(self) -> bool:
        return time.time() - self.last_measured > 5.0


@dataclass
class StreamRequest:
    """A network-aware stream request."""
    chunk_id: str
    priority: int
    size_bytes: int
    created_at: float = field(default_factory=time.time)
    attempts: int = 0
    max_attempts: int = 3
    timeout_ms: float = 5000.0

    @property
    def is_expired(self) -> bool:
        return self.attempts >= self.max_attempts

    @property
    def effective_timeout(self) -> float:
        """Timeout increases with each retry attempt."""
        return self.timeout_ms * (1 + self.attempts * 0.5)


class NetworkAwareStreamer:
    """Adapts streaming based on network conditions."""

    def __init__(self):
        self.metrics = NetworkMetrics()
        self.pending_requests: List[StreamRequest] = []
        self.completed_requests: List[str] = []
        self.failed_requests: List[str] = []
        self.bandwidth_history: List[float] = []
        self.max_history = 100

    def update_metrics(
        self,
        bandwidth_mbps: Optional[float] = None,
        latency_ms: Optional[float] = None,
        packet_loss: Optional[float] = None,
    ):
        if bandwidth_mbps is not None:
            self.metrics.bandwidth_mbps = bandwidth_mbps
            self.bandwidth_history.append(bandwidth_mbps)
            if len(self.bandwidth_history) > self.max_history:
                self.bandwidth_history.pop(0)

        if latency_ms is not None:
            self.metrics.latency_ms = latency_ms

        if packet_loss is not None:
            self.metrics.packet_loss = packet_loss

        self.metrics.quality = self._assess_quality()
        self.metrics.last_measured = time.time()

    def get_adaptive_quality(self) -> Dict[str, Any]:
        """Get quality settings adapted to current network."""
        quality = self.metrics.quality

        settings = {
            NetworkQuality.EXCELLENT: {
                "max_concurrent": 8,
                "prefetch_distance": 3.0,
                "texture_quality": "ultra",
                "mesh_quality": "high",
            },
            NetworkQuality.GOOD: {
                "max_concurrent": 4,
                "prefetch_distance": 2.0,
                "texture_quality": "high",
                "mesh_quality": "medium",
            },
            NetworkQuality.FAIR: {
                "max_concurrent": 2,
                "prefetch_distance": 1.0,
                "texture_quality": "medium",
                "mesh_quality": "low",
            },
            NetworkQuality.POOR: {
                "max_concurrent": 1,
                "prefetch_distance": 0.5,
                "texture_quality": "low",
                "mesh_quality": "minimal",
            },
            NetworkQuality.OFFLINE: {
                "max_concurrent": 0,
                "prefetch_distance": 0.0,
                "texture_quality": "minimal",
                "mesh_quality": "minimal",
            },
        }

        return settings.get(quality, settings[NetworkQuality.GOOD])

    def estimate_download_time(self, size_bytes: int) -> float:
        """Estimate download time in seconds."""
        if self.metrics.bandwidth_mbps <= 0:
            return float("inf")
        bandwidth_bytes = self.metrics.bandwidth_mbps * 1024 * 1024
        return size_bytes / bandwidth_bytes

    def can_load_now(self, size_bytes: int, max_time_ms: float = 5000) -> bool:
        """Check if we can load within time budget."""
        est = self.estimate_download_time(size_bytes)
        return est * 1000 <= max_time_ms

    def prioritize_requests(self) -> List[StreamRequest]:
        """Sort requests by priority and feasibility."""
        feasible = []
        infeasible = []

        for req in self.pending_requests:
            if req.is_expired:
                self.failed_requests.append(req.chunk_id)
                continue

            if self.can_load_now(req.size_bytes):
                feasible.append(req)
            else:
                infeasible.append(req)

        feasible.sort(key=lambda r: (-r.priority, r.created_at))
        return feasible + infeasible

    def submit_request(self, chunk_id: str, priority: int, size_bytes: int) -> StreamRequest:
        req = StreamRequest(
            chunk_id=chunk_id,
            priority=priority,
            size_bytes=size_bytes,
        )
        self.pending_requests.append(req)
        return req

    def complete_request(self, chunk_id: str):
        self.pending_requests = [r for r in self.pending_requests if r.chunk_id != chunk_id]
        self.completed_requests.append(chunk_id)

    def retry_request(self, chunk_id: str) -> Optional[StreamRequest]:
        for req in self.pending_requests:
            if req.chunk_id == chunk_id:
                req.attempts += 1
                if req.is_expired:
                    self.failed_requests.append(chunk_id)
                    return None
                return req
        return None

    def _assess_quality(self) -> NetworkQuality:
        bw = self.metrics.bandwidth_mbps
        lat = self.metrics.latency_ms
        loss = self.metrics.packet_loss

        if bw == 0:
            return NetworkQuality.OFFLINE
        if loss > 0.1:
            return NetworkQuality.POOR
        if bw < 2 or lat > 200:
            return NetworkQuality.POOR
        if bw < 5 or lat > 100:
            return NetworkQuality.FAIR
        if bw < 10 or lat > 50:
            return NetworkQuality.GOOD
        return NetworkQuality.EXCELLENT

    def get_stats(self) -> Dict[str, Any]:
        avg_bw = (sum(self.bandwidth_history) / len(self.bandwidth_history)
                  if self.bandwidth_history else 0)
        return {
            "quality": self.metrics.quality.value,
            "bandwidth_mbps": self.metrics.bandwidth_mbps,
            "latency_ms": self.metrics.latency_ms,
            "avg_bandwidth_mbps": avg_bw,
            "pending_requests": len(self.pending_requests),
            "completed": len(self.completed_requests),
            "failed": len(self.failed_requests),
        }


# Module-level singleton
network_streamer = NetworkAwareStreamer()
