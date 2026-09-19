"""Monitoring and logging service."""
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from collections import deque
import asyncio
import os


LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def setup_logging():
    """Configure application logging."""
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[
            logging.FileHandler(LOG_DIR / "app.log"),
            logging.StreamHandler(),
        ],
    )

    # Suppress noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logging.getLogger("recorded_world")


logger = setup_logging()


@dataclass
class MetricPoint:
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class HealthStatus:
    service: str
    status: str  # healthy, degraded, unhealthy
    latency_ms: float = 0
    last_check: str = ""
    error: Optional[str] = None


class MetricsCollector:
    """Collects and stores application metrics."""

    def __init__(self):
        self.counters: Dict[str, int] = {}
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, deque] = {}
        self._max_history = 1000

    def increment(self, name: str, value: int = 1, labels: Dict[str, str] = None):
        key = self._make_key(name, labels)
        self.counters[key] = self.counters.get(key, 0) + value

    def gauge(self, name: str, value: float, labels: Dict[str, str] = None):
        key = self._make_key(name, labels)
        self.gauges[key] = value

    def histogram(self, name: str, value: float, labels: Dict[str, str] = None):
        key = self._make_key(name, labels)
        if key not in self.histograms:
            self.histograms[key] = deque(maxlen=self._max_history)
        self.histograms[key].append(MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {},
        ))

    def get_counter(self, name: str, labels: Dict[str, str] = None) -> int:
        key = self._make_key(name, labels)
        return self.counters.get(key, 0)

    def get_gauge(self, name: str, labels: Dict[str, str] = None) -> float:
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0)

    def get_histogram_stats(self, name: str, labels: Dict[str, str] = None) -> Dict:
        key = self._make_key(name, labels)
        values = [p.value for p in self.histograms.get(key, [])]
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "p95": 0}
        values_sorted = sorted(values)
        p95_idx = int(len(values_sorted) * 0.95)
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p95": values_sorted[p95_idx] if p95_idx < len(values_sorted) else values_sorted[-1],
        }

    def _make_key(self, name: str, labels: Dict[str, str] = None) -> str:
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name

    def export(self) -> Dict:
        return {
            "counters": self.counters,
            "gauges": self.gauges,
            "histograms": {k: self.get_histogram_stats(k.split("{")[0]) for k in self.histograms},
        }


class HealthChecker:
    """Performs health checks on all services."""

    def __init__(self):
        self.services: Dict[str, HealthStatus] = {}

    async def check_all(self) -> Dict[str, HealthStatus]:
        """Run health checks on all services."""
        checks = [
            self._check_service("backend", "http://localhost:8000/health"),
            self._check_service("websocket", "http://localhost:8765/health"),
        ]
        results = await asyncio.gather(*checks, return_exceptions=True)

        for result in results:
            if isinstance(result, HealthStatus):
                self.services[result.service] = result

        return self.services

    async def _check_service(self, name: str, url: str) -> HealthStatus:
        """Check a single service health."""
        import httpx

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                latency = (time.time() - start) * 1000

                if response.status_code == 200:
                    return HealthStatus(
                        service=name,
                        status="healthy",
                        latency_ms=round(latency, 2),
                        last_check=datetime.utcnow().isoformat(),
                    )
                else:
                    return HealthStatus(
                        service=name,
                        status="degraded",
                        latency_ms=round(latency, 2),
                        last_check=datetime.utcnow().isoformat(),
                        error=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            return HealthStatus(
                service=name,
                status="unhealthy",
                last_check=datetime.utcnow().isoformat(),
                error=str(e),
            )

    def get_overall_status(self) -> str:
        """Get overall system health."""
        if not self.services:
            return "unknown"
        statuses = [s.status for s in self.services.values()]
        if all(s == "healthy" for s in statuses):
            return "healthy"
        if any(s == "unhealthy" for s in statuses):
            return "unhealthy"
        return "degraded"


class AlertManager:
    """Manages alerts and notifications."""

    def __init__(self):
        self.alerts: List[Dict] = []
        self.alert_rules: List[Dict] = []

    def add_alert(self, level: str, message: str, source: str = "system"):
        alert = {
            "id": len(self.alerts) + 1,
            "level": level,
            "message": message,
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "acknowledged": False,
        }
        self.alerts.append(alert)
        logger.warning(f"ALERT [{level}] {message}")

    def acknowledge(self, alert_id: int):
        for alert in self.alerts:
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                break

    def get_active_alerts(self) -> List[Dict]:
        return [a for a in self.alerts if not a["acknowledged"]]


# Singletons
metrics = MetricsCollector()
health_checker = HealthChecker()
alert_manager = AlertManager()
