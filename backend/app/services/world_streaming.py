"""
World Streaming Service

Manages continuous world streaming as players move through the environment.
Handles chunk loading/unloading, predictive prefetching, and bandwidth management.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from enum import Enum


class ChunkLoadState(Enum):
    UNLOADED = "unloaded"
    QUEUED = "queued"
    LOADING = "loading"
    LOADED = "loaded"
    READY = "ready"
    UNLOADING = "unloading"


@dataclass
class WorldChunk:
    """A chunk of the world that can be loaded/unloaded independently."""
    id: str
    center_lat: float
    center_lon: float
    size_km: float
    state: ChunkLoadState = ChunkLoadState.UNLOADED
    priority: int = 0
    load_progress: float = 0.0  # 0.0 to 1.0
    data: Dict[str, Any] = field(default_factory=dict)
    last_access: float = 0.0
    load_start: float = 0.0
    load_time_ms: float = 0.0
    size_bytes: int = 0

    @property
    def is_ready(self) -> bool:
        return self.state == ChunkLoadState.READY

    def distance_to(self, lat: float, lon: float) -> float:
        """Calculate distance from a point to this chunk's center."""
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * math.cos(math.radians(self.center_lat))
        dx = (lon - self.center_lon) * km_per_deg_lon
        dy = (lat - self.center_lat) * km_per_deg_lat
        return math.sqrt(dx * dx + dy * dy)


@dataclass
class StreamConfig:
    """Configuration for world streaming."""
    load_radius_km: float = 2.0  # how far ahead to load
    unload_radius_km: float = 3.0  # when to unload
    prefetch_radius_km: float = 1.0  # predictive prefetch
    max_concurrent_loads: int = 4
    max_memory_mb: float = 512.0
    chunk_size_km: float = 0.5
    priority_decay_rate: float = 0.1


class WorldStreamingService:
    """Manages streaming of world chunks based on player position."""

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()
        self.chunks: Dict[str, WorldChunk] = {}
        self.load_queue: List[str] = []
        self.active_loads: Set[str] = set()
        self.player_positions: Dict[int, Tuple[float, float]] = {}
        self.on_chunk_loaded: Optional[Callable] = None
        self.on_chunk_unloaded: Optional[Callable] = None

    def update_player_position(
        self, player_id: int, lat: float, lon: float
    ):
        self.player_positions[player_id] = (lat, lon)
        self._update_priorities(lat, lon)
        self._process_load_queue()
        self._unload_distant_chunks(lat, lon)

    def get_chunks_for_player(self, player_id: int) -> List[WorldChunk]:
        pos = self.player_positions.get(player_id)
        if not pos:
            return []

        lat, lon = pos
        result = []
        for chunk in self.chunks.values():
            dist = chunk.distance_to(lat, lon)
            if dist <= self.config.load_radius_km:
                result.append(chunk)
        return result

    def get_ready_chunks(self) -> List[WorldChunk]:
        return [c for c in self.chunks.values() if c.is_ready]

    def get_chunk_at(self, lat: float, lon: float) -> Optional[WorldChunk]:
        for chunk in self.chunks.values():
            if chunk.distance_to(lat, lon) <= chunk.size_km / 2:
                return chunk
        return None

    def create_chunk(
        self,
        chunk_id: str,
        center_lat: float,
        center_lon: float,
        size_km: float = 0.5,
    ) -> WorldChunk:
        chunk = WorldChunk(
            id=chunk_id,
            center_lat=center_lat,
            center_lon=center_lon,
            size_km=size_km,
        )
        self.chunks[chunk_id] = chunk
        return chunk

    def _update_priorities(self, lat: float, lon: float):
        for chunk in self.chunks.values():
            dist = chunk.distance_to(lat, lon)
            if dist <= self.config.load_radius_km:
                chunk.priority = max(0, int(1000 - dist * 100))
                if chunk.id not in self.load_queue and chunk.state == ChunkLoadState.UNLOADED:
                    self.load_queue.append(chunk.id)
            else:
                chunk.priority = 0

        self.load_queue.sort(
            key=lambda cid: self.chunks[cid].priority if cid in self.chunks else 0,
            reverse=True,
        )

    def _process_load_queue(self):
        while (self.load_queue and
               len(self.active_loads) < self.config.max_concurrent_loads):
            chunk_id = self.load_queue.pop(0)
            if chunk_id in self.chunks and chunk_id not in self.active_loads:
                self._start_load(chunk_id)

    def _start_load(self, chunk_id: str):
        chunk = self.chunks.get(chunk_id)
        if not chunk:
            return

        chunk.state = ChunkLoadState.LOADING
        chunk.load_start = time.time()
        self.active_loads.add(chunk_id)

        # Simulate load completion (in production: async network fetch)
        chunk.state = ChunkLoadState.LOADED
        chunk.load_progress = 1.0
        chunk.load_time_ms = (time.time() - chunk.load_start) * 1000
        chunk.last_access = time.time()
        chunk.state = ChunkLoadState.READY
        self.active_loads.discard(chunk_id)

        if self.on_chunk_loaded:
            self.on_chunk_loaded(chunk)

    def _unload_distant_chunks(self, lat: float, lon: float):
        for chunk_id, chunk in list(self.chunks.items()):
            if chunk.state != ChunkLoadState.READY:
                continue
            dist = chunk.distance_to(lat, lon)
            if dist > self.config.unload_radius_km:
                chunk.state = ChunkLoadState.UNLOADING
                chunk.state = ChunkLoadState.UNLOADED
                chunk.load_progress = 0.0
                if self.on_chunk_unloaded:
                    self.on_chunk_unloaded(chunk)

    def get_stats(self) -> Dict[str, Any]:
        states = {}
        for chunk in self.chunks.values():
            states[chunk.state.value] = states.get(chunk.state.value, 0) + 1

        total_memory = sum(c.size_bytes for c in self.chunks.values())

        return {
            "total_chunks": len(self.chunks),
            "states": states,
            "load_queue_size": len(self.load_queue),
            "active_loads": len(self.active_loads),
            "total_memory_mb": total_memory / (1024 * 1024),
            "players_tracked": len(self.player_positions),
        }


# Module-level singleton
world_streaming = WorldStreamingService()
