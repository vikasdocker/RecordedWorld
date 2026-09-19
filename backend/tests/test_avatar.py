"""Tests for Phase 12: Player Avatars — color customization, animation state, visibility indicators."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.websocket_server import (
    MultiplayerServer,
    MessageType,
    PlayerVisibility,
)


def _run(coro):
    """Run an async coroutine in tests."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class MockWebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, data):
        self.messages.append(data)

    async def accept(self):
        pass


@pytest.fixture
def server():
    return MultiplayerServer(
        heartbeat_interval=1.0,
        heartbeat_timeout=5.0,
        view_radius_meters=500.0,
        position_update_rate_limit=0.0,
        max_speed_units_sec=5000000.0,
        max_position_jump_units=10000000.0,
    )


class TestAvatarColor:
    def test_default_color(self, server):
        """New players get default color #00ff88."""
        ws = MockWebSocket()
        player = _run(server.connect(ws, "alice", 1))
        assert player.color == "#00ff88"

    def test_set_avatar_color(self, server):
        """Player can set avatar color via SET_AVATAR message."""
        ws = MockWebSocket()
        player = _run(server.connect(ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_AVATAR,
            "color": "#ff0000",
        }))

        assert player.color == "#ff0000"
        # Should get confirmation
        avatar_msgs = [m for m in ws.messages if m["type"] == "avatar_changed"]
        assert len(avatar_msgs) == 1
        assert avatar_msgs[0]["color"] == "#ff0000"

    def test_invalid_color_rejected(self, server):
        """Invalid color format is rejected."""
        ws = MockWebSocket()
        player = _run(server.connect(ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_AVATAR,
            "color": "not-a-color",
        }))

        assert player.color == "#00ff88"  # unchanged
        error_msgs = [m for m in ws.messages if m["type"] == MessageType.ERROR]
        assert len(error_msgs) == 1

    def test_empty_color_rejected(self, server):
        """Empty color is rejected."""
        ws = MockWebSocket()
        player = _run(server.connect(ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_AVATAR,
            "color": "",
        }))

        assert player.color == "#00ff88"

    def test_short_hex_color_accepted(self, server):
        """3-digit hex color (#RGB) is accepted."""
        ws = MockWebSocket()
        player = _run(server.connect(ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_AVATAR,
            "color": "#f00",
        }))

        assert player.color == "#f00"

    def test_color_broadcast_in_move(self, server):
        """Color is included in PLAYER_MOVE broadcasts."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.SET_AVATAR,
            "color": "#ff0000",
        }))

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        ws2.messages.clear()
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 1
        assert move_msgs[0]["color"] == "#ff0000"

    def test_color_in_world_state(self, server):
        """Color is included in WORLD_STATE for existing players."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.SET_AVATAR,
            "color": "#aabbcc",
        }))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Bob connects and gets world state
        ws2 = MockWebSocket()
        _run(server.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        alice_data = [p for p in world_msgs[0]["players"] if p["username"] == "alice"]
        assert len(alice_data) == 1
        assert alice_data[0]["color"] == "#aabbcc"

    def test_color_in_join_event(self, server):
        """Color is included in PLAYER_JOIN events."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws1.messages.clear()

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.SET_AVATAR,
            "color": "#112233",
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 1
        assert join_msgs[0]["player"]["color"] == "#112233"

    def test_color_persists_across_reconnect(self, server):
        """Color is preserved when player reconnects."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.SET_AVATAR,
            "color": "#deadbe",
        }))
        _run(server.disconnect(p1))

        ws2 = MockWebSocket()
        p1_2 = _run(server.connect(ws2, "alice", 1))
        assert p1_2.color == "#deadbe"


class TestPlayerVisibility:
    def test_visibility_in_world_state(self, server):
        """Visibility is included in WORLD_STATE."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        ws2 = MockWebSocket()
        _run(server.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        alice_data = [p for p in world_msgs[0]["players"] if p["username"] == "alice"]
        assert alice_data[0]["visibility"] == "public"

    def test_visibility_in_join_event(self, server):
        """Visibility is included in PLAYER_JOIN events."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws1.messages.clear()

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Hidden player should not send join event
        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 0
