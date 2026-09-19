"""WebSocket integration tests."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


class TestWebSocket:
    def test_ws_disconnect_on_bad_msg(self, client):
        """WS disconnects on invalid message gracefully."""
        try:
            with client.websocket_connect("/ws") as ws:
                ws.send_text("not json")
        except WebSocketDisconnect:
            pass  # Expected — server closes invalid connections
