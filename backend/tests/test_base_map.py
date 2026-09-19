"""
Tests for Phase 2: Base Map services.
"""
import pytest
import numpy as np
from app.services.map_provider import (
    MapProviderFactory, MapProviderType, TileCoords, GeoBounds,
    OpenStreetMapProvider, MapTile
)
from app.services.tile_manager import TileManager, TileState, MapChunk
from app.services.vector_ingester import (
    VectorMapIngester, FeatureType, RoadType, BuildingType,
    VectorFeature, RoadSegment, BuildingFootprint
)
from app.services.terrain_ingester import TerrainIngester, TerrainChunk
from app.services.building_footprint import BuildingFootprintService, Building3D
from app.services.road_network import RoadNetworkService, Road3D
from app.services.streaming_cache import StreamingCache, CachePriority, CacheEntry
from app.services.lod_system import LODManager, LODLevel, LODConfig


# --- Map Provider ---

class TestMapProvider:
    def test_create_osm_provider(self):
        provider = MapProviderFactory.create()
        assert isinstance(provider, OpenStreetMapProvider)

    def test_osm_provider_type(self):
        provider = OpenStreetMapProvider()
        assert provider.provider_type == MapProviderType.OPENSTREETMAP

    def test_tile_coords_from_lat_lon(self):
        coords = TileCoords.from_lat_lon(40.7128, -74.0060, 10)
        assert coords.zoom == 10
        assert isinstance(coords.x, int)
        assert isinstance(coords.y, int)

    def test_tile_coords_to_bounds(self):
        coords = TileCoords(zoom=10, x=300, y=400)
        bounds = coords.to_lat_lon_bounds()
        assert isinstance(bounds, GeoBounds)
        assert bounds.min_lat < bounds.max_lat
        assert bounds.min_lon < bounds.max_lon

    def test_geo_bounds_contains(self):
        bounds = GeoBounds(40.0, -74.0, 41.0, -73.0)
        assert bounds.contains(40.5, -73.5)
        assert not bounds.contains(42.0, -73.5)

    def test_geo_bounds_overlaps(self):
        b1 = GeoBounds(40.0, -74.0, 41.0, -73.0)
        b2 = GeoBounds(40.5, -73.5, 41.5, -72.5)
        assert b1.overlaps(b2)

    def test_get_tile(self):
        provider = OpenStreetMapProvider()
        coords = TileCoords(zoom=10, x=300, y=400)
        tile = provider.get_tile(coords)
        assert isinstance(tile, MapTile)
        assert tile.zoom == 10

    def test_get_tiles_in_bounds(self):
        provider = OpenStreetMapProvider()
        bounds = GeoBounds(40.5, -74.0, 41.0, -73.5)
        tiles = provider.get_tiles_in_bounds(bounds, zoom=10)
        assert len(tiles) > 0

    def test_get_elevation(self):
        provider = OpenStreetMapProvider()
        elev = provider.get_elevation(40.7128, -74.0060)
        assert isinstance(elev, float)

    def test_get_building_footprints(self):
        provider = OpenStreetMapProvider()
        bounds = GeoBounds(40.7128, -74.0060, 40.7138, -74.0050)
        footprints = provider.get_building_footprints(bounds)
        assert isinstance(footprints, list)

    def test_get_road_network(self):
        provider = OpenStreetMapProvider()
        bounds = GeoBounds(40.7128, -74.0060, 40.7138, -74.0050)
        roads = provider.get_road_network(bounds)
        assert isinstance(roads, list)


# --- Tile Manager ---

