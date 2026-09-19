"""
Building Footprint Service

Processes building footprints from map data into 3D geometry.
Extrudes polygons to building heights, generates roof geometry.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.vector_ingester import BuildingFootprint, BuildingType


@dataclass
class Building3D:
    """3D building with vertices and faces."""
    id: str
    name: Optional[str]
    building_type: BuildingType
    vertices: List[Tuple[float, float, float]]  # (x, y, z) in local coords
    faces: List[Tuple[int, int, int]]  # triangle indices
    height: float
    num_floors: int
    footprint_area: float  # square meters
    centroid: Tuple[float, float]  # (lon, lat) of center


class BuildingFootprintService:
    """Converts 2D building footprints to 3D geometry."""

    def __init__(self):
        self.buildings: Dict[str, Building3D] = {}
        self.default_floor_height = 3.0  # meters

    def extrude_footprint(
        self,
        footprint: BuildingFootprint,
        center_lon: float = 0.0,
        center_lat: float = 0.0,
    ) -> Optional[Building3D]:
        """Extrude a 2D footprint to 3D building."""
        if not footprint.geometry:
            return None

        height = footprint.height
        if height is None and footprint.num_floors:
            height = footprint.num_floors * self.default_floor_height
        elif height is None:
            height = 3.0

        num_floors = footprint.num_floors or max(1, int(height / self.default_floor_height))

        # Convert geographic coords to local meters
        local_footprint = self._geo_to_local(
            footprint.geometry, center_lon, center_lat
        )

        # Generate vertices: bottom ring + top ring
        vertices = []
        for pt in local_footprint:
            vertices.append((pt[0], 0.0, pt[1]))  # bottom
        for pt in local_footprint:
            vertices.append((pt[0], height, pt[1]))  # top

        # Generate faces: side walls
        n = len(local_footprint)
        faces = []
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, j + n))
            faces.append((i, j + n, i + n))

        # Roof cap (fan from center)
        centroid_x = sum(p[0] for p in local_footprint) / n
        centroid_z = sum(p[1] for p in local_footprint) / n
        roof_center_idx = len(vertices)
        vertices.append((centroid_x, height, centroid_z))

        for i in range(n):
            j = (i + 1) % n
            faces.append((i + n, j + n, roof_center_idx))

        # Calculate footprint area
        area = self._polygon_area(local_footprint)

        centroid = (
            sum(p[0] for p in footprint.geometry) / len(footprint.geometry),
            sum(p[1] for p in footprint.geometry) / len(footprint.geometry),
        )

        building = Building3D(
            id=footprint.id,
            name=footprint.name,
            building_type=footprint.building_type,
            vertices=vertices,
            faces=faces,
            height=height,
            num_floors=num_floors,
            footprint_area=area,
            centroid=centroid,
        )

        self.buildings[footprint.id] = building
        return building

    def _geo_to_local(
        self,
        coords: List[Tuple[float, float]],
        center_lon: float,
        center_lat: float,
    ) -> List[Tuple[float, float]]:
        """Convert geographic coordinates to local meters."""
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))

        local = []
        for lon, lat in coords:
            x = (lon - center_lon) * km_per_deg_lon * 1000
            z = (lat - center_lat) * km_per_deg_lat * 1000
            local.append((x, z))
        return local

    def _polygon_area(self, points: List[Tuple[float, float]]) -> float:
        """Calculate polygon area using shoelace formula."""
        if len(points) < 3:
            return 0.0
        area = 0.0
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    def batch_extrude(
        self,
        footprints: List[BuildingFootprint],
        center_lon: float = 0.0,
        center_lat: float = 0.0,
    ) -> List[Building3D]:
        results = []
        for fp in footprints:
            building = self.extrude_footprint(fp, center_lon, center_lat)
            if building:
                results.append(building)
        return results

    def get_buildings_in_radius(
        self, lon: float, lat: float, radius_m: float
    ) -> List[Building3D]:
        result = []
        for b in self.buildings.values():
            dx = (b.centroid[0] - lon) * 111000 * math.cos(math.radians(lat))
            dy = (b.centroid[1] - lat) * 111000
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= radius_m:
                result.append(b)
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_buildings": len(self.buildings),
            "total_vertices": sum(len(b.vertices) for b in self.buildings.values()),
            "total_faces": sum(len(b.faces) for b in self.buildings.values()),
        }


# Module-level singleton
building_service = BuildingFootprintService()
