"""Health check and monitoring API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from app.services.monitoring import metrics, health_checker, alert_manager
from app.services.gpu_profiler import gpu_profiler, FrameMetrics

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class AlertCreate(BaseModel):
    level: str
    message: str
    source: str = "system"


@router.get("/health")
async def health():
    """Quick health check."""
    return {"status": "healthy"}


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health check of all services."""
    checks = await health_checker.check_all()
    return {
        "overall": health_checker.get_overall_status(),
        "services": {
            name: {
                "status": s.status,
                "latency_ms": s.latency_ms,
                "last_check": s.last_check,
                "error": s.error,
            }
            for name, s in checks.items()
        },
    }


@router.get("/metrics")
def get_metrics():
    """Get all collected metrics."""
    return metrics.export()


@router.get("/metrics/{name}")
def get_metric(name: str):
    """Get a specific metric."""
    counter = metrics.get_counter(name)
    gauge = metrics.get_gauge(name)
    histogram = metrics.get_histogram_stats(name)
    return {
        "name": name,
        "counter": counter,
        "gauge": gauge,
        "histogram": histogram,
    }


@router.get("/alerts")
def list_alerts():
    """List all alerts."""
    return {"alerts": alert_manager.alerts}


@router.get("/alerts/active")
def active_alerts():
    """List active (unacknowledged) alerts."""
    return {"alerts": alert_manager.get_active_alerts()}


@router.post("/alerts")
def create_alert(alert: AlertCreate):
    """Create a new alert."""
    alert_manager.add_alert(alert.level, alert.message, alert.source)
    return {"status": "created"}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int):
    """Acknowledge an alert."""
    alert_manager.acknowledge(alert_id)
    return {"status": "acknowledged"}


@router.get("/dashboard")
async def dashboard():
    """Get monitoring dashboard data."""
    checks = await health_checker.check_all()
    return {
        "health": {
            "overall": health_checker.get_overall_status(),
            "services": {n: s.status for n, s in checks.items()},
        },
        "metrics": metrics.export(),
        "alerts": {
            "active_count": len(alert_manager.get_active_alerts()),
            "total_count": len(alert_manager.alerts),
        },
    }


# =============================================================================
# GPU Profiling
# =============================================================================

class FrameMetricsRequest(BaseModel):
    frame_time_ms: float
    fps: float
    draw_calls: int = 0
    triangles: int = 0
    texture_memory_mb: float = 0.0
    gpu_utilization: float = 0.0
    player_id: Optional[str] = None


@router.post("/gpu/report")
def report_frame_metrics(req: FrameMetricsRequest):
    """Report frame metrics from a client."""
    import time
    metrics_record = FrameMetrics(
        timestamp=time.time(),
        frame_time_ms=req.frame_time_ms,
        fps=req.fps,
        draw_calls=req.draw_calls,
        triangles=req.triangles,
        texture_memory_mb=req.texture_memory_mb,
        gpu_utilization=req.gpu_utilization,
        player_id=req.player_id,
    )
    gpu_profiler.record_frame(metrics_record)
    return {"status": "recorded"}


@router.get("/gpu/snapshot")
def gpu_snapshot(window_seconds: float = Query(60.0, ge=1, le=3600)):
    """Get aggregated GPU metrics over a time window."""
    snap = gpu_profiler.get_snapshot(window_seconds)
    return {
        "avg_fps": snap.avg_fps,
        "min_fps": snap.min_fps,
        "max_fps": snap.max_fps,
        "avg_frame_time_ms": snap.avg_frame_time_ms,
        "p95_frame_time_ms": snap.p95_frame_time_ms,
        "avg_draw_calls": snap.avg_draw_calls,
        "avg_triangles": snap.avg_triangles,
        "avg_texture_memory_mb": snap.avg_texture_memory_mb,
        "sample_count": snap.sample_count,
    }


@router.get("/gpu/alerts")
def gpu_alerts():
    """Check for GPU performance alerts."""
    return {"alerts": gpu_profiler.check_alerts()}


@router.get("/gpu/suggestions")
def gpu_suggestions():
    """Get optimization suggestions based on current metrics."""
    return {"suggestions": gpu_profiler.get_optimization_suggestions()}


@router.get("/gpu/player/{player_id}")
def gpu_player_metrics(player_id: str, limit: int = Query(100, ge=1, le=1000)):
    """Get recent metrics for a specific player."""
    player_metrics = gpu_profiler.get_player_metrics(player_id, limit)
    return {
        "player_id": player_id,
        "metrics": [
            {
                "timestamp": m.timestamp,
                "frame_time_ms": m.frame_time_ms,
                "fps": m.fps,
                "draw_calls": m.draw_calls,
                "triangles": m.triangles,
            }
            for m in player_metrics
        ],
    }
