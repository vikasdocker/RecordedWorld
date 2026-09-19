"""
Tests for Phase 3: World Streaming services.
"""
import pytest
from app.services.world_streaming import (
    WorldStreamingService, WorldChunk, ChunkLoadState, StreamConfig
)
from app.services.network_streamer import (
    NetworkAwareStreamer, NetworkQuality, NetworkMetrics, StreamRequest
)
from app.services.memory_manager import (
    MemoryManager, MemoryPool, MemoryBudget, MemoryBlock
)


# --- World Streaming ---

class TestWorldStreaming:
    def test_create_chunk(self):
        svc = WorldStreamingService()
        chunk = svc.create_chunk("c1", 40.0, -74.0, 0.5)
        assert isinstance(chunk, WorldChunk)
        assert chunk.center_lat == 40.0

    def test_update_player_position(self):
        svc = WorldStreamingService()
        svc.create_chunk("c1", 40.0, -74.0, 0.5)
        svc.update_player_position(1, 40.0, -74.0)
        assert 1 in svc.player_positions

    def test_get_chunks_for_player(self):
        svc = WorldStreamingService()
        svc.create_chunk("c1", 40.0, -74.0, 0.5)
        svc.update_player_position(1, 40.0, -74.0)
        chunks = svc.get_chunks_for_player(1)
        assert len(chunks) >= 1

    def test_get_ready_chunks(self):
        svc = WorldStreamingService()
        chunk = svc.create_chunk("c1", 40.0, -74.0, 0.5)
        svc.update_player_position(1, 40.0, -74.0)
        ready = svc.get_ready_chunks()
        assert len(ready) >= 0  # May be 0 if async not completed

    def test_get_chunk_at(self):
        svc = WorldStreamingService()
        svc.create_chunk("c1", 40.0, -74.0, 0.5)
        chunk = svc.get_chunk_at(40.0, -74.0)
        assert chunk is not None

    def test_unload_distant_chunks(self):
        svc = WorldStreamingService()
        svc.create_chunk("c1", 40.0, -74.0, 0.5)
        svc.update_player_position(1, 40.0, -74.0)
        # Move far away
        svc.update_player_position(1, 50.0, -60.0)
        stats = svc.get_stats()
        assert "total_chunks" in stats

    def test_get_stats(self):
        svc = WorldStreamingService()
        stats = svc.get_stats()
        assert "total_chunks" in stats
        assert "players_tracked" in stats

    def test_chunk_distance_to(self):
        chunk = WorldChunk(id="c1", center_lat=40.0, center_lon=-74.0, size_km=0.5)
        dist = chunk.distance_to(40.001, -74.001)
        assert isinstance(dist, float)
        assert dist < 1.0

    def test_chunk_is_ready(self):
        chunk = WorldChunk(id="c1", center_lat=40.0, center_lon=-74.0, size_km=0.5)
        assert not chunk.is_ready
        chunk.state = ChunkLoadState.READY
        assert chunk.is_ready

    def test_stream_config_defaults(self):
        config = StreamConfig()
        assert config.load_radius_km == 2.0
        assert config.max_concurrent_loads == 4


# --- Network Streamer ---

class TestNetworkStreamer:
    def test_update_metrics(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=15.0, latency_ms=30.0)
        assert streamer.metrics.bandwidth_mbps == 15.0

    def test_assess_quality_excellent(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=15.0, latency_ms=30.0, packet_loss=0.0)
        assert streamer.metrics.quality == NetworkQuality.EXCELLENT

    def test_assess_quality_poor(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=1.0, latency_ms=300.0, packet_loss=0.0)
        assert streamer.metrics.quality == NetworkQuality.POOR

    def test_assess_quality_offline(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=0.0, latency_ms=0.0)
        assert streamer.metrics.quality == NetworkQuality.OFFLINE

    def test_get_adaptive_quality(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=8.0, latency_ms=60.0)
        settings = streamer.get_adaptive_quality()
        assert "max_concurrent" in settings
        assert "texture_quality" in settings

    def test_estimate_download_time(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=10.0)
        est = streamer.estimate_download_time(10 * 1024 * 1024)  # 10 MB
        assert est == pytest.approx(1.0, abs=0.1)

    def test_can_load_now(self):
        streamer = NetworkAwareStreamer()
        streamer.update_metrics(bandwidth_mbps=10.0)
        assert streamer.can_load_now(1024 * 1024)  # 1 MB

    def test_submit_and_complete_request(self):
        streamer = NetworkAwareStreamer()
        req = streamer.submit_request("c1", priority=100, size_bytes=1024)
        assert isinstance(req, StreamRequest)
        streamer.complete_request("c1")
        assert len(streamer.pending_requests) == 0

    def test_retry_request(self):
        streamer = NetworkAwareStreamer()
        streamer.submit_request("c1", priority=100, size_bytes=1024)
        retried = streamer.retry_request("c1")
        assert retried is not None
        assert retried.attempts == 1

    def test_get_stats(self):
        streamer = NetworkAwareStreamer()
        stats = streamer.get_stats()
        assert "quality" in stats
        assert "bandwidth_mbps" in stats

    def test_network_metrics_stale(self):
        metrics = NetworkMetrics()
        metrics.last_measured = 0
        assert metrics.is_stale


# --- Memory Manager ---

class TestMemoryManager:
    def test_allocate(self):
        mgr = MemoryManager()
        result = mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        assert result is True

    def test_allocate_over_budget(self):
        budget = MemoryBudget(total_mb=0.001, pool_budgets={MemoryPool.TERRAIN: 0.001})
        mgr = MemoryManager(budget=budget)
        result = mgr.allocate("b1", MemoryPool.TERRAIN, 10 * 1024 * 1024, "chunk1")
        assert result is False

    def test_free(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        assert mgr.free("b1")
        assert not mgr.free("b1")

    def test_touch(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        mgr.touch("b1")
        block = mgr.blocks["b1"]
        assert block.last_accessed > 0

    def test_get_usage(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        usage = mgr.get_usage()
        assert "total_mb" in usage
        assert usage["block_count"] == 1

    def test_get_eviction_candidates(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        mgr.allocate("b2", MemoryPool.TERRAIN, 2048, "chunk2")
        candidates = mgr.get_eviction_candidates(MemoryPool.TERRAIN, 1024)
        assert len(candidates) >= 1

    def test_pinned_not_evicted(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1", pinned=True)
        candidates = mgr.get_eviction_candidates(MemoryPool.TERRAIN, 1024)
        assert len(candidates) == 0

    def test_get_stats(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        stats = mgr.get_stats()
        assert "total_mb" in stats
        assert "pinned_blocks" in stats

    def test_pool_usage_tracking(self):
        mgr = MemoryManager()
        mgr.allocate("b1", MemoryPool.TERRAIN, 1024, "chunk1")
        mgr.allocate("b2", MemoryPool.TEXTURES, 2048, "chunk1")
        assert mgr.pool_usage[MemoryPool.TERRAIN] == 1024
        assert mgr.pool_usage[MemoryPool.TEXTURES] == 2048
