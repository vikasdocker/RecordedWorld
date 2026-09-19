"""
World Coordinate Precision

Handles large-world floating-point precision:
- Floating origin: rebase coordinates as player moves
- Chunk-relative coordinates: positions relative to chunk center
- High precision: double-precision throughout
- Deterministic conversion: consistent rounding

Architecture:
  WGS84 (global) → ENU (origin-relative) → Chunk-relative (chunk-local)
  Floating origin shifts when player moves >threshold from current origin.
"""

import math
from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict
from app.core.geospatial import (
    WGS84Coordinate,
    ENUVector,
    GameCoordinate,
    GeoTransform,
    create_transform,
    haversine_distance,
)


# =============================================================================
# Constants
# =============================================================================

# Default chunk size in meters
DEFAULT_CHUNK_SIZE = 1000.0

# Origin rebasing threshold — rebase when player moves this far from origin
ORIGIN_REBASE_THRESHOLD = 5000.0  # 5 km

# Maximum single-precision float precision at 1 meter scale
# float32 has ~7 decimal digits of precision
# At 1000m, precision is ~0.001m — acceptable for game coordinates
FLOAT32_PRECISION_LIMIT = 1000.0


# =============================================================================
# Chunk Coordinate System
# =============================================================================

@dataclass(frozen=True)
class ChunkIndex:
    """Identifies a chunk in the world grid."""
    cx: int  # chunk column
    cy: int  # chunk row
    cz: int = 0  # chunk layer (usually 0 for ground-level)

    def __hash__(self):
        return hash((self.cx, self.cy, self.cz))

    def __eq__(self, other):
        return self.cx == other.cx and self.cy == other.cy and self.cz == other.cz


@dataclass
class ChunkRelativePosition:
    """A position relative to a chunk's center."""
    chunk: ChunkIndex
    local_x: float  # meters from chunk center (East)
    local_y: float  # meters from chunk center (Up)
    local_z: float  # meters from chunk center (North)

    def to_world_enu(self, chunk_size: float = DEFAULT_CHUNK_SIZE) -> ENUVector:
        """Convert to world ENU coordinates."""
        world_x = self.chunk.cx * chunk_size + self.local_x
        world_y = self.chunk.cy * chunk_size + self.local_y
        world_z = self.chunk.cz * chunk_size + self.local_z
        return ENUVector(east=world_x, north=world_z, up=world_y)

    def to_game_coord(self, chunk_size: float = DEFAULT_CHUNK_SIZE) -> GameCoordinate:
        """Convert to game coordinates (Y-up)."""
        enu = self.to_world_enu(chunk_size)
        return GameCoordinate(x=enu.east, y=enu.up, z=enu.north)


def enu_to_chunk_relative(
    enu: ENUVector,
    chunk_size: float = DEFAULT_CHUNK_SIZE,
) -> ChunkRelativePosition:
    """Convert ENU coordinates to chunk-relative position."""
    # Determine which chunk this falls in
    cx = math.floor(enu.east / chunk_size + 0.5)
    cy = math.floor(enu.up / chunk_size + 0.5)
    cz = math.floor(enu.north / chunk_size + 0.5)

    # Local position relative to chunk center
    local_x = enu.east - cx * chunk_size
    local_y = enu.up - cy * chunk_size
    local_z = enu.north - cz * chunk_size

    return ChunkRelativePosition(
        chunk=ChunkIndex(cx, cy, cz),
        local_x=local_x,
        local_y=local_y,
        local_z=local_z,
    )


def chunk_relative_to_enu(
    pos: ChunkRelativePosition,
    chunk_size: float = DEFAULT_CHUNK_SIZE,
) -> ENUVector:
    """Convert chunk-relative position back to ENU."""
    return pos.to_world_enu(chunk_size)


# =============================================================================
# Floating Origin System
# =============================================================================

@dataclass
class FloatingOrigin:
    """
    Maintains a floating origin that shifts as the player moves.

    This prevents floating-point precision loss at large distances by
    keeping all coordinates small relative to the current origin.
    """
    origin: WGS84Coordinate
    transform: GeoTransform = field(init=False)
    total_offset: ENUVector = field(default_factory=lambda: ENUVector(0, 0, 0))

    def __post_init__(self):
        self.transform = create_transform(self.origin)

    def wgs84_to_game(self, coord: WGS84Coordinate) -> GameCoordinate:
        """Convert WGS84 to game coordinates using current origin."""
        return self.transform.wgs84_to_game(coord)

    def game_to_wgs84(self, game: GameCoordinate) -> WGS84Coordinate:
        """Convert game coordinates back to WGS84."""
        return self.transform.game_to_wgs84(game)

    def check_rebase(self, player_position: WGS84Coordinate) -> bool:
        """
        Check if origin should be rebased based on player position.
        Returns True if rebase was performed.
        """
        dist = haversine_distance(self.origin, player_position)
        if dist > ORIGIN_REBASE_THRESHOLD:
            self.rebase(player_position)
            return True
        return False

    def rebase(self, new_origin: WGS84Coordinate):
        """
        Rebase the origin to a new WGS84 point.

        All existing game coordinates become invalid after rebase.
        The client must request a fresh world state.
        """
        self.origin = new_origin
        self.transform = create_transform(new_origin)
        self.total_offset = ENUVector(0, 0, 0)

    def get_offset_from_original(self) -> ENUVector:
        """Get the total offset from the original origin."""
        return self.total_offset


