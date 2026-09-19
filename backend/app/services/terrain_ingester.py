"""
Terrain Ingestion Service

Handles DEM (Digital Elevation Model) and heightmap data for terrain generation.
Supports SRTM, GeoTIFF, and heightmap image formats.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np


@dataclass
class TerrainChunk:
    """A terrain chunk with height data."""
    id: str
    lat: float
    lon: float
    width_deg: float
    height_deg: float
    resolution: int  # pixels per degree
    height_data: Optional[np.ndarray] = None  # 2D height array
    min_elevation: float = 0.0
    max_elevation: float = 0.0

    def get_height_at(self, lat: float, lon: float) -> float:
        """Get interpolated height at a lat/lon position."""
        if self.height_data is None:
            return 0.0

        # Convert lat/lon to array indices
        y = (lat - self.lat) / self.height_deg * self.height_data.shape[0]
        x = (lon - self.lon) / self.width_deg * self.height_data.shape[1]

        y = max(0, min(y, self.height_data.shape[0] - 1))
        x = max(0, min(x, self.height_data.shape[1] - 1))

        # Bilinear interpolation
        y0 = int(y)
        x0 = int(x)
        y1 = min(y0 + 1, self.height_data.shape[0] - 1)
        x1 = min(x0 + 1, self.height_data.shape[1] - 1)

        dy = y - y0
        dx = x - x0

        h00 = float(self.height_data[y0, x0])
        h01 = float(self.height_data[y0, x1])
        h10 = float(self.height_data[y1, x0])
        h11 = float(self.height_data[y1, x1])

        h0 = h00 * (1 - dx) + h01 * dx
        h1 = h10 * (1 - dx) + h11 * dx
        return h0 * (1 - dy) + h1 * dy

    def to_mesh_grid(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Convert to mesh grid for 3D rendering."""
        if self.height_data is None:
            return np.array([]), np.array([]), np.array([])

        rows, cols = self.height_data.shape
        lats = np.linspace(self.lat, self.lat + self.height_deg, rows)
        lons = np.linspace(self.lon, self.lon + self.width_deg, cols)
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        return lat_grid, lon_grid, self.height_data.astype(float)


class TerrainIngester:
    """Ingests and processes terrain data from various sources."""

    def __init__(self):
        self.chunks: Dict[str, TerrainChunk] = {}

    def load_heightmap(
        self,
        chunk_id: str,
        lat: float,
        lon: float,
        width_deg: float,
        height_deg: float,
        height_data: np.ndarray,
    ) -> TerrainChunk:
        """Load terrain from a heightmap array."""
        chunk = TerrainChunk(
            id=chunk_id,
            lat=lat,
            lon=lon,
            width_deg=width_deg,
            height_deg=height_deg,
            resolution=height_data.shape[0],
            height_data=height_data,
            min_elevation=float(np.min(height_data)),
            max_elevation=float(np.max(height_data)),
        )
        self.chunks[chunk_id] = chunk
        return chunk

    def load_srtm_placeholder(
        self, chunk_id: str, lat: float, lon: float, resolution: int = 256
    ) -> TerrainChunk:
        """Load SRTM-style terrain (placeholder with flat elevation)."""
        height_data = np.zeros((resolution, resolution), dtype=np.float32)
        chunk = TerrainChunk(
            id=chunk_id,
            lat=lat,
            lon=lon,
            width_deg=1.0,
            height_deg=1.0,
            resolution=resolution,
            height_data=height_data,
        )
        self.chunks[chunk_id] = chunk
        return chunk

    def generate_procedural_terrain(
        self,
        chunk_id: str,
        lat: float,
        lon: float,
        width_deg: float,
        height_deg: float,
        resolution: int = 256,
        scale: float = 0.01,
        octaves: int = 4,
    ) -> TerrainChunk:
        """Generate procedural terrain using simplex noise approximation."""
        height_data = np.zeros((resolution, resolution), dtype=np.float32)

        for octave in range(octaves):
            freq = 2 ** octave
            amp = 0.5 ** octave
            for y in range(resolution):
                for x in range(resolution):
                    nx = x / resolution * scale * freq
                    ny = y / resolution * scale * freq
                    height_data[y, x] += self._simplex2d(nx, ny) * amp

        # Normalize to 0-100 meters
        height_data = (height_data - height_data.min()) / (height_data.max() - height_data.min() + 1e-8) * 100

        chunk = TerrainChunk(
            id=chunk_id,
            lat=lat,
            lon=lon,
            width_deg=width_deg,
            height_deg=height_deg,
            resolution=resolution,
            height_data=height_data,
            min_elevation=0.0,
            max_elevation=100.0,
        )
        self.chunks[chunk_id] = chunk
        return chunk

    def _simplex2d(self, x: float, y: float) -> float:
        """Simple 2D noise approximation."""
        return math.sin(x * 12.9898 + y * 78.233) * 0.5

    def get_chunk(self, chunk_id: str) -> Optional[TerrainChunk]:
        return self.chunks.get(chunk_id)

    def get_height_at(self, lat: float, lon: float) -> float:
        for chunk in self.chunks.values():
            if (chunk.lat <= lat <= chunk.lat + chunk.height_deg and
                chunk.lon <= lon <= chunk.lon + chunk.width_deg):
                return chunk.get_height_at(lat, lon)
        return 0.0

    def get_stats(self) -> Dict[str, Any]:
        total_pixels = sum(
            c.height_data.size if c.height_data is not None else 0
            for c in self.chunks.values()
        )
        return {
            "total_chunks": len(self.chunks),
            "total_pixels": total_pixels,
            "memory_mb": total_pixels * 4 / (1024 * 1024),  # float32
        }


# Module-level singleton
terrain_ingester = TerrainIngester()
