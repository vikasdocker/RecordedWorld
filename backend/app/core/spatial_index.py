"""
Grid-based Spatial Index

Provides spatial indexing for geographic coordinates without PostGIS/SpatiaLite.
Uses a uniform grid overlay where the world is divided into cells of configurable size.

Query strategy:
  1. Convert search radius to grid cells
  2. Find candidate cells (center cell + neighbors within radius)
  3. Filter locations by grid_cell_id
  4. Refine with haversine distance for exact results

Cell ID format: "{lat_cell}:{lon_cell}" (string for SQLite compatibility)
"""

import math
from typing import List, Tuple, Optional
from dataclasses import dataclass

from app.core.geospatial import WGS84Coordinate, haversine_distance, _meters_per_degree_latitude, _meters_per_degree_longitude


@dataclass(frozen=True)
class GridCell:
    """A cell in the spatial grid."""
    lat_cell: int
    lon_cell: int

    @property
    def cell_id(self) -> str:
        return f"{self.lat_cell}:{self.lon_cell}"

    @classmethod
    def from_coordinate(cls, coord: WGS84Coordinate, cell_size_meters: float) -> "GridCell":
        """Compute the grid cell for a WGS84 coordinate."""
        lat_cell = int(math.floor(coord.latitude / _cell_size_degrees_lat(coord.latitude, cell_size_meters)))
        lon_cell = int(math.floor(coord.longitude / _cell_size_degrees_lon(coord.latitude, cell_size_meters)))
        return cls(lat_cell=lat_cell, lon_cell=lon_cell)

    @classmethod
    def from_id(cls, cell_id: str) -> "GridCell":
        parts = cell_id.split(":")
        return cls(lat_cell=int(parts[0]), lon_cell=int(parts[1]))


def _cell_size_degrees_lat(latitude: float, cell_size_meters: float) -> float:
    """Convert cell size from meters to degrees latitude."""
    return cell_size_meters / _meters_per_degree_latitude(latitude)


def _cell_size_degrees_lon(latitude: float, cell_size_meters: float) -> float:
    """Convert cell size from meters to degrees longitude."""
    return cell_size_meters / _meters_per_degree_longitude(latitude)


def compute_grid_cell_id(coord: WGS84Coordinate, cell_size_meters: float = 100.0) -> str:
    """
    Compute the grid cell ID for a coordinate.

    Args:
        coord: WGS84 coordinate
        cell_size_meters: Grid cell size in meters (default 100m)

    Returns:
        Grid cell ID string (e.g., "45:-122")
    """
    cell = GridCell.from_coordinate(coord, cell_size_meters)
    return cell.cell_id


def compute_candidate_cells(
    center: WGS84Coordinate,
    radius_meters: float,
    cell_size_meters: float = 100.0,
) -> List[str]:
    """
    Compute the set of grid cell IDs that could contain locations within
    radius_meters of the center point.

    Args:
        center: Center point
        radius_meters: Search radius
        cell_size_meters: Grid cell size

    Returns:
        List of grid cell ID strings
    """
    center_cell = GridCell.from_coordinate(center, cell_size_meters)

    # How many cells does the radius span in each direction?
    d_lat_deg = _cell_size_degrees_lat(center.latitude, cell_size_meters)
    d_lon_deg = _cell_size_degrees_lon(center.latitude, cell_size_meters)

    # Convert radius to approximate cell count (add 1 for safety)
    n_lat = int(math.ceil(radius_meters / cell_size_meters)) + 1
    n_lon = int(math.ceil(radius_meters / cell_size_meters)) + 1

    cells = []
    for dlat in range(-n_lat, n_lat + 1):
        for dlon in range(-n_lon, n_lon + 1):
            cell = GridCell(
                lat_cell=center_cell.lat_cell + dlat,
                lon_cell=center_cell.lon_cell + dlon,
            )
            cells.append(cell.cell_id)

    return cells


def search_locations_sql(
    center: WGS84Coordinate,
    radius_meters: float,
    cell_size_meters: float = 100.0,
) -> Tuple[List[str], float, float, float, float]:
    """
    Compute SQL filter parameters for spatial proximity search.

    Returns:
        (cell_ids, min_lat, max_lat, min_lon, max_lon)
        Use these to filter: WHERE grid_cell_id IN (cell_ids)
        AND latitude BETWEEN min_lat AND max_lat
        AND longitude BETWEEN min_lon AND max_lon
    """
    cells = compute_candidate_cells(center, radius_meters, cell_size_meters)

    # Bounding box for coarse filtering
    from app.core.geospatial import bounding_box
    min_lat, max_lat, min_lon, max_lon = bounding_box(center, radius_meters)

    return cells, min_lat, max_lat, min_lon, max_lon


def generate_spatial_index_sql(cell_size_meters: float = 100.0) -> str:
    """
    Generate SQL to create a spatial index table.
    Call this once during migration/setup.
    """
    return """
    CREATE TABLE IF NOT EXISTS spatial_grid_cells (
        cell_id TEXT PRIMARY KEY,
        lat_center REAL NOT NULL,
        lon_center REAL NOT NULL,
        location_count INTEGER DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_locations_grid_cell ON locations(grid_cell_id);
    """


def update_location_grid_cell(
    latitude: float,
    longitude: float,
    cell_size_meters: float = 100.0,
) -> str:
    """Compute the grid_cell_id for a location being inserted/updated."""
    coord = WGS84Coordinate(latitude=latitude, longitude=longitude)
    return compute_grid_cell_id(coord, cell_size_meters)
