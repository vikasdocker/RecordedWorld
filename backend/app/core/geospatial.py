"""
Geographic Coordinate System

Provides WGS84 coordinate handling, conversion to local ENU frames,
and precision-safe game coordinate management.

Architecture:
  GPS (WGS84 lat/lon/alt)
    → ENU (East/North/Up local frame relative to an origin)
      → Game coordinates (origin-relative float)

Storage: Always store WGS84 (lat, lon, alt) in the database.
Rendering: Use ENU/local coordinates for game world positions.
"""

import math
from dataclasses import dataclass
from typing import Optional


# WGS84 ellipsoid constants
WGS84_A = 6378137.0  # Semi-major axis (meters)
WGS84_F = 1 / 298.257223563  # Flattening
WGS84_B = WGS84_A * (1 - WGS84_F)  # Semi-minor axis
WGS84_E2 = 2 * WGS84_F - WGS84_F ** 2  # Eccentricity squared


@dataclass(frozen=True)
class WGS84Coordinate:
    """
    A point on the WGS84 ellipsoid.

    Attributes:
        latitude: Degrees north (-90 to 90)
        longitude: Degrees east (-180 to 180)
        altitude: Height above ellipsoid in meters
    """
    latitude: float
    longitude: float
    altitude: float = 0.0

    def __post_init__(self):
        if not (-90 <= self.latitude <= 90):
            raise ValueError(f"Latitude out of range: {self.latitude}")
        if not (-180 <= self.longitude <= 180):
            raise ValueError(f"Longitude out of range: {self.longitude}")

    def to_dict(self) -> dict:
        return {"lat": self.latitude, "lon": self.longitude, "alt": self.altitude}

    @classmethod
    def from_dict(cls, d: dict) -> "WGS84Coordinate":
        return cls(
            latitude=d.get("lat", d.get("latitude", 0.0)),
            longitude=d.get("lon", d.get("longitude", 0.0)),
            altitude=d.get("alt", d.get("altitude", 0.0)),
        )


@dataclass(frozen=True)
class ENUVector:
    """
    A vector in the East/North/Up local coordinate frame.

    All values in meters.
    """
    east: float
    north: float
    up: float

    def to_list(self) -> list:
        return [self.east, self.north, self.up]

    def length(self) -> float:
        return math.sqrt(self.east ** 2 + self.north ** 2 + self.up ** 2)


@dataclass(frozen=True)
class GameCoordinate:
    """
    A position in the game world, relative to an origin.

    The origin is a WGS84Coordinate that defines (0, 0, 0) in game space.
    x = East, y = Up, z = North (Three.js convention: Y-up).
    """
    x: float
    y: float
    z: float

    def to_dict(self) -> dict:
        return {"x": self.x, "y": self.y, "z": self.z}


@dataclass(frozen=True)
class GeoTransform:
    """
    Defines the relationship between WGS84 and game coordinates.

    The origin is the WGS84 point that maps to game coordinate (0, 0, 0).
    """
    origin: WGS84Coordinate
    origin_ecef: tuple  # ECEF of origin, precomputed

    def wgs84_to_enu(self, coord: WGS84Coordinate) -> ENUVector:
        """Convert WGS84 coordinate to ENU relative to this origin."""
        ecef = _wgs84_to_ecef(coord)
        return _ecef_to_enu(ecef, self.origin_ecef, self.origin)

    def enu_to_game(self, enu: ENUVector) -> GameCoordinate:
        """Convert ENU to game coordinates (swap axes for Y-up)."""
        return GameCoordinate(x=enu.east, y=enu.up, z=enu.north)

    def wgs84_to_game(self, coord: WGS84Coordinate) -> GameCoordinate:
        """Convert WGS84 directly to game coordinates."""
        enu = self.wgs84_to_enu(coord)
        return self.enu_to_game(enu)

    def game_to_enu(self, game: GameCoordinate) -> ENUVector:
        """Convert game coordinates back to ENU."""
        return ENUVector(east=game.x, north=game.z, up=game.y)

    def enu_to_wgs84(self, enu: ENUVector) -> WGS84Coordinate:
        """Convert ENU back to WGS84."""
        # Approximate inverse for small distances
        d_lat = enu.north / _meters_per_degree_latitude(self.origin.latitude)
        d_lon = enu.east / _meters_per_degree_longitude(self.origin.latitude)
        return WGS84Coordinate(
            latitude=self.origin.latitude + d_lat,
            longitude=self.origin.longitude + d_lon,
            altitude=self.origin.altitude + enu.up,
        )

    def game_to_wgs84(self, game: GameCoordinate) -> WGS84Coordinate:
        """Convert game coordinates back to WGS84."""
        enu = self.game_to_enu(game)
        return self.enu_to_wgs84(enu)


