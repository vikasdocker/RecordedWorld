"""
Multiplayer Service

WebSocket connection management and spatial interest.
"""

from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PlayerConnection:
    """A connected player's WebSocket state."""
    player_id: int
    username: str
    ws_id: str
    position: dict = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    rotation: float = 0.0
    velocity: float = 0.0
    color: str = "#00ff88"
    visibility: str = "public"
    connected_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.player_id,
            "username": self.username,
            "ws_id": self.ws_id,
            "position": self.position,
            "rotation": self.rotation,
            "velocity": self.velocity,
            "color": self.color,
            "visibility": self.visibility,
        }


class MultiplayerService:
    """Manages WebSocket connections and spatial interest."""

    _connections: Dict[str, PlayerConnection] = {}  # ws_id -> connection
    _player_connections: Dict[int, str] = {}  # player_id -> ws_id
    _color_cache: Dict[str, str] = {}  # username -> color
    _visibility_cache: Dict[str, str] = {}  # username -> visibility

    @classmethod
    def connect(
        cls,
        player_id: int,
        username: str,
        ws_id: str,
    ) -> PlayerConnection:
        """Register a new WebSocket connection."""
        # Restore cached state
        color = cls._color_cache.get(username, "#00ff88")
        visibility = cls._visibility_cache.get(username, "public")

        conn = PlayerConnection(
            player_id=player_id,
            username=username,
            ws_id=ws_id,
            color=color,
            visibility=visibility,
            connected_at=datetime.now(timezone.utc).isoformat(),
        )
        cls._connections[ws_id] = conn
        cls._player_connections[player_id] = ws_id
        return conn

    @classmethod
    def disconnect(cls, ws_id: str) -> Optional[PlayerConnection]:
        """Remove a WebSocket connection."""
        conn = cls._connections.pop(ws_id, None)
        if conn:
            cls._player_connections.pop(conn.player_id, None)
            # Cache state for reconnect
            cls._color_cache[conn.username] = conn.color
            cls._visibility_cache[conn.username] = conn.visibility
        return conn

    @classmethod
    def get_connection(cls, ws_id: str) -> Optional[PlayerConnection]:
        """Get connection by ws_id."""
        return cls._connections.get(ws_id)

    @classmethod
    def get_player_ws_id(cls, player_id: int) -> Optional[str]:
        """Get WebSocket ID for a player."""
        return cls._player_connections.get(player_id)

    @classmethod
    def update_position(cls, ws_id: str, position: dict, rotation: float = 0, velocity: float = 0):
        """Update player position."""
        conn = cls._connections.get(ws_id)
        if conn:
            conn.position = position
            conn.rotation = rotation
            conn.velocity = velocity

    @classmethod
    def set_color(cls, ws_id: str, color: str):
        """Set player color."""
        conn = cls._connections.get(ws_id)
        if conn:
            conn.color = color
            cls._color_cache[conn.username] = color

    @classmethod
    def set_visibility(cls, ws_id: str, visibility: str):
        """Set player visibility."""
        conn = cls._connections.get(ws_id)
        if conn:
            conn.visibility = visibility
            cls._visibility_cache[conn.username] = visibility

    @classmethod
    def get_visible_players(cls, player_id: int) -> List[PlayerConnection]:
        """Get all players visible to a given player."""
        viewer = None
        for conn in cls._connections.values():
            if conn.player_id == player_id:
                viewer = conn
                break
        if not viewer:
            return []

        visible = []
        for conn in cls._connections.values():
            if conn.player_id == player_id:
                continue  # skip self
            # Basic visibility check (full spatial interest done in websocket_server)
            if conn.visibility == "hidden":
                continue
            if conn.visibility == "friends_only":
                continue  # simplified — full check needs friendship service
            visible.append(conn)
        return visible

    @classmethod
    def get_all_connections(cls) -> List[PlayerConnection]:
        """Get all active connections."""
        return list(cls._connections.values())

    @classmethod
    def get_connection_count(cls) -> int:
        """Get number of active connections."""
        return len(cls._connections)

    @classmethod
    def get_player_color(cls, username: str) -> str:
        """Get cached color for a username."""
        return cls._color_cache.get(username, "#00ff88")

    @classmethod
    def get_player_visibility(cls, username: str) -> str:
        """Get cached visibility for a username."""
        return cls._visibility_cache.get(username, "public")
