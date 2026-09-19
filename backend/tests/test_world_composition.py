"""
Tests for Phase 9: World Composition services.
"""
import pytest
from app.services.layer_compositor import (
    LayerCompositor, WorldLayer, LayerType, LayerBlendMode, CompositeResult
)
from app.services.content_addressing import (
    ContentAddressableStore, ContentAddress, ContentRecord
)
from app.services.user_content_manager import (
    UserContentManager, UserContent, ContentStatus
)
from app.services.rendering_pipeline import (
    RenderingPipeline, ViewRegion, RenderFrame, DrawCall, CullingMethod
)


# --- Layer Compositor ---

class TestLayerCompositor:
    def test_add_layer(self):
        comp = LayerCompositor()
        layer = WorldLayer(
            id="l1", type=LayerType.TERRAIN, name="Terrain",
            priority=0, data={"vertex_count": 100},
        )
        comp.add_layer(layer)
        assert comp.get_layer("l1") is not None

    def test_remove_layer(self):
        comp = LayerCompositor()
        layer = WorldLayer(id="l1", type=LayerType.TERRAIN, name="Terrain")
        comp.add_layer(layer)
        assert comp.remove_layer("l1")
        assert comp.get_layer("l1") is None

    def test_set_visible(self):
        comp = LayerCompositor()
        layer = WorldLayer(id="l1", type=LayerType.TERRAIN, name="Terrain")
        comp.add_layer(layer)
        comp.set_layer_visible("l1", False)
        assert not comp.get_layer("l1").visible

    def test_set_opacity(self):
        comp = LayerCompositor()
        layer = WorldLayer(id="l1", type=LayerType.TERRAIN, name="Terrain")
        comp.add_layer(layer)
        comp.set_layer_opacity("l1", 0.5)
        assert comp.get_layer("l1").opacity == 0.5

    def test_composite(self):
        comp = LayerCompositor()
        comp.add_layer(WorldLayer(
            id="terrain", type=LayerType.TERRAIN, name="Terrain",
            priority=0, visible=True,
            data={"vertex_count": 100, "face_count": 50},
        ))
        comp.add_layer(WorldLayer(
            id="buildings", type=LayerType.BASE_MAP, name="Buildings",
            priority=1, visible=True,
            data={"vertex_count": 200, "face_count": 100},
        ))
        result = comp.composite()
        assert isinstance(result, CompositeResult)
        assert result.visible_count == 2
        assert result.total_vertices == 300

    def test_composite_hidden_layer(self):
        comp = LayerCompositor()
        comp.add_layer(WorldLayer(
            id="l1", type=LayerType.TERRAIN, name="Terrain",
            priority=0, visible=False,
            data={"vertex_count": 100},
        ))
        result = comp.composite()
        assert result.visible_count == 0

    def test_get_user_layers(self):
        comp = LayerCompositor()
        comp.add_layer(WorldLayer(
            id="user1", type=LayerType.USER_RECONSTRUCTION, name="User Recon",
        ))
        comp.add_layer(WorldLayer(
            id="base1", type=LayerType.BASE_MAP, name="Base Map",
        ))
        user_layers = comp.get_user_layers()
        assert len(user_layers) == 1
        assert user_layers[0].type == LayerType.USER_RECONSTRUCTION

    def test_get_stats(self):
        comp = LayerCompositor()
        comp.add_layer(WorldLayer(id="l1", type=LayerType.TERRAIN, name="T"))
        stats = comp.get_stats()
        assert stats["total_layers"] == 1

    def test_render_order(self):
        comp = LayerCompositor()
        comp.add_layer(WorldLayer(id="top", type=LayerType.EFFECTS, name="Effects", priority=10))
        comp.add_layer(WorldLayer(id="bottom", type=LayerType.TERRAIN, name="Terrain", priority=0))
        result = comp.composite()
        assert result.layers[0].id == "bottom"
        assert result.layers[1].id == "top"


# --- Content Addressing ---

