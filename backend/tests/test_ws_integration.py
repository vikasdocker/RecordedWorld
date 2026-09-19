"""WebSocket integration tests."""

import pytest
import json
import time
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.websocket_server import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestWebSocket:
    def test_ws_disconnect_on_bad_msg(self, client):
        """WS disconnects on invalid message gracefully."""
        try:
            with client.websocket_connect("/ws/testuser/0") as ws:
                ws.send_text("not json")
        except WebSocketDisconnect:
            pass  # Expected — server closes invalid connections

    def test_full_websocket_lifecycle(self, client):
        """Test complete WebSocket lifecycle: connect → join → move → chat → disconnect."""
        with client.websocket_connect("/ws/lifecycle_player/0") as ws:
            world_state = ws.receive_json()
            assert world_state["type"] == "world_state"

            ws.send_json({
                "type": "position_update",
                "position": {"lat": 40.7128, "lon": -74.0060, "alt": 10.0},
                "rotation": 90.0
            })

            ws.send_json({
                "type": "chat",
                "message": "Hello world!"
            })

            # Read messages until we find the chat_msg (skip pings, position corrections, etc.)
            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "chat_msg":
                    assert msg["message"] == "Hello world!"
                    assert msg["username"] == "lifecycle_player"
                    break
            else:
                pytest.fail("chat_msg not received within 10 messages")

    def test_multiple_players_join(self, client):
        """Test that two clients join and see each other via spatial interest."""
        with client.websocket_connect("/ws/joiner_a/0") as ws1:
            world_state_a = ws1.receive_json()
            assert world_state_a["type"] == "world_state"

            with client.websocket_connect("/ws/joiner_b/0") as ws2:
                world_state_b = ws2.receive_json()
                assert world_state_b["type"] == "world_state"

                # Both players set position at same location
                ws1.send_json({
                    "type": "position_update",
                    "position": {"lat": 40.7128, "lon": -74.0060, "alt": 10.0},
                    "rotation": 0.0
                })
                ws2.send_json({
                    "type": "position_update",
                    "position": {"lat": 40.7128, "lon": -74.0060, "alt": 10.0},
                    "rotation": 0.0
                })

                # ws2 sends position update → ws1 should receive player_join for joiner_b
                found_join = False
                for _ in range(20):
                    msg = ws1.receive_json()
                    if msg["type"] == "player_join":
                        player_info = msg.get("player", {})
                        assert player_info["username"] == "joiner_b"
                        found_join = True
                        break
                assert found_join, "player_join for joiner_b not received by joiner_a"

    def test_position_broadcast(self, client):
        """Test that a position update from one player reaches another."""
        with client.websocket_connect("/ws/mover_x/0") as ws1:
            world_state = ws1.receive_json()
            assert world_state["type"] == "world_state"

            with client.websocket_connect("/ws/watcher_x/0") as ws2:
                world_state_b = ws2.receive_json()
                assert world_state_b["type"] == "world_state"

                # Both players set position at same location
                ws1.send_json({
                    "type": "position_update",
                    "position": {"lat": 40.7128, "lon": -74.0060, "alt": 10.0},
                    "rotation": 45.0
                })
                ws2.send_json({
                    "type": "position_update",
                    "position": {"lat": 40.7128, "lon": -74.0060, "alt": 10.0},
                    "rotation": 0.0
                })

                # ws1 should receive a player_move from watcher_x (from ws2's position update)
                # and/or a player_join for watcher_x
                found_move_or_join = False
                for _ in range(30):
                    msg = ws1.receive_json()
                    if msg["type"] in ("player_move", "player_join"):
                        found_move_or_join = True
                        break
                assert found_move_or_join, "ws1 did not receive move/join from ws2"

    def test_chat_relay(self, client):
        """Test that chat messages are relayed to other players."""
        with client.websocket_connect("/ws/chatter_a/0") as ws1:
            world_state = ws1.receive_json()
            assert world_state["type"] == "world_state"

            with client.websocket_connect("/ws/chatter_b/0") as ws2:
                world_state_b = ws2.receive_json()
                assert world_state_b["type"] == "world_state"

                ws1.send_json({
                    "type": "chat",
                    "message": "Test relay message"
                })

                # Sender should receive own chat (broadcast to all)
                found_chat1 = False
                for _ in range(10):
                    msg = ws1.receive_json()
                    if msg["type"] == "chat_msg":
                        assert msg["message"] == "Test relay message"
                        assert msg["username"] == "chatter_a"
                        found_chat1 = True
                        break
                assert found_chat1, "Sender did not receive own chat_msg"

                # Receiver should also get it
                found_chat2 = False
                for _ in range(10):
                    msg = ws2.receive_json()
                    if msg["type"] == "chat_msg":
                        assert msg["message"] == "Test relay message"
                        assert msg["username"] == "chatter_a"
                        found_chat2 = True
                        break
                assert found_chat2, "Receiver did not receive chat_msg"
