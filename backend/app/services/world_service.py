"""
World Service

World state management and chunk operations.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.core.world_precision import (
    ChunkIndex,
    FloatingOrigin,
    WorldCoordinateManager,
    enu_to_chunk_relative,
)
from app.core.geospatial import WGS84Coordinate


@dataclass
class WorldState:
    """Complete world state snapshot."""
    locations: Dict[int, dict] = field(default_factory=dict)
    players: Dict[int, dict] = field(default_factory=dict)
    entities: Dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "locations": self.locations,
            "players": self.players,
            "entities": self.entities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class WorldService:
    """Manages world state, chunks, and spatial queries."""

    _world_state: WorldState = WorldState()
    _manager: Optional[WorldCoordinateManager] = None

    @classmethod
    def initialize(cls, origin: WGS84Coordinate):
        """Initialize world with a WGS84 origin."""
        fo = FloatingOrigin(origin=origin)
        cls._manager = WorldCoordinateManager(floating_origin=fo)

    @classmethod
    def get_manager(cls) -> WorldCoordinateManager:
        """Get the world coordinate manager."""
        if cls._manager is None:
            cls.initialize(WGS84Coordinate(latitude=0, longitude=0))
        return cls._manager

    @classmethod
    def register_location(cls, location_id: int, coord: WGS84Coordinate, data: dict):
        """Register a location in the world state."""
        cls._world_state.locations[location_id] = {
            "id": location_id,
            "latitude": coord.latitude,
            "longitude": coord.longitude,
            "altitude": coord.altitude,
            **data,
        }

    @classmethod
    def unregister_location(cls, location_id: int):
        """Remove a location from the world state."""
        cls._world_state.locations.pop(location_id, None)

    @classmethod
    def register_player(cls, player_id: int, data: dict):
        """Register a player in the world state."""
        cls._world_state.players[player_id] = data

    @classmethod
    def unregister_player(cls, player_id: int):
        """Remove a player from the world state."""
        cls._world_state.players.pop(player_id, None)

    @classmethod
    def update_player_position(cls, player_id: int, position: dict):
        """Update a player's position."""
        if player_id in cls._world_state.players:
            cls._world_state.players[player_id]["position"] = position

    @classmethod
    def register_entity(cls, entity_id: str, data: dict):
        """Register an entity in the world state."""
        cls._world_state.entities[entity_id] = data

    @classmethod
    def unregister_entity(cls, entity_id: str):
        """Remove an entity from the world state."""
        cls._world_state.entities.pop(entity_id, None)

    @classmethod
    def get_state(cls) -> WorldState:
        """Get the current world state."""
        return cls._world_state

    @classmethod
    def get_locations_in_chunk(cls, chunk: ChunkIndex) -> List[dict]:
        """Get all locations in a chunk."""
        manager = cls.get_manager()
        results = []
        for loc_id, loc_data in cls._world_state.locations.items():
            coord = WGS84Coordinate(
                loc_data["latitude"], loc_data["longitude"],
                loc_data.get("altitude", 0)
            )
            chunk_pos = manager.wgs84_to_chunk_relative(coord)
            if chunk_pos.chunk == chunk:
                results.append(loc_data)
        return results

    @classmethod
    def get_nearby_chunks(cls, center: ChunkIndex, radius: int = 1) -> List[ChunkIndex]:
        """Get chunks within radius of center."""
        manager = cls.get_manager()
        return manager.get_nearby_chunks(center, radius)

    @classmethod
    def get_player_count(cls) -> int:
        """Get number of registered players."""
        return len(cls._world_state.players)

    @classmethod
    def get_location_count(cls) -> int:
        """Get number of registered locations."""
        return len(cls._world_state.locations)