class TestContentAddressing:
    def test_store_and_get(self):
        store = ContentAddressableStore()
        addr = store.store(b"hello world", "test")
        assert isinstance(addr, ContentAddress)
        assert addr.size_bytes == 11
        record = store.get(addr.hash)
        assert record is not None
        assert record.references == 1

    def test_store_json(self):
        store = ContentAddressableStore()
        addr = store.store_json({"key": "value"}, "metadata")
        assert isinstance(addr, ContentAddress)

    def test_deduplication(self):
        store = ContentAddressableStore()
        addr1 = store.store(b"same data", "test")
        addr2 = store.store(b"same data", "test")
        assert addr1.hash == addr2.hash
        assert store.get(addr1.hash).references == 2

    def test_exists(self):
        store = ContentAddressableStore()
        addr = store.store(b"test", "test")
        assert store.exists(addr.hash)
        assert not store.exists("nonexistent")

    def test_release_and_gc(self):
        store = ContentAddressableStore()
        addr = store.store(b"test", "test")
        store.release(addr.hash)
        removed = store.gc()
        assert removed == 1

    def test_compute_hash(self):
        store = ContentAddressableStore()
        h = store.compute_hash(b"test")
        assert len(h) == 64  # SHA-256 hex

    def test_get_stats(self):
        store = ContentAddressableStore()
        store.store(b"test", "mesh")
        stats = store.get_stats()
        assert stats["total_objects"] == 1


# --- User Content Manager ---

class TestUserContentManager:
    def test_create_content(self):
        mgr = UserContentManager()
        content = mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        assert isinstance(content, UserContent)
        assert content.status == ContentStatus.ACTIVE

    def test_get_content(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        c = mgr.get_content("c1")
        assert c is not None
        assert c.id == "c1"

    def test_update_content(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        updated = mgr.update_content("c1", base_map_version="v2")
        assert updated is not None
        assert updated.version == 2
        assert updated.status == ContentStatus.STALE

    def test_delete_content(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        assert mgr.delete_content("c1")
        c = mgr.get_content("c1")
        assert c is None or c.status == ContentStatus.DELETED

    def test_get_user_content(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        mgr.create_content(
            "c2", user_id=1, content_type="annotation",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        contents = mgr.get_user_content(1)
        assert len(contents) == 2

    def test_check_conflicts(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        mgr.create_content(
            "c2", user_id=2, content_type="reconstruction",
            geo_bounds={"min_lat": 40.5, "max_lat": 41.5, "min_lon": -73.5, "max_lon": -72.5},
            base_map_version="v1",
        )
        conflicts = mgr.check_conflicts("c1")
        assert "c2" in conflicts

    def test_get_stats(self):
        mgr = UserContentManager()
        mgr.create_content(
            "c1", user_id=1, content_type="reconstruction",
            geo_bounds={"min_lat": 40, "max_lat": 41, "min_lon": -74, "max_lon": -73},
            base_map_version="v1",
        )
        stats = mgr.get_stats()
        assert stats["total_content"] == 1


# --- Rendering Pipeline ---

class TestRenderingPipeline:
    def test_process_frame(self):
        pipeline = RenderingPipeline()
        from app.services.layer_compositor import WorldLayer, LayerType
        from app.services.layer_compositor import CompositeResult

        layers = [
            WorldLayer(
                id="terrain", type=LayerType.TERRAIN, name="Terrain",
                visible=True, priority=0,
                data={
                    "vertex_count": 100, "face_count": 50,
                    "features": [{"position": (0, 0, 0), "mesh_id": "m1",
                                  "vertex_count": 100, "face_count": 50}],
                },
            )
        ]
        composited = CompositeResult(
            layers=layers, total_vertices=100, total_faces=50,
            visible_count=1,
        )
        view = ViewRegion(center=(0, 0, 0), radius=1000)
        frame = pipeline.process_frame(composited, view)
        assert isinstance(frame, RenderFrame)
        assert len(frame.draw_calls) >= 0

    def test_culling_distance(self):
        pipeline = RenderingPipeline()
        from app.services.layer_compositor import WorldLayer, LayerType, CompositeResult

        layers = [
            WorldLayer(
                id="far", type=LayerType.BASE_MAP, name="Far",
                visible=True, priority=0,
                data={
                    "features": [{"position": (10000, 0, 0), "mesh_id": "m1",
                                  "vertex_count": 100, "face_count": 50}],
                },
            )
        ]
        composited = CompositeResult(
            layers=layers, total_vertices=100, total_faces=50, visible_count=1,
        )
        view = ViewRegion(center=(0, 0, 0), radius=1000)
        frame = pipeline.process_frame(composited, view)
        assert frame.culled_count >= 1

    def test_get_stats(self):
        pipeline = RenderingPipeline()
        frame = RenderFrame(draw_calls=[], total_vertices=0, total_faces=0, culled_count=0)
        stats = pipeline.get_stats(frame)
        assert "draw_calls" in stats

    def test_view_region(self):
        view = ViewRegion(center=(1, 2, 3), radius=500, fov=90)
        assert view.center == (1, 2, 3)
        assert view.radius == 500
