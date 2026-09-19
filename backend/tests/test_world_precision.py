"""Tests for Phase 20: World Coordinate Precision — chunks, floating origin, deterministic."""

import pytest
import math

from app.core.geospatial import (
    WGS84Coordinate,
    ENUVector,
    GameCoordinate,
    create_transform,
    haversine_distance,
)
from app.core.world_precision import (
    ChunkIndex,
    ChunkRelativePosition,
    FloatingOrigin,
    HighPrecisionPosition,
    WorldCoordinateManager,
    enu_to_chunk_relative,
    chunk_relative_to_enu,
    deterministic_round,
    wgs84_to_game_deterministic,
    game_to_wgs84_deterministic,
    DEFAULT_CHUNK_SIZE,
    ORIGIN_REBASE_THRESHOLD,
)


# Test coordinates
NYC_ORIGIN = WGS84Coordinate(latitude=40.785, longitude=-73.968, altitude=0.0)
NYC_POINT_A = WGS84Coordinate(latitude=40.786, longitude=-73.967, altitude=10.0)
NYC_POINT_B = WGS84Coordinate(latitude=40.790, longitude=-73.960, altitude=5.0)


class TestChunkIndex:
    def test_chunk_equality(self):
        """ChunkIndex equality works correctly."""
        a = ChunkIndex(1, 2, 3)
        b = ChunkIndex(1, 2, 3)
        c = ChunkIndex(1, 2, 4)
        assert a == b
        assert a != c

    def test_chunk_hash(self):
        """ChunkIndex is hashable."""
        a = ChunkIndex(1, 2, 3)
        b = ChunkIndex(1, 2, 3)
        assert hash(a) == hash(b)
        # Can be used in sets/dicts
        s = {a, b}
        assert len(s) == 1


class TestChunkRelativePosition:
    def test_enu_to_chunk_relative(self):
        """ENU coordinates convert to chunk-relative position."""
        enu = ENUVector(east=500, north=300, up=10)
        pos = enu_to_chunk_relative(enu, chunk_size=1000)
        assert pos.chunk.cx == 1  # 500m is in chunk 1 (center at 1000)
        assert pos.local_x == -500  # 500 - 1000 = -500

    def test_chunk_relative_to_enu_roundtrip(self):
        """Converting ENU → chunk-relative → ENU preserves position."""
        original = ENUVector(east=1234.5, north=678.9, up=42.0)
        chunk_pos = enu_to_chunk_relative(original, chunk_size=1000)
        recovered = chunk_pos.to_world_enu(chunk_size=1000)

        assert abs(recovered.east - original.east) < 0.001
        assert abs(recovered.north - original.north) < 0.001
        assert abs(recovered.up - original.up) < 0.001

    def test_chunk_relative_to_game(self):
        """Chunk-relative position converts to game coordinates."""
        enu = ENUVector(east=100, north=200, up=50)
        chunk_pos = enu_to_chunk_relative(enu, chunk_size=1000)
        game = chunk_pos.to_game_coord(chunk_size=1000)
        assert game.x == chunk_pos.local_x
        assert game.y == chunk_pos.local_y
        assert game.z == chunk_pos.local_z

    def test_origin_chunk_is_zero(self):
        """Position near origin is in chunk (0,0,0)."""
        enu = ENUVector(east=10, north=20, up=5)
        pos = enu_to_chunk_relative(enu, chunk_size=1000)
        assert pos.chunk == ChunkIndex(0, 0, 0)
        assert abs(pos.local_x - 10) < 0.001
        assert abs(pos.local_z - 20) < 0.001


class TestFloatingOrigin:
    def test_initial_origin(self):
        """Floating origin starts at specified WGS84 point."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        assert fo.origin == NYC_ORIGIN

    def test_wgs84_to_game(self):
        """Can convert WGS84 to game coordinates."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        game = fo.wgs84_to_game(NYC_POINT_A)
        assert isinstance(game, GameCoordinate)
        # NYC point A is northeast of origin
        assert game.x > 0  # east
        assert game.z > 0  # north

    def test_game_to_wgs84_roundtrip(self):
        """Converting WGS84 → game → WGS84 preserves position."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        game = fo.wgs84_to_game(NYC_POINT_A)
        recovered = fo.game_to_wgs84(game)

        assert abs(recovered.latitude - NYC_POINT_A.latitude) < 0.0001
        assert abs(recovered.longitude - NYC_POINT_A.longitude) < 0.0001

    def test_rebase_needed(self):
        """Rebase is triggered when player moves beyond threshold."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        # Create a point 6 km away
        far_point = WGS84Coordinate(
            latitude=NYC_ORIGIN.latitude + 0.06,
            longitude=NYC_ORIGIN.longitude,
        )
        should_rebase = fo.check_rebase(far_point)
        assert should_rebase is True
        # Origin should have moved
        assert fo.origin != NYC_ORIGIN

    def test_rebase_not_needed(self):
        """No rebase if player is within threshold."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        close_point = WGS84Coordinate(
            latitude=NYC_ORIGIN.latitude + 0.01,
            longitude=NYC_ORIGIN.longitude,
        )
        should_rebase = fo.check_rebase(close_point)
        assert should_rebase is False

    def test_rebase_resets_offset(self):
        """Rebase resets the total offset."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        far_point = WGS84Coordinate(
            latitude=NYC_ORIGIN.latitude + 0.06,
            longitude=NYC_ORIGIN.longitude,
        )
        fo.rebase(far_point)
        assert fo.total_offset.east == 0
        assert fo.total_offset.north == 0


