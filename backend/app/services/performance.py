"""Performance optimization middleware and utilities."""
import time
import functools
from typing import Callable, Any
from collections import OrderedDict
import hashlib
import json


class ResponseCache:
    """Simple in-memory response cache with TTL."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 60):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._ttl_seconds:
                self._cache.move_to_end(key)
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any):
        if key in self._cache:
            del self._cache[key]
        elif len(self._cache) >= self._max_size:
            self._cache.popitem(last=False)
        self._cache[key] = (value, time.time())

    def invalidate(self, prefix: str = ""):
        keys_to_delete = [k for k in self._cache if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._cache[k]


cache = ResponseCache()


def cached(ttl_seconds: int = 60, prefix: str = ""):
    """Decorator for caching function results."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{prefix}:{func.__name__}:{hashlib.md5(json.dumps({'args': str(args), 'kwargs': str(kwargs)}).encode()).hexdigest()}"
            result = cache.get(cache_key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(cache_key, result)
            return result
        return wrapper
    return decorator


def rate_limit(max_calls: int, period_seconds: int):
    """Rate limiting decorator."""
    calls = []

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            calls[:] = [t for t in calls if now - t < period_seconds]
            if len(calls) >= max_calls:
                raise Exception(f"Rate limit exceeded: {max_calls} calls per {period_seconds}s")
            calls.append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator


class ObjectPool:
    """Generic object pool for reuse."""

    def __init__(self, factory: Callable, max_size: int = 100):
        self._factory = factory
        self._pool = []
        self._max_size = max_size

    def acquire(self) -> Any:
        if self._pool:
            return self._pool.pop()
        return self._factory()

    def release(self, obj: Any):
        if len(self._pool) < self._max_size:
            self._pool.append(obj)
