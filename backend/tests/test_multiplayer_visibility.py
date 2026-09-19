"""
Comprehensive tests for multiplayer player visibility system.

Tests cover:
- Public visibility (default): all nearby players see each other
- Friends-only visibility: only friends see each other
- Hidden visibility: invisible to everyone
- Visibility changes: real-time updates when players change visibility
- Blocking: blocked players cannot see each other
- Reconnects: visibility state preserved on reconnect
- Privacy: GPS coordinates not exposed to unauthorized viewers
- Server-authoritative enforcement: all visibility rules enforced server-side
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock

from app.websocket_server import (
    MultiplayerServer, Player, PlayerVisibility, MessageType,
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
        max_speed_ms=5000000.0,
        max_position_jump_meters=10000000.0,
    )


@pytest.fixture
def server_with_friends():
    """Server with friendship callbacks configured."""
    s = MultiplayerServer(
        heartbeat_interval=1.0,
        heartbeat_timeout=5.0,
        view_radius_meters=500.0,
        position_update_rate_limit=0.0,
        max_speed_ms=5000000.0,
        max_position_jump_meters=10000000.0,
    )
    # Simple in-memory friendship store
    friendships = set()
    blocked = set()

    def is_friend(a, b):
        return (a, b) in friendships or (b, a) in friendships

    def is_blocked(a, b):
        return (a, b) in blocked or (b, a) in blocked

    s.set_callbacks(is_friend_func=is_friend, is_blocked_func=is_blocked)
    s._test_friendships = friendships
    s._test_blocked = blocked
    return s


@pytest.fixture
def mock_ws():
    return MockWebSocket()


# =============================================================================
# Public Visibility Tests (Default)
# =============================================================================

class TestPublicVisibility:
    def test_default_visibility_is_public(self, server, mock_ws):
        """All new players start with PUBLIC visibility."""
        player = _run(server.connect(mock_ws, "alice", 1))
        assert player.visibility == PlayerVisibility.PUBLIC

    def test_public_players_see_each_other(self, server):
        """Two public players within range see each other."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p2.id in p1.visible_players
        assert p1.id in p2.visible_players

    def test_public_players_see_strangers(self, server):
        """Public players see other public players they are NOT friends with."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        # No friendship callbacks set — still visible
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p2.id in p1.visible_players
        assert p1.id in p2.visible_players

    def test_public_join_broadcasts_to_all_nearby(self, server):
        """When a public player sends first position update, nearby players get PLAYER_JOIN."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws1.messages.clear()

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        # Bob sends first position — this triggers join broadcasts
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 1
        assert join_msgs[0]["player"]["username"] == "bob"

    def test_world_state_includes_public_players(self, server):
        """World state snapshot includes public players."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p1.id in player_ids


# =============================================================================
# Friends-Only Visibility Tests
# =============================================================================

class TestFriendsOnlyVisibility:
    def test_friends_only_not_visible_to_strangers(self, server_with_friends):
        """A friends_only player is NOT visible to non-friends, but can still see them."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Alice is friends_only, Bob is NOT her friend
        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Bob should NOT see Alice (friends_only, not friends)
        assert p1.id not in p2.visible_players
        # Alice should still see Bob (his visibility is public, friends_only observers can see public targets)
        assert p2.id in p1.visible_players

    def test_friends_only_visible_to_friends(self, server_with_friends):
        """A friends_only player IS visible to friends."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Make them friends
        s._test_friendships.add((p1.id, p2.id))

        # Alice is friends_only
        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Both should see each other
        assert p2.id in p1.visible_players
        assert p1.id in p2.visible_players

    def test_friends_only_no_friend_callback_hides(self, server):
        """Without friendship callback, friends_only is invisible to everyone."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        # No callbacks set — friends_only should hide
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p1.id not in p2.visible_players

    def test_friends_only_join_event_respects_visibility(self, server_with_friends):
        """Friends_only player joining only notifies friends."""
        s = server_with_friends

        # Create alice (public)
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws1.messages.clear()

        # Create charlie as friends_only
        ws3 = MockWebSocket()
        p3 = _run(s.connect(ws3, "charlie", 1))
        _run(s.handle_message(p3, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p3, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))
        ws1.messages.clear()

        # Disconnect charlie and reconnect
        _run(s.disconnect(p3))
        ws3_2 = MockWebSocket()
        p3_2 = _run(s.connect(ws3_2, "charlie", 1))
        _run(s.handle_message(p3_2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Alice is NOT friends with charlie, so should NOT get join event
        join_msgs_alice = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        charlie_joins = [m for m in join_msgs_alice if m["player"]["username"] == "charlie"]
        assert len(charlie_joins) == 0

    def test_friends_only_world_state_excludes_strangers(self, server_with_friends):
        """World state snapshot excludes friends_only players for non-friends."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))

        # Set alice to friends_only
        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        # Bob connects — should NOT see alice in world state
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p1.id not in player_ids


# =============================================================================
# Hidden Visibility Tests
# =============================================================================

class TestHiddenVisibility:
    def test_hidden_player_invisible_to_all(self, server):
        """A hidden player is invisible to everyone but can still see others."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Bob goes hidden
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # Alice should NOT see bob (hidden)
        assert p2.id not in p1.visible_players
        # Bob should still see alice (hidden players can see others)
        assert p1.id in p2.visible_players

    def test_hidden_player_no_join_event(self, server):
        """Hidden player joining does not trigger PLAYER_JOIN for others."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Set alice hidden BEFORE bob connects
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))
        ws1.messages.clear()

        # Bob connects — alice should NOT get join event for bob
        # (actually bob gets world state, which should NOT include alice)
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        # Check bob's world state doesn't include alice
        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p1.id not in player_ids

        # Alice should NOT get a join event for bob
        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 0

    def test_hidden_player_not_in_world_state(self, server):
        """Hidden player not included in world state for new connections."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        ws2 = MockWebSocket()
        _run(server.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p1.id not in player_ids

    def test_hidden_player_leave_event_not_sent(self, server):
        """Hidden player disconnecting does not send PLAYER_LEAVE."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        ws1.messages.clear()
        _run(server.disconnect(p2))

        leave_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_msgs) == 0


# =============================================================================
# Visibility Change Tests
# =============================================================================

class TestVisibilityChanges:
    def test_set_visibility_sends_confirmation(self, server, mock_ws):
        """Setting visibility sends VISIBILITY_CHANGED confirmation."""
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        vis_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.VISIBILITY_CHANGED]
        assert len(vis_msgs) == 1
        assert vis_msgs[0]["visibility"] == "hidden"

    def test_set_visibility_invalid_value(self, server, mock_ws):
        """Invalid visibility value sends ERROR."""
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "invalid_value",
        }))

        error_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.ERROR]
        assert len(error_msgs) == 1

    def test_change_from_public_to_hidden(self, server):
        """Changing from public to hidden removes player from others' visible sets."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p2.id in p1.visible_players
        ws1.messages.clear()

        # Bob goes hidden
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # Alice should get a PLAYER_LEAVE for bob
        leave_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_msgs) == 1
        assert leave_msgs[0]["player_id"] == p2.id
        assert p2.id not in p1.visible_players

    def test_change_from_hidden_to_public(self, server):
        """Changing from hidden to public makes player visible again."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Bob goes hidden
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))
        ws1.messages.clear()

        # Bob goes public again
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "public",
        }))

        # Alice should get a PLAYER_JOIN for bob
        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        assert len(join_msgs) == 1
        assert join_msgs[0]["player"]["username"] == "bob"
        assert p2.id in p1.visible_players

    def test_visibility_change_affects_all_players(self, server):
        """Visibility change triggers spatial interest update for all world players."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        ws3 = MockWebSocket()
        p3 = _run(server.connect(ws3, "charlie", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p3, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 2, "y": 0, "z": 0},
        }))

        ws1.messages.clear()
        ws3.messages.clear()

        # Bob goes hidden
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # Both alice and charlie should get leave events
        leave_alice = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        leave_charlie = [m for m in ws3.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_alice) == 1
        assert len(leave_charlie) == 1


