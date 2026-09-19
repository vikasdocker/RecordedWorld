"""
Road Network Service

Converts road segments from map data into 3D road geometry.
Handles road width, lanes, surfaces, and intersections.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.services.vector_ingester import RoadSegment, RoadType


@dataclass
class Road3D:
    """3D road with geometry."""
    id: str
    name: Optional[str]
    road_type: RoadType
    vertices: List[Tuple[float, float, float]]
    faces: List[Tuple[int, int, int]]
    width: float
    lanes: int
    length: float  # meters
    surface: Optional[str]


class RoadNetworkService:
    """Converts 2D road segments to 3D road geometry."""

    # Default widths in meters by road type
    ROAD_WIDTHS = {
        RoadType.MOTORWAY: 24.0,
        RoadType.TRUNK: 18.0,
        RoadType.PRIMARY: 14.0,
        RoadType.SECONDARY: 10.0,
        RoadType.TERTIARY: 8.0,
        RoadType.RESIDENTIAL: 6.0,
        RoadType.SERVICE: 4.0,
        RoadType.FOOTWAY: 2.0,
    }

    def __init__(self):
        self.roads: Dict[str, Road3D] = {}

    def create_road_3d(
        self,
        segment: RoadSegment,
        center_lon: float = 0.0,
        center_lat: float = 0.0,
        elevation_fn=None,
    ) -> Optional[Road3D]:
        """Convert a 2D road segment to 3D geometry."""
        if not segment.geometry or len(segment.geometry) < 2:
            return None

        width = self.ROAD_WIDTHS.get(segment.road_type, 6.0)
        half_width = width / 2

        # Convert to local coords
        local_pts = self._geo_to_local(segment.geometry, center_lon, center_lat)

        # Get elevation for each point
        left_pts = []
        right_pts = []
        for i, pt in enumerate(local_pts):
            elev = 0.0
            if elevation_fn:
                lon, lat = segment.geometry[i]
                elev = elevation_fn(lat, lon)

            # Calculate perpendicular offset
            if i < len(local_pts) - 1:
                dx = local_pts[i + 1][0] - pt[0]
                dz = local_pts[i + 1][1] - pt[1]
            else:
                dx = pt[0] - local_pts[i - 1][0]
                dz = pt[1] - local_pts[i - 1][1]

            length = math.sqrt(dx * dx + dz * dz)
            if length > 0:
                nx = -dz / length * half_width
                nz = dx / length * half_width
            else:
                nx, nz = half_width, 0

            left_pts.append((pt[0] + nx, elev, pt[1] + nz))
            right_pts.append((pt[0] - nx, elev, pt[1] - nz))

        # Generate vertices: left points + right points
        vertices = left_pts + right_pts

        # Generate faces
        n = len(local_pts)
        faces = []
        for i in range(n - 1):
            li = i
            ri = i + n
            lj = i + 1
            rj = i + 1 + n
            faces.append((li, lj, rj))
            faces.append((li, rj, ri))

        # Calculate road length
        length = 0.0
        for i in range(len(local_pts) - 1):
            dx = local_pts[i + 1][0] - local_pts[i][0]
            dz = local_pts[i + 1][1] - local_pts[i][1]
            length += math.sqrt(dx * dx + dz * dz)

        road = Road3D(
            id=segment.id,
            name=segment.name,
            road_type=segment.road_type,
            vertices=vertices,
            faces=faces,
            width=width,
            lanes=segment.lanes,
            length=length,
            surface=segment.surface,
        )

        self.roads[segment.id] = road
        return road

    def _geo_to_local(
        self,
        coords: List[Tuple[float, float]],
        center_lon: float,
        center_lat: float,
    ) -> List[Tuple[float, float]]:
        km_per_deg_lat = 111.0
        km_per_deg_lon = 111.0 * math.cos(math.radians(center_lat))

        local = []
        for lon, lat in coords:
            x = (lon - center_lon) * km_per_deg_lon * 1000
            z = (lat - center_lat) * km_per_deg_lat * 1000
            local.append((x, z))
        return local

    def batch_create_roads(
        self,
        segments: List[RoadSegment],
        center_lon: float = 0.0,
        center_lat: float = 0.0,
        elevation_fn=None,
    ) -> List[Road3D]:
        results = []
        for seg in segments:
            road = self.create_road_3d(seg, center_lon, center_lat, elevation_fn)
            if road:
                results.append(road)
        return results

    def get_roads_in_radius(
        self, lon: float, lat: float, radius_m: float
    ) -> List[Road3D]:
        result = []
        for road in self.roads.values():
            # Approximate check using first vertex
            if road.vertices:
                vx = road.vertices[0][0]
                vz = road.vertices[0][2]
                dist = math.sqrt(vx * vx + vz * vz)
                if dist <= radius_m:
                    result.append(road)
        return result

    def get_stats(self) -> Dict[str, Any]:
        total_length = sum(r.length for r in self.roads.values())
        return {
            "total_roads": len(self.roads),
            "total_length_m": total_length,
            "total_vertices": sum(len(r.vertices) for r in self.roads.values()),
            "by_type": {
                t.value: sum(1 for r in self.roads.values() if r.road_type == t)
                for t in RoadType
            },
        }


# Module-level singleton
road_service = RoadNetworkService()
