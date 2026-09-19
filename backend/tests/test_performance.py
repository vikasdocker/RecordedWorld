"""Tests for Phase 25: Performance — monitoring, caching, optimization."""

import time
import pytest
from app.services.performance_service import PerformanceMonitor, performance_monitor
from app.services.optimization import LRUCache, timed, cached, BatchProcessor


class TestPerformanceMonitor:
    def test_record_cpu(self):
        """Can record CPU usage."""
        monitor = PerformanceMonitor()
        monitor.record_cpu(50.0)
        snapshot = monitor.get_snapshot()
        assert snapshot.cpu_percent == 50.0

    def test_record_memory(self):
        """Can record memory usage."""
        monitor = PerformanceMonitor()
        monitor.record_memory(100.0, 25.0)
        snapshot = monitor.get_snapshot()
        assert snapshot.memory_mb == 100.0

    def test_record_response_time(self):
        """Can record response time."""
        monitor = PerformanceMonitor()
        monitor.record_response_time(50.0)
        stats = monitor.get_stats()
        assert stats["avg_response_time_ms"] == 50.0

    def test_record_ws_message(self):
        """Can record WebSocket message."""
        monitor = PerformanceMonitor()
        monitor.record_ws_message()
        stats = monitor.get_stats()
        assert stats["total_ws_messages"] == 1

    def test_record_db_query(self):
        """Can record DB query time."""
        monitor = PerformanceMonitor()
        monitor.record_db_query(10.0)
        snapshot = monitor.get_snapshot()
        assert snapshot.db_query_time_ms == 10.0

    def test_set_active_connections(self):
        """Can set active connections."""
        monitor = PerformanceMonitor()
        monitor.set_active_connections(42)
        snapshot = monitor.get_snapshot()
        assert snapshot.active_connections == 42

    def test_get_stats(self):
        """Can get stats."""
        monitor = PerformanceMonitor()
        monitor.record_cpu(50.0)
        monitor.record_memory(100.0)
        stats = monitor.get_stats()
        assert "uptime_seconds" in stats
        assert stats["avg_cpu_percent"] == 50.0

    def test_check_thresholds(self):
        """Threshold check returns warnings."""
        monitor = PerformanceMonitor()
        monitor.record_cpu(90.0)
        warnings = monitor.check_thresholds()
        assert len(warnings) > 0
        assert any("CPU" in w for w in warnings)

    def test_percentile(self):
        """Percentile calculation works."""
        monitor = PerformanceMonitor()
        for i in range(100):
            monitor.record_response_time(float(i))
        p50 = monitor._percentile(monitor._response_times, 50)
        p95 = monitor._percentile(monitor._response_times, 95)
        assert p50 < p95

    def test_global_monitor(self):
        """Global monitor exists."""
        assert performance_monitor is not None


class TestLRUCache:
    def test_set_get(self):
        """Can set and get values."""
        cache = LRUCache(max_size=10)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_miss(self):
        """Cache miss returns None."""
        cache = LRUCache()
        assert cache.get("nonexistent") is None

    def test_eviction(self):
        """Cache evicts oldest when full."""
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Evicts "a"
        assert cache.get("a") is None
        assert cache.get("d") == 4

    def test_ttl_expiry(self):
        """Cache entries expire after TTL."""
        cache = LRUCache(ttl_seconds=0.1)
        cache.set("key", "value")
        time.sleep(0.2)
        assert cache.get("key") is None

    def test_lru_order(self):
        """Accessing item moves it to end."""
        cache = LRUCache(max_size=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.get("a")  # Access "a"
        cache.set("d", 4)  # Evicts "b" (least recently used)
        assert cache.get("a") == 1
        assert cache.get("b") is None

    def test_delete(self):
        """Can delete from cache."""
        cache = LRUCache()
        cache.set("key", "value")
        assert cache.delete("key") is True
        assert cache.get("key") is None

    def test_clear(self):
        """Can clear cache."""
        cache = LRUCache()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert cache.get_stats()["size"] == 0

    def test_stats(self):
        """Cache stats are correct."""
        cache = LRUCache()
        cache.set("a", 1)
        cache.get("a")
        cache.get("b")
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1


class TestTimedDecorator:
    def test_timed(self):
        """Timed decorator tracks duration."""
        @timed
        def slow_function():
            time.sleep(0.01)
            return 42

        result = slow_function()
        assert result == 42
        assert slow_function._last_duration > 10  # ms


class TestCachedDecorator:
    def test_cached(self):
        """Cached decorator caches results."""
        cache = LRUCache()
        call_count = 0

        @cached(cache)
        def expensive(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        assert expensive(5) == 10
        assert expensive(5) == 10
        assert call_count == 1

    def test_cache_miss(self):
        """Different args get different cache entries."""
        cache = LRUCache()

        @cached(cache)
        def multiply(x):
            return x * 2

        assert multiply(5) == 10
        assert multiply(6) == 12


class TestBatchProcessor:
    def test_add(self):
        """Can add items to batch."""
        bp = BatchProcessor(batch_size=5)
        processed = []

        def process(batch):
            processed.extend(batch)

        bp.set_processor(process)
        for i in range(5):
            bp.add(i)
        time.sleep(0.1)
        assert len(processed) == 5

    def test_flush(self):
        """Can force flush."""
        bp = BatchProcessor(batch_size=100)
        processed = []

        def process(batch):
            processed.extend(batch)

        bp.set_processor(process)
        bp.add(1)
        bp.add(2)
        bp.flush()
        time.sleep(0.1)
        assert len(processed) == 2

    def test_stats(self):
        """Can get stats."""
        bp = BatchProcessor()
        stats = bp.get_stats()
        assert "buffer_size" in stats
