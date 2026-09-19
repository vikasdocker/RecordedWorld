"""
Base Map Provider Abstraction

Provides a unified interface for fetching map data from different providers.
Supports OpenStreetMap, Mapbox, and custom tile servers.
"""
import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class MapProviderType(Enum):
    OPENSTREETMAP = "openstreetmap"
    MAPBOX = "mapbox"
    CUSTOM = "custom"


@dataclass
class MapTile:
    """A geographic tile containing map data."""
    zoom: int
    x: int
    y: int
    data: Dict[str, Any] = field(default_factory=dict)
    provider: str = "openstreetmap"
    format: str = "json"


@dataclass
class GeoBounds:
    """Geographic bounding box."""
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float

    def contains(self, lat: float, lon: float) -> bool:
        return (self.min_lat <= lat <= self.max_lat and
                self.min_lon <= lon <= self.max_lon)

    def overlaps(self, other: "GeoBounds") -> bool:
        return not (self.max_lat < other.min_lat or
                    self.min_lat > other.max_lat or
                    self.max_lon < other.min_lon or
                    self.min_lon > other.max_lon)


@dataclass
class TileCoords:
    """Tile coordinates at a given zoom level."""
    zoom: int
    x: int
    y: int

    @classmethod
    def from_lat_lon(cls, lat: float, lon: float, zoom: int) -> "TileCoords":
        """Convert lat/lon to tile coordinates."""
        n = 2 ** zoom
        x = int((lon + 180.0) / 360.0 * n)
        lat_rad = math.radians(lat)
        y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return cls(zoom=zoom, x=x, y=y)

    def to_lat_lon_bounds(self) -> GeoBounds:
        """Convert tile coordinates to lat/lon bounds."""
        n = 2 ** self.zoom
        lon_min = self.x / n * 360.0 - 180.0
        lon_max = (self.x + 1) / n * 360.0 - 180.0
        lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * self.y / n))))
        lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (self.y + 1) / n))))
        return GeoBounds(min_lat=lat_min, min_lon=lon_min,
                         max_lat=lat_max, max_lon=lon_max)


class MapProvider(ABC):
    """Abstract base class for map data providers."""

    @property
    @abstractmethod
    def provider_type(self) -> MapProviderType:
        pass

    @abstractmethod
    def get_tile(self, coords: TileCoords) -> MapTile:
        """Fetch a single tile."""
        pass

    @abstractmethod
    def get_tiles_in_bounds(self, bounds: GeoBounds, zoom: int) -> List[MapTile]:
        """Fetch all tiles within a geographic bounds."""
        pass

    @abstractmethod
    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        """Get elevation at a point."""
        pass

    @abstractmethod
    def get_building_footprints(self, bounds: GeoBounds) -> List[Dict[str, Any]]:
        """Get building footprints within bounds."""
        pass

    @abstractmethod
    def get_road_network(self, bounds: GeoBounds) -> List[Dict[str, Any]]:
        """Get road network within bounds."""
        pass


class OpenStreetMapProvider(MapProvider):
    """OpenStreetMap-based map provider using Overpass API."""

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    @property
    def provider_type(self) -> MapProviderType:
        return MapProviderType.OPENSTREETMAP

    def get_tile(self, coords: TileCoords) -> MapTile:
        bounds = coords.to_lat_lon_bounds()
        return MapTile(
            zoom=coords.zoom,
            x=coords.x,
            y=coords.y,
            data={"bounds": bounds.__dict__},
            provider="openstreetmap",
        )

    def get_tiles_in_bounds(self, bounds: GeoBounds, zoom: int) -> List[MapTile]:
        tiles = []
        min_tile = TileCoords.from_lat_lon(bounds.max_lat, bounds.min_lon, zoom)
        max_tile = TileCoords.from_lat_lon(bounds.min_lat, bounds.max_lon, zoom)

        for x in range(min_tile.x, max_tile.x + 1):
            for y in range(min_tile.y, max_tile.y + 1):
                tiles.append(self.get_tile(TileCoords(zoom=zoom, x=x, y=y)))
        return tiles

    def get_elevation(self, lat: float, lon: float) -> Optional[float]:
        # Production: query Open-Elevation or SRTM data
        return 0.0

    def get_building_footprints(self, bounds: GeoBounds) -> List[Dict[str, Any]]:
        # Production: query Overpass API for building ways
        return []

    def get_road_network(self, bounds: GeoBounds) -> List[Dict[str, Any]]:
        # Production: query Overpass API for highway ways
        return []


class MapProviderFactory:
    """Factory for creating map providers."""

    _providers: Dict[MapProviderType, type] = {
        MapProviderType.OPENSTREETMAP: OpenStreetMapProvider,
    }

    @classmethod
    def register(cls, provider_type: MapProviderType, provider_class: type):
        cls._providers[provider_type] = provider_class

    @classmethod
    def create(cls, provider_type: MapProviderType = MapProviderType.OPENSTREETMAP,
               **kwargs) -> MapProvider:
        if provider_type not in cls._providers:
            raise ValueError(f"Unknown provider: {provider_type}")
        return cls._providers[provider_type](**kwargs)


# Module-level singleton
map_provider = MapProviderFactory.create()