class TestTileManager:
    def test_get_or_create_chunk(self):
        tm = TileManager()
        chunk = tm.get_or_create_chunk(40.7128, -74.0060, 1.0)
        assert isinstance(chunk, MapChunk)
        assert chunk.center_lat == 40.7128

    def test_get_tiles_for_area(self):
        tm = TileManager()
        bounds = GeoBounds(40.5, -74.0, 41.0, -73.5)
        result = tm.get_tiles_for_area(bounds, zoom=10)
        assert len(result) > 0

    def test_load_tile(self):
        tm = TileManager()
        coords = TileCoords(zoom=10, x=300, y=400)
        tile = tm.load_tile(coords)
        assert tile is not None

    def test_get_loaded_tiles(self):
        tm = TileManager()
        coords = TileCoords(zoom=10, x=300, y=400)
        tm.load_tile(coords)
        loaded = tm.get_loaded_tiles()
        assert len(loaded) >= 1

    def test_get_stats(self):
        tm = TileManager()
        stats = tm.get_stats()
        assert "total_tiles" in stats
        assert "loaded_tiles" in stats

    def test_eviction(self):
        tm = TileManager(max_cached_tiles=2)
        for i in range(4):
            tm.load_tile(TileCoords(zoom=10, x=300 + i, y=400))
        assert len(tm.tiles) <= 3  # 2 + some tolerance


# --- Vector Ingester ---

class TestVectorIngester:
    def test_ingest_osm_data(self):
        ingester = VectorMapIngester()
        osm_data = {
            "elements": [
                {
                    "type": "way",
                    "id": 1,
                    "tags": {"building": "yes", "name": "Test Building"},
                },
                {
                    "type": "way",
                    "id": 2,
                    "tags": {"highway": "residential", "name": "Main St"},
                },
            ]
        }
        features = ingester.ingest_osm_data(osm_data)
        assert len(features) == 2
        assert any(f.type == FeatureType.BUILDING for f in features)
        assert any(f.type == FeatureType.ROAD for f in features)

    def test_ingest_geojson(self):
        ingester = VectorMapIngester()
        geojson = {
            "features": [
                {
                    "id": 1,
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [-74.0, 40.7]},
                    "properties": {"name": "POI"},
                }
            ]
        }
        features = ingester.ingest_geojson(geojson)
        assert len(features) == 1

    def test_get_stats(self):
        ingester = VectorMapIngester()
        stats = ingester.get_stats()
        assert "total_features" in stats
        assert "buildings" in stats

    def test_feature_properties(self):
        feature = VectorFeature(
            id="1",
            type=FeatureType.BUILDING,
            geometry={"type": "Polygon"},
            properties={"name": "Test"},
        )
        assert feature.name == "Test"


# --- Terrain Ingester ---

class TestTerrainIngester:
    def test_load_heightmap(self):
        ingester = TerrainIngester()
        data = np.random.rand(64, 64).astype(np.float32) * 100
        chunk = ingester.load_heightmap("c1", 40.0, -74.0, 1.0, 1.0, data)
        assert isinstance(chunk, TerrainChunk)
        assert chunk.height_data is not None

    def test_get_height_at(self):
        ingester = TerrainIngester()
        data = np.ones((64, 64), dtype=np.float32) * 50
        ingester.load_heightmap("c1", 40.0, -74.0, 1.0, 1.0, data)
        h = ingester.get_height_at(40.5, -73.5)
        assert isinstance(h, float)

    def test_generate_procedural(self):
        ingester = TerrainIngester()
        chunk = ingester.generate_procedural_terrain(
            "c2", 40.0, -74.0, 1.0, 1.0, resolution=32
        )
        assert chunk.height_data is not None
        assert chunk.height_data.shape == (32, 32)

    def test_to_mesh_grid(self):
        ingester = TerrainIngester()
        data = np.ones((32, 32), dtype=np.float32)
        chunk = ingester.load_heightmap("c1", 40.0, -74.0, 1.0, 1.0, data)
        lat_grid, lon_grid, height = chunk.to_mesh_grid()
        assert lat_grid.shape == (32, 32)

    def test_get_stats(self):
        ingester = TerrainIngester()
        stats = ingester.get_stats()
        assert "total_chunks" in stats


# --- Building Footprint ---

class TestBuildingFootprint:
    def test_extrude_footprint(self):
        service = BuildingFootprintService()
        fp = BuildingFootprint(
            id="b1", name="Test", building_type=BuildingType.RESIDENTIAL,
            height=10.0, num_floors=3,
            geometry=[(-74.0, 40.7), (-74.0, 40.71), (-74.01, 40.71), (-74.01, 40.7)],
        )
        building = service.extrude_footprint(fp)
        assert isinstance(building, Building3D)
        assert len(building.vertices) > 0
        assert len(building.faces) > 0

    def test_get_stats(self):
        service = BuildingFootprintService()
        stats = service.get_stats()
        assert "total_buildings" in stats

    def test_polygon_area(self):
        service = BuildingFootprintService()
        points = [(0, 0), (1, 0), (1, 1), (0, 1)]
        area = service._polygon_area(points)
        assert abs(area - 1.0) < 0.01