class TestHighPrecisionPosition:
    def test_from_wgs84(self):
        """Can create from WGS84 coordinate."""
        hpp = HighPrecisionPosition.from_wgs84(NYC_POINT_A)
        assert hpp.latitude == NYC_POINT_A.latitude
        assert hpp.longitude == NYC_POINT_A.longitude
        assert hpp.altitude == NYC_POINT_A.altitude

    def test_to_wgs84(self):
        """Can convert back to WGS84."""
        hpp = HighPrecisionPosition.from_wgs84(NYC_POINT_A)
        wgs = hpp.to_wgs84()
        assert wgs == NYC_POINT_A

    def test_distance_to(self):
        """Distance calculation works between high-precision positions."""
        a = HighPrecisionPosition.from_wgs84(NYC_ORIGIN)
        b = HighPrecisionPosition.from_wgs84(NYC_POINT_A)
        dist = a.distance_to(b)
        assert dist > 0
        assert dist < 1000  # Should be less than 1 km for NYC points


class TestDeterministicConversion:
    def test_deterministic_round(self):
        """Deterministic rounding produces consistent results."""
        assert deterministic_round(1.23456789, 3) == 1.235
        assert deterministic_round(1.23456789, 0) == 1.0
        assert deterministic_round(1.23456789, 6) == 1.234568

    def test_deterministic_same_output(self):
        """Same input always produces same output."""
        coord = WGS84Coordinate(latitude=40.785, longitude=-73.968)
        origin = WGS84Coordinate(latitude=40.785, longitude=-73.968)
        g1 = wgs84_to_game_deterministic(coord, origin)
        g2 = wgs84_to_game_deterministic(coord, origin)
        assert g1.x == g2.x
        assert g1.y == g2.y
        assert g1.z == g2.z

    def test_deterministic_roundtrip(self):
        """Deterministic conversion roundtrips correctly."""
        origin = NYC_ORIGIN
        coord = NYC_POINT_A
        game = wgs84_to_game_deterministic(coord, origin)
        recovered = game_to_wgs84_deterministic(game, origin)

        assert abs(recovered.latitude - coord.latitude) < 0.0001
        assert abs(recovered.longitude - coord.longitude) < 0.0001


class TestWorldCoordinateManager:
    def test_manager_creation(self):
        """Can create a world coordinate manager."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        manager = WorldCoordinateManager(floating_origin=fo)
        assert manager.floating_origin == fo

    def test_wgs84_to_chunk_relative(self):
        """Manager converts WGS84 to chunk-relative."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        manager = WorldCoordinateManager(floating_origin=fo)
        chunk_pos = manager.wgs84_to_chunk_relative(NYC_POINT_A)
        assert isinstance(chunk_pos, ChunkRelativePosition)

    def test_register_entity(self):
        """Manager registers entities in chunks."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        manager = WorldCoordinateManager(floating_origin=fo)
        manager.register_entity("player_1", NYC_POINT_A)

        chunk_pos = manager.wgs84_to_chunk_relative(NYC_POINT_A)
        entities = manager.get_entities_in_chunk(chunk_pos.chunk)
        assert "player_1" in entities

    def test_get_nearby_chunks(self):
        """Manager can get nearby chunks."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        manager = WorldCoordinateManager(floating_origin=fo)
        center = ChunkIndex(5, 5, 0)
        nearby = manager.get_nearby_chunks(center, radius=1)
        assert len(nearby) == 27  # 3x3x3 cube

    def test_get_chunk_for_position(self):
        """Manager gets chunk index for a game position."""
        fo = FloatingOrigin(origin=NYC_ORIGIN)
        manager = WorldCoordinateManager(floating_origin=fo)
        game = GameCoordinate(x=1500, y=0, z=2500)
        chunk = manager.get_chunk_for_position(game)
        assert chunk.cx == 2  # 1500 / 1000 = 1.5, rounds to 2
        assert chunk.cz == 3  # 2500 / 1000 = 2.5, rounds to 3


class TestPrecisionGuarantees:
    def test_small_distance_precision(self):
        """Small distances maintain millimeter precision."""
        a = WGS84Coordinate(latitude=40.785000, longitude=-73.968000)
        b = WGS84Coordinate(latitude=40.785001, longitude=-73.968001)
        origin = WGS84Coordinate(latitude=40.785, longitude=-73.968)

        game_a = wgs84_to_game_deterministic(a, origin)
        game_b = wgs84_to_game_deterministic(b, origin)

        # Should have measurable difference
        dx = game_b.x - game_a.x
        dz = game_b.z - game_a.z
        assert abs(dx) > 0.0001  # At least 0.1mm
        assert abs(dz) > 0.0001

    def test_large_distance_chunking(self):
        """Large distances are handled via chunking."""
        far_point = WGS84Coordinate(latitude=41.0, longitude=-74.0)
        origin = NYC_ORIGIN

        transform = create_transform(origin)
        enu = transform.wgs84_to_enu(far_point)
        chunk_pos = enu_to_chunk_relative(enu, chunk_size=1000)

        # Far point should be in a distant chunk
        assert abs(chunk_pos.chunk.cx) > 10 or abs(chunk_pos.chunk.cz) > 10
        # Local coordinates should be small
        assert abs(chunk_pos.local_x) < DEFAULT_CHUNK_SIZE / 2
        assert abs(chunk_pos.local_z) < DEFAULT_CHUNK_SIZE / 2
