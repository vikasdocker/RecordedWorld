"""
Streaming and Caching Service

Manages tile loading priorities, network-aware streaming,
and memory-efficient caching for base map data.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum
import heapq


class CachePriority(Enum):
    CRITICAL = 0  # Currently visible
    HIGH = 1  # Within view distance
    MEDIUM = 2  # Nearby chunks
    LOW = 3  # Prefetch
    EVICTABLE = 4  # Can be removed


@dataclass
class StreamRequest:
    """A request to stream map data."""
    tile_key: Tuple[int, int, int]
    priority: CachePriority
    requested_at: float = field(default_factory=time.time)
    callback: Optional[str] = None


@dataclass
class CacheEntry:
    """A cached tile entry."""
    key: Tuple[int, int, int]
    data: Any
    size_bytes: int
    priority: CachePriority
    last_access: float = field(default_factory=time.time)
    access_count: int = 0
    pinned: bool = False


class StreamingCache:
    """LRU/LFU hybrid cache with priority-based eviction."""

    def __init__(self, max_size_bytes: int = 500 * 1024 * 1024):  # 500MB
        self.max_size_bytes = max_size_bytes
        self.entries: Dict[Tuple[int, int, int], CacheEntry] = {}
        self.current_size_bytes = 0
        self.pending_requests: List[StreamRequest] = []
        self.active_streams: Set[Tuple[int, int, int]] = set()

    def get(self, key: Tuple[int, int, int]) -> Optional[Any]:
        if key in self.entries:
            entry = self.entries[key]
            entry.last_access = time.time()
            entry.access_count += 1
            return entry.data
        return None

    def put(
        self,
        key: Tuple[int, int, int],
        data: Any,
        size_bytes: int,
        priority: CachePriority = CachePriority.MEDIUM,
    ):
        if key in self.entries:
            self.current_size_bytes -= self.entries[key].size_bytes

        self.entries[key] = CacheEntry(
            key=key,
            data=data,
            size_bytes=size_bytes,
            priority=priority,
        )
        self.current_size_bytes += size_bytes
        self._evict_if_needed()

    def remove(self, key: Tuple[int, int, int]) -> bool:
        if key in self.entries:
            self.current_size_bytes -= self.entries[key].size_bytes
            del self.entries[key]
            return True
        return False

    def pin(self, key: Tuple[int, int, int]):
        if key in self.entries:
            self.entries[key].pinned = True

    def unpin(self, key: Tuple[int, int, int]):
        if key in self.entries:
            self.entries[key].pinned = False

    def _evict_if_needed(self):
        while self.current_size_bytes > self.max_size_bytes:
            evictable = [
                (k, e) for k, e in self.entries.items()
                if not e.pinned
            ]
            if not evictable:
                break

            # Sort by priority (high number = low priority), then by last access
            evictable.sort(key=lambda x: (-x[1].priority.value, x[1].last_access))
            key, entry = evictable[0]
            self.current_size_bytes -= entry.size_bytes
            del self.entries[key]

    def request_stream(
        self, tile_key: Tuple[int, int, int], priority: CachePriority
    ):
        request = StreamRequest(tile_key=tile_key, priority=priority)
        heapq.heappush(self.pending_requests, (priority.value, request))

    def get_next_request(self) -> Optional[StreamRequest]:
        if self.pending_requests:
            _, request = heapq.heappop(self.pending_requests)
            return request
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            "cached_entries": len(self.entries),
            "current_size_mb": self.current_size_bytes / (1024 * 1024),
            "max_size_mb": self.max_size_bytes / (1024 * 1024),
            "usage_pct": self.current_size_bytes / self.max_size_bytes * 100,
            "pending_requests": len(self.pending_requests),
            "active_streams": len(self.active_streams),
            "pinned_entries": sum(1 for e in self.entries.values() if e.pinned),
        }


# Module-level singleton
streaming_cache = StreamingCache()
