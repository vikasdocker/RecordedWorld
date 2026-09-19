"""
Vector Map Ingestion

Parses OpenStreetMap data into game-ready vector features:
  - Building footprints (polygons)
  - Road segments (lines)
  - Land use areas (polygons)
  - Water features (polygons)
  - POI points
"""
import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class FeatureType(Enum):
    BUILDING = "building"
    ROAD = "road"
    LAND_USE = "land_use"
    WATER = "water"
    POI = "poi"
    BOUNDARY = "boundary"


class RoadType(Enum):
    MOTORWAY = "motorway"
    TRUNK = "trunk"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    RESIDENTIAL = "residential"
    SERVICE = "service"
    FOOTWAY = "footway"


class BuildingType(Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    PUBLIC = "public"
    UNKNOWN = "unknown"


@dataclass
class VectorFeature:
    """A single vector feature from map data."""
    id: str
    type: FeatureType
    geometry: Dict[str, Any]  # GeoJSON-like geometry
    properties: Dict[str, Any] = field(default_factory=dict)
    bounds: Optional[Dict[str, float]] = None  # bbox

    @property
    def name(self) -> Optional[str]:
        return self.properties.get("name")

    @property
    def height(self) -> Optional[float]:
        return self.properties.get("height")

    @property
    def num_floors(self) -> Optional[int]:
        return self.properties.get("building:levels")


@dataclass
class RoadSegment:
    """A road segment with geometry and metadata."""
    id: str
    name: Optional[str]
    road_type: RoadType
    lanes: int
    surface: Optional[str]
    geometry: List[Tuple[float, float]]  # list of (lon, lat)
    oneway: bool = False
    max_speed: Optional[int] = None


@dataclass
class BuildingFootprint:
    """A building footprint polygon."""
    id: str
    name: Optional[str]
    building_type: BuildingType
    height: Optional[float]
    num_floors: Optional[int]
    geometry: List[Tuple[float, float]]  # polygon vertices (lon, lat)


class VectorMapIngester:
    """Ingests and parses vector map data from various sources."""

    def __init__(self):
        self.features: List[VectorFeature] = []
        self.buildings: List[BuildingFootprint] = []
        self.roads: List[RoadSegment] = []

    def ingest_osm_data(self, osm_data: Dict[str, Any]) -> List[VectorFeature]:
        """Parse OpenStreetMap JSON data into VectorFeatures."""
        features = []

        elements = osm_data.get("elements", [])
        for element in elements:
            feature = self._parse_osm_element(element)
            if feature:
                features.append(feature)
                self.features.append(feature)

        return features

    def ingest_geojson(self, geojson: Dict[str, Any]) -> List[VectorFeature]:
        """Parse GeoJSON data into VectorFeatures."""
        features = []
        for feature_data in geojson.get("features", []):
            feature = VectorFeature(
                id=str(feature_data.get("id", len(features))),
                type=self._classify_feature(feature_data),
                geometry=feature_data.get("geometry", {}),
                properties=feature_data.get("properties", {}),
            )
            features.append(feature)
            self.features.append(feature)
        return features

    def _parse_osm_element(self, element: Dict[str, Any]) -> Optional[VectorFeature]:
        elem_type = element.get("type")
        tags = element.get("tags", {})

        if elem_type == "way":
            return self._parse_osm_way(element, tags)
        elif elem_type == "node":
            return self._parse_osm_node(element, tags)
        return None

    def _parse_osm_way(self, element: Dict, tags: Dict) -> Optional[VectorFeature]:
        elem_id = str(element.get("id", ""))
        geometry = {"type": "LineString", "coordinates": []}

        if tags.get("building"):
            geometry["type"] = "Polygon"
            self.buildings.append(self._create_building_footprint(elem_id, tags))
            feature_type = FeatureType.BUILDING
        elif tags.get("highway"):
            self.roads.append(self._create_road_segment(elem_id, tags))
            feature_type = FeatureType.ROAD
        elif tags.get("natural") == "water":
            feature_type = FeatureType.WATER
        elif tags.get("landuse"):
            feature_type = FeatureType.LAND_USE
        else:
            return None

        return VectorFeature(
            id=elem_id,
            type=feature_type,
            geometry=geometry,
            properties=tags,
        )

    def _parse_osm_node(self, element: Dict, tags: Dict) -> Optional[VectorFeature]:
        if not tags:
            return None

        lon = element.get("lon", 0)
        lat = element.get("lat", 0)
        geometry = {
            "type": "Point",
            "coordinates": [lon, lat],
        }

        return VectorFeature(
            id=str(element.get("id", "")),
            type=FeatureType.POI,
            geometry=geometry,
            properties=tags,
        )

    def _create_building_footprint(self, elem_id: str, tags: Dict) -> BuildingFootprint:
        height = None
        if "height" in tags:
            try:
                height = float(tags["height"].replace("m", "").strip())
            except (ValueError, AttributeError):
                pass

        num_floors = None
        if "building:levels" in tags:
            try:
                num_floors = int(tags["building:levels"])
            except (ValueError, TypeError):
                pass

        building_type = BuildingType.UNKNOWN
        btype = tags.get("building", "")
        if isinstance(btype, str):
            btype_lower = btype.lower()
            if "residential" in btype_lower or btype_lower == "yes":
                building_type = BuildingType.RESIDENTIAL
            elif "commercial" in btype_lower:
                building_type = BuildingType.COMMERCIAL
            elif "industrial" in btype_lower:
                building_type = BuildingType.INDUSTRIAL
            elif "public" in btype_lower or "civic" in btype_lower:
                building_type = BuildingType.PUBLIC

        return BuildingFootprint(
            id=elem_id,
            name=tags.get("name"),
            building_type=building_type,
            height=height,
            num_floors=num_floors,
            geometry=[],
        )

    def _create_road_segment(self, elem_id: str, tags: Dict) -> RoadSegment:
        road_type_map = {
            "motorway": RoadType.MOTORWAY,
            "trunk": RoadType.TRUNK,
            "primary": RoadType.PRIMARY,
            "secondary": RoadType.SECONDARY,
            "tertiary": RoadType.TERTIARY,
            "residential": RoadType.RESIDENTIAL,
            "service": RoadType.SERVICE,
            "footway": RoadType.FOOTWAY,
        }

        highway = tags.get("highway", "residential")
        road_type = road_type_map.get(highway, RoadType.RESIDENTIAL)

        lanes = 2
        if "lanes" in tags:
            try:
                lanes = int(tags["lanes"])
            except (ValueError, TypeError):
                pass

        return RoadSegment(
            id=elem_id,
            name=tags.get("name"),
            road_type=road_type,
            lanes=lanes,
            surface=tags.get("surface"),
            geometry=[],
            oneway=tags.get("oneway") == "yes",
        )

    def _classify_feature(self, feature_data: Dict) -> FeatureType:
        props = feature_data.get("properties", {})
        geom_type = feature_data.get("geometry", {}).get("type", "")

        if "building" in props:
            return FeatureType.BUILDING
        if "highway" in props:
            return FeatureType.ROAD
        if geom_type == "Point":
            return FeatureType.POI
        return FeatureType.LAND_USE

    def get_features_in_bounds(
        self, min_lat: float, min_lon: float, max_lat: float, max_lon: float
    ) -> List[VectorFeature]:
        result = []
        for feature in self.features:
            if feature.bounds:
                fb = feature.bounds
                if (fb.get("min_lat", 0) <= max_lat and
                    fb.get("max_lat", 0) >= min_lat and
                    fb.get("min_lon", 0) <= max_lon and
                    fb.get("max_lon", 0) >= min_lon):
                    result.append(feature)
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_features": len(self.features),
            "buildings": len(self.buildings),
            "roads": len(self.roads),
            "by_type": {
                t.value: sum(1 for f in self.features if f.type == t)
                for t in FeatureType
            },
        }


# Module-level singleton
vector_ingester = VectorMapIngester()
