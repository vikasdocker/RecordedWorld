"""Performance optimization service for low-latency multiplayer."""
import asyncio
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import deque
import json


@dataclass
class LatencyMetrics:
    ws_message_latency_ms: float = 0
    render_fps: float = 60
    network_send_rate: int = 0
    network_recv_rate: int = 0
    last_update: float = field(default_factory=time.time)


class LatencyOptimizer:
    """Optimizes network and rendering for real-time performance."""

    def __init__(self):
        self.metrics = LatencyMetrics()
        self.position_buffer: deque = deque(maxlen=10)
        self.interpolation_delay_ms = 50
        self.tick_rate_hz = 20
        self.enable_prediction = True
        self.enable_interpolation = True

    def configure_for_quality(self, quality: str):
        """Adjust settings based on connection quality."""
        if quality == "high":
            self.tick_rate_hz = 30
            self.interpolation_delay_ms = 33
            self.enable_prediction = True
        elif quality == "medium":
            self.tick_rate_hz = 20
            self.interpolation_delay_ms = 50
            self.enable_prediction = True
        else:  # low
            self.tick_rate_hz = 10
            self.interpolation_delay_ms = 100
            self.enable_prediction = False

    def interpolate_position(
        self,
        pos_a: Dict[str, float],
        pos_b: Dict[str, float],
        t: float,
    ) -> Dict[str, float]:
        """Interpolate between two positions for smooth movement."""
        return {
            "x": pos_a["x"] + (pos_b["x"] - pos_a["x"]) * t,
            "y": pos_a["y"] + (pos_b["y"] - pos_a["y"]) * t,
            "z": pos_a["z"] + (pos_b["z"] - pos_a["z"]) * t,
        }

    def predict_position(
        self,
        current_pos: Dict[str, float],
        velocity: Dict[str, float],
        delta_time: float,
    ) -> Dict[str, float]:
        """Predict next position based on velocity (client-side prediction)."""
        if not self.enable_prediction:
            return current_pos

        return {
            "x": current_pos["x"] + velocity["x"] * delta_time,
            "y": current_pos["y"] + velocity["y"] * delta_time,
            "z": current_pos["z"] + velocity["z"] * delta_time,
        }

    def should_send_update(self, last_pos: Dict, current_pos: Dict, threshold: float = 0.1) -> bool:
        """Determine if position change is significant enough to broadcast."""
        dx = abs(current_pos["x"] - last_pos.get("x", 0))
        dy = abs(current_pos["y"] - last_pos.get("y", 0))
        dz = abs(current_pos["z"] - last_pos.get("z", 0))
        return (dx + dy + dz) > threshold

    def compress_state(self, state: Dict) -> bytes:
        """Compress game state for network transmission."""
        # Use minimal JSON format
        compressed = {
            "p": state.get("position"),
            "r": state.get("rotation"),
            "a": state.get("animation"),
        }
        return json.dumps(compressed).encode()

    def decompress_state(self, data: bytes) -> Dict:
        """Decompress received game state."""
        compressed = json.loads(data.decode())
        return {
            "position": compressed.get("p"),
            "rotation": compressed.get("r"),
            "animation": compressed.get("a"),
        }


class RenderOptimizer:
    """Optimizes 3D rendering for smooth frame rates."""

    def __init__(self):
        self.lod_distances = [10, 30, 60, 100]
        self.enable_frustum_culling = True
        self.enable_occlusion_culling = True
        self.max_draw_calls = 500

    def calculate_lod(self, distance: float) -> int:
        """Calculate level of detail based on distance."""
        for i, d in enumerate(self.lod_distances):
            if distance < d:
                return i
        return len(self.lod_distances)

    def should_render(self, object_pos: Dict, camera_pos: Dict, fov: float = 75) -> bool:
        """Determine if object is within view frustum."""
        if not self.enable_frustum_culling:
            return True

        dx = object_pos["x"] - camera_pos["x"]
        dz = object_pos["z"] - camera_pos["z"]
        distance = (dx ** 2 + dz ** 2) ** 0.5

        return distance < 150  # View distance

    def get_optimal_settings(self, target_fps: float = 60) -> Dict:
        """Get rendering settings for target FPS."""
        return {
            "shadow_map_size": 1024 if target_fps >= 60 else 512,
            "antialiasing": target_fps >= 60,
            "pixel_ratio": 1.0 if target_fps >= 60 else 0.75,
            "max_objects": self.max_draw_calls,
        }


# Singletons
latency_optimizer = LatencyOptimizer()
render_optimizer = RenderOptimizer()
