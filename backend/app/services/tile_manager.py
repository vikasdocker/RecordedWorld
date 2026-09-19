"""
Tile/Chunk System for Base Map

Manages geographic tiles for streaming and caching.
Each tile contains terrain, buildings, roads, and other map features.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from enum import Enum

from app.services.map_provider import GeoBounds, TileCoords, MapTile


class TileState(Enum):
    UNLOADED = "unloaded"
    LOADING = "loading"
    LOADED = "loaded"
    CACHED = "cached"


@dataclass
class MapChunk:
    """A chunk of the base map containing multiple tiles."""
    id: str
    center_lat: float
    center_lon: float
    radius_km: float
    tiles: Dict[Tuple[int, int, int], MapTile] = field(default_factory=dict)
    state: TileState = TileState.UNLOADED
    last_access: float = 0.0
    priority: int = 0

    @property
    def tile_count(self) -> int:
        return len(self.tiles)

    def get_bounds(self) -> GeoBounds:
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * math.cos(math.radians(self.center_lat))
        dlat = self.radius_km / km_per_deg_lat
        dlon = self.radius_km / km_per_deg_lon
        return GeoBounds(
            min_lat=self.center_lat - dlat,
            min_lon=self.center_lon - dlon,
            max_lat=self.center_lat + dlat,
            max_lon=self.center_lon + dlon,
        )


class TileManager:
    """Manages tile loading, caching, and unloading."""

    def __init__(self, max_cached_tiles: int = 1000):
        self.max_cached_tiles = max_cached_tiles
        self.tiles: Dict[Tuple[int, int, int], MapTile] = {}
        self.chunks: Dict[str, MapChunk] = {}
        self.load_order: List[Tuple[int, int, int]] = []

    def get_or_create_chunk(
        self, center_lat: float, center_lon: float, radius_km: float = 1.0
    ) -> MapChunk:
        chunk_id = f"{center_lat:.4f}_{center_lon:.4f}_{radius_km}"
        if chunk_id not in self.chunks:
            self.chunks[chunk_id] = MapChunk(
                id=chunk_id,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_km=radius_km,
            )
        return self.chunks[chunk_id]

    def get_tiles_for_area(
        self, bounds: GeoBounds, zoom: int
    ) -> List[Tuple[TileCoords, MapTile]]:
        min_tile = TileCoords.from_lat_lon(bounds.max_lat, bounds.min_lon, zoom)
        max_tile = TileCoords.from_lat_lon(bounds.min_lat, bounds.max_lon, zoom)

        result = []
        for x in range(min_tile.x, max_tile.x + 1):
            for y in range(min_tile.y, max_tile.y + 1):
                coords = TileCoords(zoom=zoom, x=x, y=y)
                key = (zoom, x, y)
                if key in self.tiles:
                    tile = self.tiles[key]
                else:
                    tile = self._create_tile(coords)
                    self.tiles[key] = tile
                result.append((coords, tile))
        return result

    def _create_tile(self, coords: TileCoords) -> MapTile:
        bounds = coords.to_lat_lon_bounds()
        return MapTile(
            zoom=coords.zoom,
            x=coords.x,
            y=coords.y,
            data={"bounds": bounds.__dict__},
        )

    def load_tile(self, coords: TileCoords) -> MapTile:
        key = (coords.zoom, coords.x, coords.y)
        if key not in self.tiles:
            self.tiles[key] = self._create_tile(coords)
        tile = self.tiles[key]
        tile.data["state"] = TileState.LOADED.value
        tile.data["last_access"] = time.time()
        self._track_access(key)
        self._evict_if_needed()
        return tile

    def unload_tile(self, coords: TileCoords):
        key = (coords.zoom, coords.x, coords.y)
        if key in self.tiles:
            self.tiles[key].data["state"] = TileState.UNLOADED.value

    def get_loaded_tiles(self) -> List[MapTile]:
        return [t for t in self.tiles.values()
                if t.data.get("state") == TileState.LOADED.value]

    def _track_access(self, key: Tuple[int, int, int]):
        if key in self.load_order:
            self.load_order.remove(key)
        self.load_order.append(key)

    def _evict_if_needed(self):
        while len(self.tiles) > self.max_cached_tiles and self.load_order:
            oldest_key = self.load_order.pop(0)
            if oldest_key in self.tiles:
                del self.tiles[oldest_key]

    def get_chunk_tiles(self, chunk: MapChunk) -> List[MapTile]:
        bounds = chunk.get_bounds()
        result = []
        for zoom in range(10, 18):
            for key, tile in self.tiles.items():
                if key[0] == zoom:
                    tc = TileCoords(zoom=zoom, x=key[1], y=key[2])
                    tile_bounds = tc.to_lat_lon_bounds()
                    if bounds.overlaps(tile_bounds):
                        result.append(tile)
        return result

    def get_stats(self) -> Dict[str, Any]:
        loaded = sum(1 for t in self.tiles.values()
                     if t.data.get("state") == TileState.LOADED.value)
        return {
            "total_tiles": len(self.tiles),
            "loaded_tiles": loaded,
            "total_chunks": len(self.chunks),
            "max_cached": self.max_cached_tiles,
            "cache_usage_pct": (len(self.tiles) / self.max_cached_tiles * 100
                               if self.max_cached_tiles > 0 else 0),
        }


# Module-level singleton
tile_manager = TileManager()
