"""
Level of Detail (LOD) System

Manages different detail levels for map features based on camera distance.
Ensures smooth transitions between LOD levels.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import IntEnum


class LODLevel(IntEnum):
    ULTRA = 0  # < 100m - full detail
    HIGH = 1  # 100-500m - high detail
    MEDIUM = 2  # 500-2000m - medium detail
    LOW = 3  # 2000-5000m - low detail
    MINIMAL = 4  # > 5000m - minimal detail


@dataclass
class LODConfig:
    """Configuration for a LOD level."""
    level: LODLevel
    max_distance: float
    building_detail: float  # 0.0 to 1.0
    road_detail: float
    terrain_resolution: int
    vegetation_density: float
    max_vertices: int


DEFAULT_LOD_CONFIGS = [
    LODConfig(
        level=LODLevel.ULTRA, max_distance=100.0,
        building_detail=1.0, road_detail=1.0,
        terrain_resolution=256, vegetation_density=1.0,
        max_vertices=100000,
    ),
    LODConfig(
        level=LODLevel.HIGH, max_distance=500.0,
        building_detail=0.8, road_detail=0.9,
        terrain_resolution=128, vegetation_density=0.7,
        max_vertices=50000,
    ),
    LODConfig(
        level=LODLevel.MEDIUM, max_distance=2000.0,
        building_detail=0.5, road_detail=0.7,
        terrain_resolution=64, vegetation_density=0.4,
        max_vertices=20000,
    ),
    LODConfig(
        level=LODLevel.LOW, max_distance=5000.0,
        building_detail=0.3, road_detail=0.5,
        terrain_resolution=32, vegetation_density=0.2,
        max_vertices=5000,
    ),
    LODConfig(
        level=LODLevel.MINIMAL, max_distance=float("inf"),
        building_detail=0.1, road_detail=0.3,
        terrain_resolution=16, vegetation_density=0.05,
        max_vertices=1000,
    ),
]


@dataclass
class LODSelection:
    """Selected LOD level for a feature."""
    level: LODLevel
    config: LODConfig
    distance: float
    fade_factor: float  # 0.0 to 1.0 for smooth transitions


class LODManager:
    """Manages LOD selection and detail reduction."""

    def __init__(self, configs: Optional[List[LODConfig]] = None):
        self.configs = configs or DEFAULT_LOD_CONFIGS
        self.configs.sort(key=lambda c: c.max_distance)

    def select_lod(
        self,
        distance: float,
        importance: float = 1.0,
    ) -> LODSelection:
        """Select appropriate LOD based on distance."""
        config = self.configs[-1]  # Default to lowest
        for cfg in self.configs:
            if distance <= cfg.max_distance:
                config = cfg
                break

        # Calculate fade factor for smooth transitions
        fade = 1.0
        if config.level > 0:
            prev_config = self.configs[config.level - 1]
            transition_start = prev_config.max_distance * 0.8
            transition_end = config.max_distance * 0.2
            if transition_start < distance < transition_end:
                fade = (distance - transition_start) / (transition_end - transition_start)
                fade = max(0.0, min(1.0, 1.0 - fade))

        return LODSelection(
            level=config.level,
            config=config,
            distance=distance,
            fade_factor=fade,
        )

    def reduce_vertices(
        self,
        vertices: List[Tuple[float, float, float]],
        target_count: int,
    ) -> List[Tuple[float, float, float]]:
        """Reduce vertex count using distance-based decimation."""
        if len(vertices) <= target_count:
            return vertices

        step = len(vertices) / target_count
        reduced = []
        for i in range(0, len(vertices), int(step)):
            reduced.append(vertices[i])
            if len(reduced) >= target_count:
                break

        return reduced

    def simplify_polygon(
        self,
        points: List[Tuple[float, float]],
        tolerance: float = 0.1,
    ) -> List[Tuple[float, float]]:
        """Simplify polygon using Douglas-Peucker algorithm."""
        if len(points) <= 2:
            return points

        # Find point with maximum distance from line between first and last
        start = points[0]
        end = points[-1]
        max_dist = 0
        max_idx = 0

        for i in range(1, len(points) - 1):
            dist = self._point_to_line_distance(points[i], start, end)
            if dist > max_dist:
                max_dist = dist
                max_idx = i

        if max_dist > tolerance:
            left = self.simplify_polygon(points[:max_idx + 1], tolerance)
            right = self.simplify_polygon(points[max_idx:], tolerance)
            return left[:-1] + right
        else:
            return [start, end]

    def _point_to_line_distance(
        self,
        point: Tuple[float, float],
        line_start: Tuple[float, float],
        line_end: Tuple[float, float],
    ) -> float:
        x0, y0 = point
        x1, y1 = line_start
        x2, y2 = line_end

        num = abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1)
        den = math.sqrt((y2 - y1) ** 2 + (x2 - x1) ** 2)
        return num / den if den > 0 else 0

    def get_config_for_distance(self, distance: float) -> LODConfig:
        for cfg in self.configs:
            if distance <= cfg.max_distance:
                return cfg
        return self.configs[-1]


# Module-level singleton
lod_manager = LODManager()
