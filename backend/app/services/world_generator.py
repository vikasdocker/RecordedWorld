"""World generation service - creates 3D game worlds from processed captures."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class WorldObject:
    id: str
    type: str  # building, tree, rock, spawn_point, etc.
    position: Dict[str, float]
    rotation: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    scale: Dict[str, float] = field(default_factory=lambda: {"x": 1, "y": 1, "z": 1})
    interactive: bool = False
    properties: Dict = field(default_factory=dict)


@dataclass
class WorldConfig:
    id: int
    name: str
    capture_id: int
    model_path: str
    spawn_points: List[Dict[str, float]]
    boundaries: Dict[str, Dict[str, float]]
    objects: List[WorldObject]
    max_players: int = 20


class WorldGenerator:
    """Generates game world configurations from 3D processed captures."""

    def __init__(self):
        self.worlds: Dict[int, WorldConfig] = {}

    def generate_from_capture(
        self,
        capture_id: int,
        model_path: str,
        point_cloud_data: Optional[Dict] = None,
    ) -> WorldConfig:
        """Generate a complete world config from processed capture data."""

        # Analyze point cloud to find ground plane
        spawn_points = self._find_spawn_points(point_cloud_data)

        # Detect boundaries from point cloud extent
        boundaries = self._calculate_boundaries(point_cloud_data)

        # Generate interactive objects based on scene analysis
        objects = self._generate_objects(point_cloud_data, boundaries)

        world = WorldConfig(
            id=capture_id,
            name=f"World {capture_id}",
            capture_id=capture_id,
            model_path=model_path,
            spawn_points=spawn_points,
            boundaries=boundaries,
            objects=objects,
        )

        self.worlds[capture_id] = world
        return world

    def _find_spawn_points(self, point_cloud: Optional[Dict]) -> List[Dict[str, float]]:
        """Find suitable spawn locations on flat ground."""
        if not point_cloud:
            return [{"x": 0, "y": 0, "z": 0}]

        # In production: analyze point cloud for flat areas
        return [
            {"x": 0, "y": 0, "z": 0},
            {"x": 5, "y": 0, "z": 5},
            {"x": -5, "y": 0, "z": -5},
        ]

    def _calculate_boundaries(self, point_cloud: Optional[Dict]) -> Dict[str, Dict[str, float]]:
        """Calculate world boundaries from point cloud extent."""
        if not point_cloud:
            return {
                "min": {"x": -50, "y": 0, "z": -50},
                "max": {"x": 50, "y": 30, "z": 50},
            }

        # In production: use actual point cloud bounds
        return {
            "min": {"x": -50, "y": 0, "z": -50},
            "max": {"x": 50, "y": 30, "z": 50},
        }

    def _generate_objects(
        self, point_cloud: Optional[Dict], boundaries: Dict
    ) -> List[WorldObject]:
        """Generate interactive objects based on scene analysis."""
        objects = [
            WorldObject(
                id="spawn_center",
                type="spawn_point",
                position={"x": 0, "y": 0, "z": 0},
                interactive=True,
                properties={"label": "Main Spawn"},
            ),
        ]
        return objects

    def export_world(self, world_id: int, output_path: Path) -> Path:
        """Export world config to JSON for the PC client."""
        world = self.worlds.get(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found")

        config = {
            "id": world.id,
            "name": world.name,
            "model_path": world.model_path,
            "spawn_points": world.spawn_points,
            "boundaries": world.boundaries,
            "objects": [
                {
                    "id": obj.id,
                    "type": obj.type,
                    "position": obj.position,
                    "rotation": obj.rotation,
                    "scale": obj.scale,
                    "interactive": obj.interactive,
                    "properties": obj.properties,
                }
                for obj in world.objects
            ],
            "max_players": world.max_players,
        }

        output_path.mkdir(parents=True, exist_ok=True)
        config_path = output_path / f"world_{world_id}.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return config_path


# Singleton
generator = WorldGenerator()