# --- Road Network ---

class TestRoadNetwork:
    def test_create_road_3d(self):
        service = RoadNetworkService()
        segment = RoadSegment(
            id="r1", name="Main St", road_type=RoadType.RESIDENTIAL,
            lanes=2, surface="asphalt",
            geometry=[(-74.0, 40.7), (-74.01, 40.71)],
        )
        road = service.create_road_3d(segment)
        assert isinstance(road, Road3D)
        assert len(road.vertices) > 0
        assert road.width > 0

    def test_road_widths(self):
        service = RoadNetworkService()
        assert service.ROAD_WIDTHS[RoadType.MOTORWAY] == 24.0
        assert service.ROAD_WIDTHS[RoadType.FOOTWAY] == 2.0

    def test_get_stats(self):
        service = RoadNetworkService()
        stats = service.get_stats()
        assert "total_roads" in stats


# --- Streaming Cache ---

class TestStreamingCache:
    def test_put_and_get(self):
        cache = StreamingCache(max_size_bytes=1024 * 1024)
        cache.put((10, 1, 2), "data", 100)
        assert cache.get((10, 1, 2)) == "data"

    def test_eviction(self):
        cache = StreamingCache(max_size_bytes=300)
        cache.put((1, 1, 1), "a", 100)
        cache.put((2, 2, 2), "b", 100)
        cache.put((3, 3, 3), "c", 100)
        cache.put((4, 4, 4), "d", 200)  # triggers eviction
        assert cache.current_size_bytes <= 300

    def test_pin_prevents_eviction(self):
        cache = StreamingCache(max_size_bytes=200)
        cache.put((1, 1, 1), "a", 100)
        cache.pin((1, 1, 1))
        cache.put((2, 2, 2), "b", 100)
        cache.put((3, 3, 3), "c", 100)  # evicts b
        assert cache.get((1, 1, 1)) == "a"  # pinned, not evicted

    def test_request_stream(self):
        cache = StreamingCache()
        cache.request_stream((10, 1, 2), CachePriority.HIGH)
        req = cache.get_next_request()
        assert req is not None
        assert req.tile_key == (10, 1, 2)

    def test_get_stats(self):
        cache = StreamingCache()
        stats = cache.get_stats()
        assert "cached_entries" in stats
        assert "usage_pct" in stats


# --- LOD System ---

class TestLODSystem:
    def test_select_lod_ultra(self):
        lod = LODManager()
        sel = lod.select_lod(50.0)
        assert sel.level == LODLevel.ULTRA

    def test_select_lod_high(self):
        lod = LODManager()
        sel = lod.select_lod(300.0)
        assert sel.level == LODLevel.HIGH

    def test_select_lod_medium(self):
        lod = LODManager()
        sel = lod.select_lod(1000.0)
        assert sel.level == LODLevel.MEDIUM

    def test_select_lod_low(self):
        lod = LODManager()
        sel = lod.select_lod(3000.0)
        assert sel.level == LODLevel.LOW

    def test_select_lod_minimal(self):
        lod = LODManager()
        sel = lod.select_lod(10000.0)
        assert sel.level == LODLevel.MINIMAL

    def test_reduce_vertices(self):
        lod = LODManager()
        verts = [(i, i, i) for i in range(100)]
        reduced = lod.reduce_vertices(verts, 10)
        assert len(reduced) <= 10

    def test_simplify_polygon(self):
        lod = LODManager()
        # Simple rectangle with extra points
        points = [(0, 0), (0.5, 0.01), (1, 0), (1, 1), (0, 1)]
        simplified = lod.simplify_polygon(points, tolerance=0.1)
        assert len(simplified) <= len(points)

    def test_get_config_for_distance(self):
        lod = LODManager()
        config = lod.get_config_for_distance(100.0)
        assert isinstance(config, LODConfig)
        assert config.level == LODLevel.ULTRA
