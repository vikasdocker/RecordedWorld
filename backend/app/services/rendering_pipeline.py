"""
Rendering Pipeline Service

Manages the mixed-content rendering pipeline for the world.
Handles layer ordering, culling, batching, and draw call generation.
"""
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

from app.services.layer_compositor import WorldLayer, LayerType, CompositeResult
from app.services.lod_system import LODManager, LODLevel, LODSelection


class CullingMethod(Enum):
    FRUSTUM = "frustum"
    DISTANCE = "distance"
    OCCLUSION = "occlusion"


class RenderBatchType(Enum):
    STATIC_MESH = "static_mesh"
    DYNAMIC_MESH = "dynamic_mesh"
    TERRAIN = "terrain"
    PARTICLES = "particles"


@dataclass
class DrawCall:
    """A single draw call for the GPU."""
    batch_type: RenderBatchType
    mesh_id: str
    material_id: str
    transform: List[float]  # 4x4 matrix as flat list
    layer_id: str
    lod_level: int
    vertex_count: int
    face_count: int


@dataclass
class RenderFrame:
    """A complete render frame with all draw calls."""
    draw_calls: List[DrawCall]
    total_vertices: int
    total_faces: int
    culled_count: int
    camera_position: Tuple[float, float, float] = (0, 0, 0)
    camera_frustum: Optional[Dict[str, float]] = None


@dataclass
class ViewRegion:
    """The visible region from the camera."""
    center: Tuple[float, float, float]  # x, y, z in world coords
    radius: float  # view distance
    fov: float = 60.0  # degrees


class RenderingPipeline:
    """Manages the rendering pipeline for mixed content."""

    def __init__(self):
        self.lod_manager = LODManager()
        self.max_draw_calls = 1000
        self.max_vertices_per_frame = 500000

    def process_frame(
        self,
        composited: CompositeResult,
        view: ViewRegion,
        culling: CullingMethod = CullingMethod.DISTANCE,
    ) -> RenderFrame:
        draw_calls = []
        culled = 0
        total_vertices = 0
        total_faces = 0

        for layer in composited.layers:
            layer_draw_calls, layer_culled = self._process_layer(
                layer, view, culling
            )

            for dc in layer_draw_calls:
                if len(draw_calls) >= self.max_draw_calls:
                    break
                if total_vertices + dc.vertex_count > self.max_vertices_per_frame:
                    break
                draw_calls.append(dc)
                total_vertices += dc.vertex_count
                total_faces += dc.face_count

            culled += layer_culled

        return RenderFrame(
            draw_calls=draw_calls,
            total_vertices=total_vertices,
            total_faces=total_faces,
            culled_count=culled,
            camera_position=view.center,
        )

    def _process_layer(
        self,
        layer: WorldLayer,
        view: ViewRegion,
        culling: CullingMethod,
    ) -> Tuple[List[DrawCall], int]:
        draw_calls = []
        culled = 0

        features = layer.data.get("features", [])
        for feature in features:
            distance = self._compute_distance(
                view.center, feature.get("position", (0, 0, 0))
            )

            if self._is_culled(distance, view, culling):
                culled += 1
                continue

            lod = self.lod_manager.select_lod(distance)

            dc = DrawCall(
                batch_type=self._layer_to_batch_type(layer.type),
                mesh_id=feature.get("mesh_id", ""),
                material_id=feature.get("material_id", "default"),
                transform=feature.get("transform", [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]),
                layer_id=layer.id,
                lod_level=lod.level,
                vertex_count=int(feature.get("vertex_count", 0) * lod.config.building_detail),
                face_count=int(feature.get("face_count", 0) * lod.config.building_detail),
            )
            draw_calls.append(dc)

        return draw_calls, culled

    def _compute_distance(
        self,
        camera: Tuple[float, float, float],
        position: Tuple[float, float, float],
    ) -> float:
        dx = camera[0] - position[0]
        dy = camera[1] - position[1]
        dz = camera[2] - position[2]
        return math.sqrt(dx * dx + dy * dy + dz * dz)

    def _is_culled(
        self, distance: float, view: ViewRegion, method: CullingMethod
    ) -> bool:
        if method == CullingMethod.DISTANCE:
            return distance > view.radius
        return False

    def _layer_to_batch_type(self, layer_type: LayerType) -> RenderBatchType:
        mapping = {
            LayerType.TERRAIN: RenderBatchType.TERRAIN,
            LayerType.BASE_MAP: RenderBatchType.STATIC_MESH,
            LayerType.USER_RECONSTRUCTION: RenderBatchType.STATIC_MESH,
            LayerType.DYNAMIC_OBJECTS: RenderBatchType.DYNAMIC_MESH,
            LayerType.PLAYERS: RenderBatchType.DYNAMIC_MESH,
            LayerType.EFFECTS: RenderBatchType.PARTICLES,
        }
        return mapping.get(layer_type, RenderBatchType.STATIC_MESH)

    def get_stats(self, frame: RenderFrame) -> Dict[str, Any]:
        return {
            "draw_calls": len(frame.draw_calls),
            "total_vertices": frame.total_vertices,
            "total_faces": frame.total_faces,
            "culled_count": frame.culled_count,
            "batch_types": {
                bt.value: sum(1 for dc in frame.draw_calls if dc.batch_type == bt)
                for bt in RenderBatchType
            },
        }


# Module-level singleton
rendering_pipeline = RenderingPipeline()