# =============================================================================
# High-Precision Position Storage
# =============================================================================

@dataclass(frozen=True)
class HighPrecisionPosition:
    """
    High-precision position using double-precision lat/lon/alt.

    Python floats are already double-precision (float64),
    so this is mainly a documentation/convention marker.
    """
    latitude: float   # double precision WGS84
    longitude: float  # double precision WGS84
    altitude: float   # double precision meters

    @classmethod
    def from_wgs84(cls, coord: WGS84Coordinate) -> "HighPrecisionPosition":
        return cls(
            latitude=coord.latitude,
            longitude=coord.longitude,
            altitude=coord.altitude,
        )

    def to_wgs84(self) -> WGS84Coordinate:
        return WGS84Coordinate(
            latitude=self.latitude,
            longitude=self.longitude,
            altitude=self.altitude,
        )

    def distance_to(self, other: "HighPrecisionPosition") -> float:
        """Distance in meters to another high-precision position."""
        return haversine_distance(self.to_wgs84(), other.to_wgs84())


# =============================================================================
# Deterministic Coordinate Conversion
# =============================================================================

# Rounding precision for game coordinates (millimeters)
GAME_COORD_DECIMALS = 3


def deterministic_round(value: float, decimals: int = GAME_COORD_DECIMALS) -> float:
    """
    Deterministic rounding to specified decimal places.
    Uses round-half-to-even (banker's rounding) for consistency.
    """
    return round(value, decimals)


def wgs84_to_game_deterministic(
    coord: WGS84Coordinate,
    origin: WGS84Coordinate,
) -> GameCoordinate:
    """
    Deterministic WGS84 to game coordinate conversion.
    Always produces the same output for the same input.
    """
    transform = create_transform(origin)
    game = transform.wgs84_to_game(coord)
    return GameCoordinate(
        x=deterministic_round(game.x),
        y=deterministic_round(game.y),
        z=deterministic_round(game.z),
    )


def game_to_wgs84_deterministic(
    game: GameCoordinate,
    origin: WGS84Coordinate,
) -> WGS84Coordinate:
    """
    Deterministic game to WGS84 coordinate conversion.
    """
    transform = create_transform(origin)
    wgs = transform.game_to_wgs84(game)
    return WGS84Coordinate(
        latitude=round(wgs.latitude, 8),
        longitude=round(wgs.longitude, 8),
        altitude=round(wgs.altitude, 3),
    )


# =============================================================================
# World Manager — combines all precision systems
# =============================================================================

@dataclass
class WorldCoordinateManager:
    """
    Manages world coordinates with precision guarantees.

    Combines floating origin, chunk-relative positions, and
    deterministic conversion for consistent, precise positioning.
    """
    floating_origin: FloatingOrigin
    chunk_size: float = DEFAULT_CHUNK_SIZE
    chunk_positions: Dict[ChunkIndex, dict] = field(default_factory=dict)

    def wgs84_to_game(self, coord: WGS84Coordinate) -> GameCoordinate:
        """Convert WGS84 to game coordinates."""
        return self.floating_origin.wgs84_to_game(coord)

    def wgs84_to_chunk_relative(self, coord: WGS84Coordinate) -> ChunkRelativePosition:
        """Convert WGS84 to chunk-relative position."""
        enu = self.floating_origin.transform.wgs84_to_enu(coord)
        return enu_to_chunk_relative(enu, self.chunk_size)

    def get_chunk_for_position(self, game: GameCoordinate) -> ChunkIndex:
        """Get the chunk index for a game coordinate."""
        enu = ENUVector(east=game.x, north=game.z, up=game.y)
        pos = enu_to_chunk_relative(enu, self.chunk_size)
        return pos.chunk

    def register_entity(self, entity_id: str, coord: WGS84Coordinate):
        """Register an entity in the chunk system."""
        chunk_pos = self.wgs84_to_chunk_relative(coord)
        chunk = chunk_pos.chunk
        if chunk not in self.chunk_positions:
            self.chunk_positions[chunk] = {}
        self.chunk_positions[chunk][entity_id] = chunk_pos

    def get_entities_in_chunk(self, chunk: ChunkIndex) -> dict:
        """Get all entities in a chunk."""
        return self.chunk_positions.get(chunk, {})

    def get_nearby_chunks(self, center: ChunkIndex, radius: int = 1) -> list:
        """Get chunks within radius of center."""
        chunks = []
        for dx in range(-radius, radius + 1):
            for dy in range(-radius, radius + 1):
                for dz in range(-radius, radius + 1):
                    chunks.append(ChunkIndex(
                        cx=center.cx + dx,
                        cy=center.cy + dy,
                        cz=center.cz + dz,
                    ))
        return chunks
