"""
Rate Limiting Middleware

Per-user rate limiting with sliding window.
"""

import time
import threading
from typing import Dict, Optional, Tuple
from collections import defaultdict


class RateLimiter:
    """Sliding window rate limiter."""

    def __init__(self, window_seconds: int = 60, max_requests: int = 100):
        self._window = window_seconds
        self._max_requests = max_requests
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> Tuple[bool, Dict]:
        """Check if request is allowed. Returns (allowed, info)."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            # Clean old entries
            self._requests[key] = [
                t for t in self._requests[key] if t > cutoff
            ]

            current_count = len(self._requests[key])

            if current_count >= self._max_requests:
                oldest = self._requests[key][0] if self._requests[key] else now
                retry_after = int(self._window - (now - oldest)) + 1
                return False, {
                    "limit": self._max_requests,
                    "remaining": 0,
                    "reset_in": retry_after,
                }

            self._requests[key].append(now)
            return True, {
                "limit": self._max_requests,
                "remaining": self._max_requests - current_count - 1,
                "reset_in": self._window,
            }

    def get_usage(self, key: str) -> Dict:
        """Get current usage for a key."""
        now = time.time()
        cutoff = now - self._window

        with self._lock:
            self._requests[key] = [
                t for t in self._requests[key] if t > cutoff
            ]
            return {
                "count": len(self._requests[key]),
                "limit": self._max_requests,
                "remaining": max(0, self._max_requests - len(self._requests[key])),
            }

    def reset(self, key: str):
        """Reset rate limit for a key."""
        with self._lock:
            self._requests[key] = []

    def get_stats(self) -> Dict:
        """Get global rate limiter stats."""
        with self._lock:
            return {
                "tracked_keys": len(self._requests),
                "window_seconds": self._window,
                "max_requests": self._max_requests,
            }


# Pre-configured limiters
api_limiter = RateLimiter(window_seconds=60, max_requests=100)
upload_limiter = RateLimiter(window_seconds=300, max_requests=10)
ws_limiter = RateLimiter(window_seconds=60, max_requests=200)
auth_limiter = RateLimiter(window_seconds=300, max_requests=10)
