"""
World Composition Service

Layer compositing system for merging base map and user-generated content.
Each layer is independently managed and composited at render time.
"""
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class LayerType(Enum):
    TERRAIN = "terrain"
    BASE_MAP = "base_map"
    USER_RECONSTRUCTION = "user_reconstruction"
    DYNAMIC_OBJECTS = "dynamic_objects"
    PLAYERS = "players"
    EFFECTS = "effects"


class LayerBlendMode(Enum):
    OPAQUE = "opaque"
    ALPHA_BLEND = "alpha_blend"
    ADDITIVE = "additive"


@dataclass
class WorldLayer:
    """A single layer in the world composition stack."""
    id: str
    type: LayerType
    name: str
    visible: bool = True
    opacity: float = 1.0
    blend_mode: LayerBlendMode = LayerBlendMode.OPAQUE
    priority: int = 0  # Higher = rendered later (on top)
    data: Dict[str, Any] = field(default_factory=dict)
    bounds: Optional[Dict[str, float]] = None  # geographic bounds
    last_modified: float = field(default_factory=time.time)

    @property
    def is_user_content(self) -> bool:
        return self.type in (LayerType.USER_RECONSTRUCTION, LayerType.DYNAMIC_OBJECTS)


@dataclass
class CompositeResult:
    """Result of compositing all visible layers."""
    layers: List[WorldLayer]
    total_vertices: int
    total_faces: int
    visible_count: int
    bounds: Optional[Dict[str, float]] = None


class LayerCompositor:
    """Manages layer stacking and compositing for the world."""

    def __init__(self):
        self.layers: Dict[str, WorldLayer] = {}
        self.render_order: List[str] = []  # layer IDs in render order

    def add_layer(self, layer: WorldLayer):
        self.layers[layer.id] = layer
        if layer.id not in self.render_order:
            self.render_order.append(layer.id)
        self._sort_render_order()

    def remove_layer(self, layer_id: str) -> bool:
        if layer_id in self.layers:
            del self.layers[layer_id]
            self.render_order.remove(layer_id)
            return True
        return False

    def get_layer(self, layer_id: str) -> Optional[WorldLayer]:
        return self.layers.get(layer_id)

    def set_layer_visible(self, layer_id: str, visible: bool):
        if layer_id in self.layers:
            self.layers[layer_id].visible = visible

    def set_layer_opacity(self, layer_id: str, opacity: float):
        if layer_id in self.layers:
            self.layers[layer_id].opacity = max(0.0, min(1.0, opacity))

    def composite(self) -> CompositeResult:
        """Composite all visible layers in render order."""
        visible_layers = []
        total_vertices = 0
        total_faces = 0

        for layer_id in self.render_order:
            layer = self.layers.get(layer_id)
            if layer and layer.visible:
                visible_layers.append(layer)
                total_vertices += layer.data.get("vertex_count", 0)
                total_faces += layer.data.get("face_count", 0)

        bounds = self._compute_combined_bounds(visible_layers)

        return CompositeResult(
            layers=visible_layers,
            total_vertices=total_vertices,
            total_faces=total_faces,
            visible_count=len(visible_layers),
            bounds=bounds,
        )

    def get_user_layers(self) -> List[WorldLayer]:
        return [l for l in self.layers.values() if l.is_user_content]

    def get_base_layers(self) -> List[WorldLayer]:
        return [l for l in self.layers.values()
                if l.type in (LayerType.TERRAIN, LayerType.BASE_MAP)]

    def _sort_render_order(self):
        self.render_order.sort(
            key=lambda lid: self.layers[lid].priority
            if lid in self.layers else 0
        )

    def _compute_combined_bounds(
        self, layers: List[WorldLayer]
    ) -> Optional[Dict[str, float]]:
        all_bounds = [l.bounds for l in layers if l.bounds]
        if not all_bounds:
            return None

        return {
            "min_lat": min(b["min_lat"] for b in all_bounds),
            "max_lat": max(b["max_lat"] for b in all_bounds),
            "min_lon": min(b["min_lon"] for b in all_bounds),
            "max_lon": max(b["max_lon"] for b in all_bounds),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_layers": len(self.layers),
            "visible_layers": sum(1 for l in self.layers.values() if l.visible),
            "user_layers": len(self.get_user_layers()),
            "base_layers": len(self.get_base_layers()),
        }


# Module-level singleton
layer_compositor = LayerCompositor()