def _wgs84_to_ecef(coord: WGS84Coordinate) -> tuple:
    """Convert WGS84 to Earth-Centered, Earth-Fixed (ECEF)."""
    lat_rad = math.radians(coord.latitude)
    lon_rad = math.radians(coord.longitude)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)

    N = WGS84_A / math.sqrt(1 - WGS84_E2 * sin_lat ** 2)

    x = (N + coord.altitude) * cos_lat * cos_lon
    y = (N + coord.altitude) * cos_lat * sin_lon
    z = (N * (1 - WGS84_E2) + coord.altitude) * sin_lat

    return (x, y, z)


def _ecef_to_enu(ecef: tuple, origin_ecef: tuple, origin: WGS84Coordinate) -> ENUVector:
    """Convert ECEF to ENU relative to an origin."""
    dx = ecef[0] - origin_ecef[0]
    dy = ecef[1] - origin_ecef[1]
    dz = ecef[2] - origin_ecef[2]

    lat_rad = math.radians(origin.latitude)
    lon_rad = math.radians(origin.longitude)

    sin_lat = math.sin(lat_rad)
    cos_lat = math.cos(lat_rad)
    sin_lon = math.sin(lon_rad)
    cos_lon = math.cos(lon_rad)

    east = -sin_lon * dx + cos_lon * dy
    north = -sin_lat * cos_lon * dx - sin_lat * sin_lon * dy + cos_lat * dz
    up = cos_lat * cos_lon * dx + cos_lat * sin_lon * dy + sin_lat * dz

    return ENUVector(east=east, north=north, up=up)


def _meters_per_degree_latitude(lat: float) -> float:
    """Approximate meters per degree of latitude at a given latitude."""
    lat_rad = math.radians(lat)
    return 111132.92 - 559.82 * math.cos(2 * lat_rad) + 1.175 * math.cos(4 * lat_rad)


def _meters_per_degree_longitude(lat: float) -> float:
    """Approximate meters per degree of longitude at a given latitude."""
    lat_rad = math.radians(lat)
    return 111412.84 * math.cos(lat_rad) - 93.5 * math.cos(3 * lat_rad)


def create_transform(origin: WGS84Coordinate) -> GeoTransform:
    """Create a GeoTransform with the given WGS84 origin."""
    origin_ecef = _wgs84_to_ecef(origin)
    return GeoTransform(origin=origin, origin_ecef=origin_ecef)


def haversine_distance(a: WGS84Coordinate, b: WGS84Coordinate) -> float:
    """
    Calculate the great-circle distance between two WGS84 points.
    Returns distance in meters.
    """
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlat = math.radians(b.latitude - a.latitude)
    dlon = math.radians(b.longitude - a.longitude)

    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))

    return WGS84_A * c


def bearing(a: WGS84Coordinate, b: WGS84Coordinate) -> float:
    """
    Calculate the initial bearing from point a to point b.
    Returns bearing in degrees (0-360, clockwise from north).
    """
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlon = math.radians(b.longitude - a.longitude)

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

    return (math.degrees(math.atan2(y, x)) + 360) % 360


def bounding_box(center: WGS84Coordinate, radius_meters: float) -> tuple:
    """
    Calculate a bounding box around a center point.
    Returns (min_lat, max_lat, min_lon, max_lon).
    """
    dlat = radius_meters / _meters_per_degree_latitude(center.latitude)
    dlon = radius_meters / _meters_per_degree_longitude(center.latitude)

    return (
        center.latitude - dlat,
        center.latitude + dlat,
        center.longitude - dlon,
        center.longitude + dlon,
    )