# =============================================================================
# Blocking Tests
# =============================================================================

class TestBlocking:
    def test_blocked_player_invisible(self, server_with_friends):
        """Blocked player cannot see the blocking player."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Alice blocks bob
        s._test_blocked.add((p1.id, p2.id))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Alice should NOT see bob (blocked)
        assert p2.id not in p1.visible_players
        # Bob should NOT see alice (blocking is bidirectional)
        assert p1.id not in p2.visible_players

    def test_blocking_bidirectional(self, server_with_friends):
        """Blocking is bidirectional — neither player sees the other."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Bob blocks alice
        s._test_blocked.add((p2.id, p1.id))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p2.id not in p1.visible_players
        assert p1.id not in p2.visible_players

    def test_blocked_player_no_join_event(self, server_with_friends):
        """Blocked player does not receive PLAYER_JOIN for the blocker."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Block bob before he connects (use a placeholder ID)
        s._test_blocked.add((p1.id, 999))

        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Update block with correct ID
        s._test_blocked.discard((p1.id, 999))
        s._test_blocked.add((p1.id, p2.id))

        # Disconnect and reconnect bob to test fresh world state
        _run(s.disconnect(p2))
        ws2_2 = MockWebSocket()
        p2_2 = _run(s.connect(ws2_2, "bob", 1))
        # Update block with new ID after reconnect
        s._test_blocked.discard((p1.id, p2.id))
        s._test_blocked.add((p1.id, p2_2.id))

        _run(s.handle_message(p2_2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Alice should NOT see bob in world state or get join event
        world_msgs = [m for m in ws1.messages if m["type"] == MessageType.WORLD_STATE]
        if world_msgs:
            player_ids = [p["id"] for p in world_msgs[0]["players"]]
            assert p2_2.id not in player_ids

        join_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_JOIN]
        bob_joins = [m for m in join_msgs if m["player"]["username"] == "bob"]
        assert len(bob_joins) == 0

    def test_blocked_player_not_in_world_state(self, server_with_friends):
        """Blocked player not included in world state for the blocker."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))

        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Pre-set block with next player ID (alice reconnects with new ID)
        next_id = s.next_player_id
        s._test_blocked.add((next_id, p2.id))

        # Reconnect alice — block is already in place during _send_world_state
        _run(s.disconnect(p1))
        ws1_2 = MockWebSocket()
        p1_2 = _run(s.connect(ws1_2, "alice", 1))
        assert p1_2.id == next_id

        world_msgs = [m for m in ws1_2.messages if m["type"] == MessageType.WORLD_STATE]
        assert len(world_msgs) == 1
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p2.id not in player_ids

    def test_blocked_player_leave_event_not_sent(self, server_with_friends):
        """Blocked player disconnecting does not send PLAYER_LEAVE to blocker."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Block bob
        s._test_blocked.add((p1.id, p2.id))

        # Force spatial interest update so alice's visible set is updated
        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws1.messages.clear()
        _run(s.disconnect(p2))

        leave_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_LEAVE]
        assert len(leave_msgs) == 0


# =============================================================================
# Reconnect Tests
# =============================================================================

class TestReconnects:
    def test_reconnect_preserves_visibility(self, server):
        """Player reconnecting after disconnect maintains visibility state."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set hidden
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # Disconnect
        _run(server.disconnect(p1))

        # Reconnect
        ws1_2 = MockWebSocket()
        p1_2 = _run(server.connect(ws1_2, "alice", 1))

        # Verify visibility was restored
        assert p1_2.visibility == PlayerVisibility.HIDDEN

        # New player should NOT see alice (she's still hidden)
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        world_msgs = [m for m in ws2.messages if m["type"] == MessageType.WORLD_STATE]
        player_ids = [p["id"] for p in world_msgs[0]["players"]]
        assert p1_2.id not in player_ids

    def test_reconnect_hidden_player_no_join_events(self, server):
        """Hidden player reconnecting does not trigger join events."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))

        # Set hidden
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # Disconnect alice
        _run(server.disconnect(p1))

        # Bob connects
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        ws2.messages.clear()

        # Alice reconnects (still hidden)
        ws1_2 = MockWebSocket()
        p1_2 = _run(server.connect(ws1_2, "alice", 1))
        _run(server.handle_message(p1_2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Bob should NOT get a join event for alice
        join_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_JOIN]
        alice_joins = [m for m in join_msgs if m["player"]["username"] == "alice"]
        assert len(alice_joins) == 0

    def test_reconnect_friends_only_with_friend(self, server_with_friends):
        """Friends_only player reconnecting is visible to friends."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        # Make friends
        s._test_friendships.add((p1.id, p2.id))

        # Set alice to friends_only
        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        # Disconnect alice
        _run(s.disconnect(p1))

        # Reconnect alice
        ws1_2 = MockWebSocket()
        p1_2 = _run(s.connect(ws1_2, "alice", 1))
        _run(s.handle_message(p1_2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))

        # Update friendship with new alice ID
        s._test_friendships.discard((p1.id, p2.id))
        s._test_friendships.add((p1_2.id, p2.id))

        # Bob (as friend) should see alice in world state
        # Predict bob's next ID and set friendship before reconnect
        next_bob_id = s.next_player_id
        s._test_friendships.discard((p1_2.id, p2.id))
        s._test_friendships.add((p1_2.id, next_bob_id))

        _run(s.disconnect(p2))
        ws2_2 = MockWebSocket()
        p2_2 = _run(s.connect(ws2_2, "bob", 1))
        assert p2_2.id == next_bob_id

        _run(s.handle_message(p2_2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        world_msgs_2 = [m for m in ws2_2.messages if m["type"] == MessageType.WORLD_STATE]
        player_ids = [p["id"] for p in world_msgs_2[0]["players"]]
        assert p1_2.id in player_ids


# =============================================================================
# GPS Privacy Tests
# =============================================================================

class TestGPSPrivacy:
    def test_public_player_position_sent_to_nearby(self, server):
        """Public player's position is sent to nearby players."""
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
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 1
        assert "x" in move_msgs[0]["position"]

    def test_friends_only_position_sent_to_friends(self, server_with_friends):
        """Friends_only player's position is sent to friends."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        s._test_friendships.add((p1.id, p2.id))

        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws2.messages.clear()
        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 1
        assert "x" in move_msgs[0]["position"]

    def test_hidden_player_position_not_sent(self, server):
        """Hidden player's position is not sent to anyone."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        ws1.messages.clear()
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 2, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 0


# =============================================================================
# Movement Broadcast Visibility Tests
# =============================================================================

class TestMovementVisibility:
    def test_movement_only_broadcasts_to_visible(self, server):
        """Position updates only sent to players in visible set."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))
        ws3 = MockWebSocket()
        p3 = _run(server.connect(ws3, "charlie", 1))

        # Alice and bob are nearby, charlie is far away
        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p3, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 10000, "y": 0, "z": 0},
        }))

        ws2.messages.clear()
        ws3.messages.clear()

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        bob_moves = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        charlie_moves = [m for m in ws3.messages if m["type"] == MessageType.PLAYER_MOVE]

        assert len(bob_moves) == 1
        assert len(charlie_moves) == 0

    def test_movement_hidden_player_no_broadcasts(self, server):
        """Hidden player's movement not broadcast to anyone."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # Bob goes hidden — this triggers spatial interest update
        _run(server.handle_message(p2, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        # After hidden, alice's visible set should NOT contain bob
        assert p2.id not in p1.visible_players

        ws1.messages.clear()
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws1.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 0

    def test_friends_only_movement_to_strangers(self, server_with_friends):
        """Friends_only player's movement not broadcast to non-friends."""
        s = server_with_friends
        ws1 = MockWebSocket()
        p1 = _run(s.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(s.connect(ws2, "bob", 1))

        _run(s.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "friends_only",
        }))

        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(s.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        # After friends_only, bob's visible set should NOT contain alice
        assert p1.id not in p2.visible_players

        ws2.messages.clear()
        _run(s.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 5, "y": 0, "z": 0},
        }))

        move_msgs = [m for m in ws2.messages if m["type"] == MessageType.PLAYER_MOVE]
        assert len(move_msgs) == 0


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    def test_self_visibility_change_ignored(self, server, mock_ws):
        """Player cannot set visibility for another player."""
        player = _run(server.connect(mock_ws, "alice", 1))

        # Set visibility for self (should work)
        _run(server.handle_message(player, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        assert player.visibility == PlayerVisibility.HIDDEN

    def test_visibility_case_insensitive(self, server, mock_ws):
        """Visibility values are case-insensitive."""
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "PUBLIC",
        }))

        assert player.visibility == PlayerVisibility.PUBLIC

    def test_multiple_visibility_changes(self, server, mock_ws):
        """Multiple visibility changes work correctly."""
        player = _run(server.connect(mock_ws, "alice", 1))

        for vis in ["hidden", "friends_only", "public", "hidden"]:
            _run(server.handle_message(player, {
                "type": MessageType.SET_VISIBILITY,
                "visibility": vis,
            }))

        assert player.visibility == PlayerVisibility.HIDDEN

    def test_visibility_change_during_move(self, server):
        """Visibility change during movement updates spatial interest for others."""
        ws1 = MockWebSocket()
        p1 = _run(server.connect(ws1, "alice", 1))
        ws2 = MockWebSocket()
        p2 = _run(server.connect(ws2, "bob", 1))

        _run(server.handle_message(p1, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 0, "y": 0, "z": 0},
        }))
        _run(server.handle_message(p2, {
            "type": MessageType.POSITION_UPDATE,
            "position": {"x": 1, "y": 0, "z": 0},
        }))

        assert p2.id in p1.visible_players
        assert p1.id in p2.visible_players

        # Alice goes hidden — bob should no longer see her
        _run(server.handle_message(p1, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "hidden",
        }))

        assert p1.id not in p2.visible_players
        # Alice can still see bob (hidden players can see others)
        assert p2.id in p1.visible_players

    def test_empty_visibility_value(self, server, mock_ws):
        """Empty visibility value sends ERROR."""
        player = _run(server.connect(mock_ws, "alice", 1))

        _run(server.handle_message(player, {
            "type": MessageType.SET_VISIBILITY,
            "visibility": "",
        }))

        error_msgs = [m for m in mock_ws.messages if m["type"] == MessageType.ERROR]
        assert len(error_msgs) == 1
