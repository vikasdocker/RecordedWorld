import pytest
import asyncio
import time
from unittest.mock import AsyncMock

from app.websocket_server import (
    MultiplayerServer, Player, MessageType,
)


class MockWebSocket:
    """Mock WebSocket for testing."""

    def __init__(self):
        self.messages = []
        self.accepted = False
        self.closed = False

    async def accept(self):
        self.accepted = True

    async def send_json(self, data):
        self.messages.append(data)

    async def close(self):
        self.closed = True


def _run(coro):
    """Run async coroutine in sync test."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def server():
    return MultiplayerServer(
        heartbeat_interval=1.0,
        heartbeat_timeout=5.0,
        view_radius_meters=500.0,
        position_update_rate_limit=0.0,
        max_speed_units_sec=100.0,
        max_position_jump_units=1000.0,
    )


@pytest.fixture
def spatial_server():
    """Server with higher limits for spatial interest tests (large position jumps)."""
    return MultiplayerServer(
        heartbeat_interval=1.0,
        heartbeat_timeout=5.0,
        view_radius_meters=500.0,
        position_update_rate_limit=0.0,
        max_speed_units_sec=5000000.0,  # ~5000 km/s for cross-city jumps
        max_position_jump_units=10000000.0,  # 10,000 km
    )


@pytest.fixture
def mock_ws():
    return MockWebSocket()


# --- Player Connection Tests ---

class TestPlayerConnection:
    def test_connect_creates_player(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", world_id=1))

        assert player.id == 1
        assert player.username == "alice"
        assert player.world_id == 1
        assert mock_ws.accepted
        assert player.id in server.players

    def test_connect_increments_id(self, server, mock_ws):
        p1 = _run(server.connect(mock_ws, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        assert p2.id == p1.id + 1

    def test_connect_adds_to_world(self, server, mock_ws):
        _run(server.connect(mock_ws, "alice", 1))

        assert 1 in server.worlds
        assert len(server.worlds[1]) == 1

    def test_connect_sends_world_state(self, server, mock_ws):
        ws1 = MockWebSocket()
        _run(server.connect(ws1, "alice", 1))

        _run(server.connect(mock_ws, "bob", 1))

        world_state_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_state_msgs) == 1
        assert len(world_state_msgs[0]["players"]) == 1
        assert world_state_msgs[0]["players"][0]["username"] == "alice"

    def test_connect_broadcasts_join(self, server, mock_ws):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws1.messages.clear()

        p2 = _run(server.connect(mock_ws, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 1
        assert join_msgs[0]["player"]["username"] == "bob"


# --- Disconnect Tests ---

class TestDisconnect:
    def test_disconnect_removes_player(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))
        _run(server.disconnect(player))

        assert player.id not in server.players

    def test_disconnect_removes_from_world(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))
        _run(server.disconnect(player))

        assert player.id not in server.worlds.get(1, set())

    def test_disconnect_broadcasts_leave(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws1.messages.clear()
        _run(server.disconnect(p2))

        leave_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_msgs) == 1
        assert leave_msgs[0]["player_id"] == p2.id


# --- Position Update Tests ---

class TestPositionUpdate:
    def test_position_update_changes_position(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
            "rotation": 90.0,
        }))

        assert player.position["lat"] == 40.7128
        assert player.rotation == 90.0

    def test_position_update_broadcasts_to_others(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        # Both use local coordinates
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws2.messages.clear()

        # Simulate time passing
        p1.last_position_update = time.time() - 0.5

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 10, "y": 0, "z": 5},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 1
        assert move_msgs[0]["position"]["x"] == 10


# --- Spatial Interest Tests ---

class TestSpatialInterest:
    def test_nearby_players_visible(self, spatial_server):
        ws1 = MockWebSocket()
        p1 = _run(spatial_server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(spatial_server.connect(ws2, "bob", 1))

        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))

        assert p2.id in p1.visible_players
        assert p1.id in p2.visible_players

    def test_distant_players_not_visible(self, spatial_server):
        ws1 = MockWebSocket()
        p1 = _run(spatial_server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(spatial_server.connect(ws2, "bob", 1))

        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 34.0522, "lon": -118.2437},
        }))

        assert p2.id not in p1.visible_players
        assert p1.id not in p2.visible_players

    def test_move_into_view_sends_join(self, spatial_server):
        ws1 = MockWebSocket()
        p1 = _run(spatial_server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(spatial_server.connect(ws2, "bob", 1))

        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 34.0522, "lon": -118.2437},
        }))

        assert p2.id not in p1.visible_players
        ws1.messages.clear()

        p2.last_position_update = time.time() - 1.0
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))

        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) >= 1

    def test_move_out_of_view_sends_leave(self, spatial_server):
        ws1 = MockWebSocket()
        p1 = _run(spatial_server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(spatial_server.connect(ws2, "bob", 1))

        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))

        assert p2.id in p1.visible_players
        ws1.messages.clear()

        p2.last_position_update = time.time() - 1.0
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 34.0522, "lon": -118.2437},
        }))

        leave_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_msgs) >= 1

    def test_position_only_broadcasts_to_visible(self, spatial_server):
        ws1 = MockWebSocket()
        p1 = _run(spatial_server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(spatial_server.connect(ws2, "bob", 1))

        ws3 = MockWebSocket()
        p3 = _run(spatial_server.connect(ws3, "charlie", 1))

        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))
        _run(spatial_server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))

        _run(spatial_server.handle_message(p3, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 34.0522, "lon": -118.2437},
        }))

        assert p2.id in p1.visible_players
        assert p3.id not in p1.visible_players

        ws2.messages.clear()
        ws3.messages.clear()

        p1.last_position_update = time.time() - 1.0
        _run(spatial_server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7130, "lon": -74.0055},
        }))

        bob_moves = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        charlie_moves = [m for m in ws3.messages if m["type"] == MessageType.PLAYER_MOVE]

        assert len(bob_moves) == 1
        assert len(charlie_moves) == 0


# --- Chat Tests ---

class TestChat:
    def test_chat_broadcasts_to_all(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.CHAT,
            "message": "Hello world!",
        }))

        chat_msgs = [m for m in ws1.messages if m["type"] == MessageType.CHAT_MSG]
        assert len(chat_msgs) == 1
        assert chat_msgs[0]["message"] == "Hello world!"

    def test_chat_empty_message_ignored(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.CHAT,
            "message": "",
        }))

        chat_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.CHAT_MSG]
        assert len(chat_msgs) == 0

    def test_chat_truncates_long_message(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.CHAT,
            "message": "x" * 1000,
        }))

        chat_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.CHAT_MSG]
        assert len(chat_msgs) == 1
        assert len(chat_msgs[0]["message"]) == 500


# --- World List Tests ---

class TestWorldList:
    def test_world_list(self, server):
        ws1 = MockWebSocket()
        _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        _run(server.connect(ws2, "bob", 2))

        player = server.players[1]
        _run(server.handle_message(player, {"type": "world_list"}))

        world_msgs = [m for m in ws1.messages if m["type"] == MessageType.WORLD_LIST_RESP]
        assert len(world_msgs) == 1
        assert len(world_msgs[0]["worlds"]) == 2


# --- Distance Calculation Tests ---

class TestDistance:
    def test_same_position_distance(self, server):
        pos = {"lat": 40.7128, "lon": -74.0060}
        dist = server._calculate_distance(pos, pos)
        assert dist == 0.0

    def test_known_distance(self, server):
        ny = {"lat": 40.7128, "lon": -74.0060}
        la = {"lat": 34.0522, "lon": -118.2437}
        dist = server._calculate_distance(ny, la)
        assert 3900000 < dist < 4000000

    def test_euclidean_distance(self, server):
        a = {"x": 0, "y": 0, "z": 0}
        b = {"x": 3, "y": 4, "z": 0}
        dist = server._calculate_distance(a, b)
        assert abs(dist - 5.0) < 0.01


# --- Heartbeat Tests ---

class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))
        old_hb = player.last_heartbeat

        time.sleep(0.1)
        _run(server.handle_message(player, {"type": MessageType.PONG}))

        assert player.last_heartbeat > old_hb


# --- Message Handling Tests ---

class TestMessageHandling:
    def test_unknown_message_type_ignored(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))
        _run(server.handle_message(player, {"type": "unknown_type"}))
        # Should not raise

    def test_multiple_worlds(self, server):
        ws1 = MockWebSocket()
        ws2 = MockWebSocket()
        _run(server.connect(ws1, "alice", 1))
        _run(server.connect(ws2, "bob", 2))

        assert server.get_world_player_count(1) == 1
        assert server.get_world_player_count(2) == 1

    def test_get_player(self, server, mock_ws):
        player = _run(server.connect(mock_ws, "alice", 1))
        assert server.get_player(player.id) == player
        assert server.get_player(999) is None

    def test_get_player_count(self, server):
        assert server.get_player_count() == 0
        ws1 = MockWebSocket()
        _run(server.connect(ws1, "alice", 1))
        assert server.get_player_count() == 1


# --- Cleanup Tests ---

class TestCleanup:
    def test_broadcast_removes_dead_connections(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        ws2.send_json = AsyncMock(side_effect=Exception("dead"))

        _run(server.broadcast(1, {"type": "chat_msg", "message": "test"}))

        assert p2.id not in server.players


# --- Authoritative Movement Tests ---

class TestAuthoritativeMovement:
    def test_valid_movement_accepted(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set initial position with proper timing
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Simulate time passing
        p1.last_position_update = time.time() - 0.5  # 0.5s ago

        # Move a reasonable distance (1m in 0.5s = 2 m/s, well under 100 m/s)
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p1.position["x"] == 1

    def test_speed_exceeds_max_corrects(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set initial position
        p1.position = {"x": 0, "y": 0, "z": 0}
        p1.last_valid_position = {"x": 0, "y": 0, "z": 0}
        p1.last_position_update = time.time() - 0.1  # 0.1 seconds ago

        # Try to move 100m in 0.1s = 1000 m/s (way over 10 m/s max)
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 100, "y": 0, "z": 0},
        }))

        # Position should be corrected
        correction_msgs = [m for m in ws1.messages if m.get("type") == MessageType.POSITION_CORRECTION]
        assert len(correction_msgs) == 1

    def test_teleport_detection(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set initial position
        p1.position = {"x": 0, "y": 0, "z": 0}
        p1.last_valid_position = {"x": 0, "y": 0, "z": 0}
        p1.last_position_update = time.time()

        # Try to teleport 1000m
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1000, "y": 0, "z": 0},
        }))

        # Should be rejected and sent back to original position
        correction_msgs = [m for m in ws1.messages if m.get("type") == MessageType.POSITION_CORRECTION]
        assert len(correction_msgs) == 1
        assert correction_msgs[0]["reason"] == "movement_violation"

    def test_velocity_calculated(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set initial position with known timing
        p1.position = {"x": 0, "y": 0, "z": 0}
        p1.last_valid_position = {"x": 0, "y": 0, "z": 0}
        p1.last_position_update = time.time() - 1.0  # 1 second ago

        # Move 5m in 1s = 5 m/s
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        # Check velocity was calculated
        assert p1.velocity["x"] > 0

    def test_geo_position_validation(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set initial geo position
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7128, "lon": -74.0060},
        }))

        # Move slightly (valid)
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"lat": 40.7130, "lon": -74.0055},
        }))

        assert abs(p1.position["lat"] - 40.7130) < 0.001

    def test_position_broadcast_includes_velocity(self, server):
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        # Both use local coords
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws2.messages.clear()

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 2, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 1
        assert "velocity" in move_msgs[0]
        assert "server_tick" in move_msgs[0]

    def test_interpolate_position(self, server):
        start = {"x": 0, "y": 0, "z": 0}
        end = {"x": 10, "y": 20, "z": 30}

        mid = server._interpolate_position(start, end, 0.5)
        assert mid["x"] == 5
        assert mid["y"] == 10
        assert mid["z"] == 15

    def test_interpolate_geo_position(self, server):
        start = {"lat": 40.0, "lon": -74.0, "alt": 0}
        end = {"lat": 41.0, "lon": -73.0, "alt": 100}

        mid = server._interpolate_position(start, end, 0.5)
        assert abs(mid["lat"] - 40.5) < 0.01
        assert abs(mid["lon"] - (-73.5)) < 0.01
        assert mid["alt"] == 50
