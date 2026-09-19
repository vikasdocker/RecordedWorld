"""
GPU Profiling Service

Receives and tracks GPU/rendering performance metrics from clients.
"""
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from collections import deque


@dataclass
class FrameMetrics:
    """Metrics for a single frame or batch of frames."""
    timestamp: float
    frame_time_ms: float  # total frame time in milliseconds
    fps: float
    draw_calls: int = 0
    triangles: int = 0
    texture_memory_mb: float = 0.0
    gpu_utilization: float = 0.0  # 0-100%
    player_id: Optional[str] = None


@dataclass
class GPUSnapshot:
    """Aggregated GPU metrics over a time window."""
    avg_fps: float = 0.0
    min_fps: float = 0.0
    max_fps: float = 0.0
    avg_frame_time_ms: float = 0.0
    p95_frame_time_ms: float = 0.0
    avg_draw_calls: float = 0.0
    avg_triangles: float = 0.0
    avg_texture_memory_mb: float = 0.0
    sample_count: int = 0


class GPUProfiler:
    """
    Collects and analyzes GPU performance metrics from connected clients.

    Clients report frame metrics via WebSocket or REST API.
    This service aggregates and provides analytics.
    """

    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self._metrics: deque[FrameMetrics] = deque(maxlen=max_history)
        self._per_player: Dict[str, deque[FrameMetrics]] = {}
        self._alert_thresholds = {
            "min_fps": 30.0,
            "max_frame_time_ms": 33.33,  # 30fps threshold
            "max_draw_calls": 2000,
            "max_triangles": 1000000,
        }

    def record_frame(self, metrics: FrameMetrics):
        """Record frame metrics from a client."""
        self._metrics.append(metrics)

        if metrics.player_id:
            if metrics.player_id not in self._per_player:
                self._per_player[metrics.player_id] = deque(maxlen=1000)
            self._per_player[metrics.player_id].append(metrics)

    def get_snapshot(self, window_seconds: float = 60.0) -> GPUSnapshot:
        """Get aggregated GPU metrics over a time window."""
        cutoff = time.time() - window_seconds
        recent = [m for m in self._metrics if m.timestamp >= cutoff]

        if not recent:
            return GPUSnapshot()

        fps_values = [m.fps for m in recent]
        frame_times = [m.frame_time_ms for m in recent]
        draw_calls = [m.draw_calls for m in recent if m.draw_calls > 0]
        triangles = [m.triangles for m in recent if m.triangles > 0]
        textures = [m.texture_memory_mb for m in recent if m.texture_memory_mb > 0]

        sorted_ft = sorted(frame_times)
        p95_idx = int(len(sorted_ft) * 0.95)

        return GPUSnapshot(
            avg_fps=round(sum(fps_values) / len(fps_values), 1),
            min_fps=round(min(fps_values), 1),
            max_fps=round(max(fps_values), 1),
            avg_frame_time_ms=round(sum(frame_times) / len(frame_times), 2),
            p95_frame_time_ms=round(sorted_ft[p95_idx] if p95_idx < len(sorted_ft) else sorted_ft[-1], 2),
            avg_draw_calls=round(sum(draw_calls) / len(draw_calls)) if draw_calls else 0,
            avg_triangles=round(sum(triangles) / len(triangles)) if triangles else 0,
            avg_texture_memory_mb=round(sum(textures) / len(textures), 1) if textures else 0,
            sample_count=len(recent),
        )

    def get_player_metrics(self, player_id: str, limit: int = 100) -> List[FrameMetrics]:
        """Get recent metrics for a specific player."""
        if player_id not in self._per_player:
            return []
        return list(self._per_player[player_id])[-limit:]

    def check_alerts(self) -> List[Dict]:
        """Check for performance alerts based on thresholds."""
        alerts = []
        snapshot = self.get_snapshot(window_seconds=30.0)

        if snapshot.sample_count == 0:
            return alerts

        if snapshot.avg_fps < self._alert_thresholds["min_fps"]:
            alerts.append({
                "type": "low_fps",
                "severity": "warning",
                "message": f"Average FPS {snapshot.avg_fps} below threshold {self._alert_thresholds['min_fps']}",
                "value": snapshot.avg_fps,
            })

        if snapshot.p95_frame_time_ms > self._alert_thresholds["max_frame_time_ms"]:
            alerts.append({
                "type": "high_frame_time",
                "severity": "warning",
                "message": f"P95 frame time {snapshot.p95_frame_time_ms}ms exceeds {self._alert_thresholds['max_frame_time_ms']}ms",
                "value": snapshot.p95_frame_time_ms,
            })

        if snapshot.avg_draw_calls > self._alert_thresholds["max_draw_calls"]:
            alerts.append({
                "type": "high_draw_calls",
                "severity": "info",
                "message": f"Average draw calls {snapshot.avg_draw_calls} exceeds {self._alert_thresholds['max_draw_calls']}",
                "value": snapshot.avg_draw_calls,
            })

        return alerts

    def get_optimization_suggestions(self) -> List[str]:
        """Suggest optimizations based on current metrics."""
        suggestions = []
        snapshot = self.get_snapshot(window_seconds=60.0)

        if snapshot.sample_count == 0:
            return ["No metrics data available"]

        if snapshot.avg_fps < 30:
            suggestions.append("Consider reducing shadow quality or disabling post-processing")
            suggestions.append("Enable LOD system to reduce triangle count at distance")

        if snapshot.avg_draw_calls > 1000:
            suggestions.append("Enable GPU instancing for repeated objects")
            suggestions.append("Merge static meshes where possible")

        if snapshot.avg_triangles > 500000:
            suggestions.append("Reduce mesh complexity or use more aggressive LOD")
            suggestions.append("Consider occlusion culling for distant objects")

        if snapshot.avg_texture_memory_mb > 256:
            suggestions.append("Use texture atlasing to reduce texture swaps")
            suggestions.append("Consider texture streaming for large worlds")

        if snapshot.p95_frame_time_ms > 20:
            suggestions.append("Profile frame spikes - possible GC or loading hitches")

        if not suggestions:
            suggestions.append("Performance looks good!")

        return suggestions


# Module-level singleton
gpu_profiler = GPUProfiler()
