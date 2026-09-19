"""
Performance Optimization Utilities

Tools for profiling, caching, and optimizing.
"""

import time
import functools
from typing import Callable, Any, Optional
from collections import OrderedDict
import threading


class LRUCache:
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, ttl_seconds: float = 300):
        self._cache: OrderedDict = OrderedDict()
        self._timestamps: dict = {}
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                # Check TTL
                if time.time() - self._timestamps[key] > self._ttl:
                    del self._cache[key]
                    del self._timestamps[key]
                    self._misses += 1
                    return None
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def set(self, key: str, value: Any):
        """Set value in cache."""
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            self._timestamps[key] = time.time()
            if len(self._cache) > self._max_size:
                oldest = next(iter(self._cache))
                del self._cache[oldest]
                del self._timestamps[oldest]

    def delete(self, key: str) -> bool:
        """Delete value from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                return True
            return False

    def clear(self):
        """Clear cache."""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total > 0 else 0.0,
            }


def timed(func: Callable) -> Callable:
    """Decorator to time function execution."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        duration = (time.time() - start) * 1000  # ms
        wrapper._last_duration = duration
        return result
    wrapper._last_duration = 0.0
    return wrapper


def cached(cache: LRUCache, key_func: Optional[Callable] = None):
    """Decorator to cache function results."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"

            result = cache.get(cache_key)
            if result is not None:
                return result

            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        return wrapper
    return decorator


class BatchProcessor:
    """Process items in batches for efficiency."""

    def __init__(self, batch_size: int = 100, flush_interval: float = 1.0):
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._buffer: list = []
        self._lock = threading.Lock()
        self._last_flush = time.time()
        self._process_func: Optional[Callable] = None

    def set_processor(self, func: Callable):
        """Set the function to process batches."""
        self._process_func = func

    def add(self, item: Any):
        """Add item to batch."""
        with self._lock:
            self._buffer.append(item)
            if len(self._buffer) >= self._batch_size:
                self._flush()

    def flush(self):
        """Force flush the batch."""
        with self._lock:
            self._flush()

    def _flush(self):
        """Internal flush."""
        if not self._buffer or not self._process_func:
            return
        batch = self._buffer.copy()
        self._buffer.clear()
        self._last_flush = time.time()
        threading.Thread(target=self._process_func, args=(batch,), daemon=True).start()

    def get_stats(self) -> dict:
        """Get batch processor stats."""
        with self._lock:
            return {
                "buffer_size": len(self._buffer),
                "batch_size": self._batch_size,
                "seconds_since_flush": time.time() - self._last_flush,
            }


# Global caches
location_cache = LRUCache(max_size=5000, ttl_seconds=600)
user_cache = LRUCache(max_size=1000, ttl_seconds=300)
asset_cache = LRUCache(max_size=2000, ttl_seconds=1800)
