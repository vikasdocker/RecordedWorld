"""
Tests for GPU Profiler and monitoring endpoints.
"""
import pytest
import time
from fastapi.testclient import TestClient
from app.main import app
from app.services.gpu_profiler import GPUProfiler, FrameMetrics, GPUSnapshot


client = TestClient(app)


class TestGPUProfiler:
    def test_record_frame(self):
        profiler = GPUProfiler()
        metrics = FrameMetrics(
            timestamp=time.time(),
            frame_time_ms=16.67,
            fps=60.0,
            draw_calls=500,
            triangles=100000,
            player_id="player1",
        )
        profiler.record_frame(metrics)
        assert len(profiler._metrics) == 1

    def test_get_snapshot_empty(self):
        profiler = GPUProfiler()
        snap = profiler.get_snapshot()
        assert snap.sample_count == 0
        assert snap.avg_fps == 0.0

    def test_get_snapshot_with_data(self):
        profiler = GPUProfiler()
        now = time.time()
        for i in range(10):
            profiler.record_frame(FrameMetrics(
                timestamp=now - (10 - i) * 0.016,
                frame_time_ms=16.67 + (i % 3),
                fps=60.0 - (i % 5),
                draw_calls=500 + i * 10,
                triangles=100000 + i * 5000,
            ))
        snap = profiler.get_snapshot(window_seconds=1.0)
        assert snap.sample_count == 10
        assert snap.avg_fps > 0
        assert snap.min_fps <= snap.avg_fps <= snap.max_fps

    def test_player_metrics(self):
        profiler = GPUProfiler()
        now = time.time()
        for i in range(5):
            profiler.record_frame(FrameMetrics(
                timestamp=now,
                frame_time_ms=16.0,
                fps=60.0,
                player_id="test_player",
            ))
        metrics = profiler.get_player_metrics("test_player")
        assert len(metrics) == 5

    def test_check_alerts_no_data(self):
        profiler = GPUProfiler()
        alerts = profiler.check_alerts()
        assert alerts == []

    def test_check_alerts_low_fps(self):
        profiler = GPUProfiler()
        now = time.time()
        for i in range(5):
            profiler.record_frame(FrameMetrics(
                timestamp=now,
                frame_time_ms=50.0,
                fps=20.0,  # Below 30fps threshold
            ))
        alerts = profiler.check_alerts()
        assert any(a["type"] == "low_fps" for a in alerts)

    def test_optimization_suggestions(self):
        profiler = GPUProfiler()
        suggestions = profiler.get_optimization_suggestions()
        assert isinstance(suggestions, list)
        assert len(suggestions) > 0


class TestGPUMonitoringAPI:
    def test_report_frame_metrics(self):
        response = client.post("/api/monitoring/gpu/report", json={
            "frame_time_ms": 16.67,
            "fps": 60.0,
            "draw_calls": 500,
            "triangles": 100000,
            "player_id": "test_api_player",
        })
        assert response.status_code == 200
        assert response.json()["status"] == "recorded"

    def test_get_gpu_snapshot(self):
        # Report some metrics first
        for i in range(3):
            client.post("/api/monitoring/gpu/report", json={
                "frame_time_ms": 16.0 + i,
                "fps": 60.0 - i,
                "draw_calls": 400 + i * 50,
            })
        response = client.get("/api/monitoring/gpu/snapshot?window_seconds=60")
        assert response.status_code == 200
        data = response.json()
        assert "avg_fps" in data
        assert "sample_count" in data

    def test_get_gpu_alerts(self):
        response = client.get("/api/monitoring/gpu/alerts")
        assert response.status_code == 200
        assert "alerts" in response.json()

    def test_get_gpu_suggestions(self):
        response = client.get("/api/monitoring/gpu/suggestions")
        assert response.status_code == 200
        assert "suggestions" in response.json()

    def test_get_player_gpu_metrics(self):
        # Report with player_id
        client.post("/api/monitoring/gpu/report", json={
            "frame_time_ms": 16.0,
            "fps": 60.0,
            "player_id": "tracked_player",
        })
        response = client.get("/api/monitoring/gpu/player/tracked_player")
        assert response.status_code == 200
        data = response.json()
        assert data["player_id"] == "tracked_player"
        assert isinstance(data["metrics"], list)
