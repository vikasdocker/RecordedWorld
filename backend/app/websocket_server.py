"""
WebSocket server for real-time multiplayer with spatial interest management.

Features:
- Player presence with heartbeat
- Spatial interest management (only sync nearby players)
- Disconnect/reconnect handling
- Position interpolation data
- World/chat/voice channels
"""

import asyncio
import json
import math
import time
from typing import Dict, Set, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.core.geospatial import haversine_distance, WGS84Coordinate


class PlayerVisibility(str, Enum):
    """Player visibility modes for multiplayer."""
    PUBLIC = "public"          # Default: visible to all nearby players
    FRIENDS_ONLY = "friends_only"  # Only visible to friends
    HIDDEN = "hidden"          # Invisible to everyone


class MessageType(str, Enum):
    # Client -> Server
    JOIN = "join"
    POSITION_UPDATE = "position_update"
    CHAT = "chat"
    DM = "dm"
    VOICE = "voice"
    WORLD_LIST = "world_list"
    PONG = "pong"
    SET_VISIBILITY = "set_visibility"
    SET_AVATAR = "set_avatar"
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPT = "friend_accept"

    # Server -> Client
    PLAYER_JOIN = "player_join"
    PLAYER_LEAVE = "player_leave"
    PLAYER_MOVE = "player_move"
    POSITION_CORRECTION = "position_correction"
    CHAT_MSG = "chat_msg"
    DM_MSG = "dm_msg"
    VOICE_START = "voice_start"
    VOICE_STOP = "voice_stop"
    WORLD_LIST_RESP = "world_list_resp"
    PING = "ping"
    WORLD_STATE = "world_state"
    ERROR = "error"
    VISIBILITY_CHANGED = "visibility_changed"
    FRIEND_ONLINE = "friend_online"
    FRIEND_OFFLINE = "friend_offline"


class PlayerState(BaseModel):
    id: int
    username: str
    position: dict  # {lat, lon, alt} or {x, y, z}
    rotation: float = 0.0
    world_id: int = 0
    visibility: str = "public"
    connected_at: float = 0.0
    last_heartbeat: float = 0.0
    last_position_update: float = 0.0
    is_moving: bool = False


@dataclass
class Player:
    id: int
    username: str
    ws: WebSocket
    position: dict = field(default_factory=lambda: {"lat": 0.0, "lon": 0.0, "alt": 0.0})
    rotation: float = 0.0
    velocity: dict = field(default_factory=lambda: {"x": 0.0, "y": 0.0, "z": 0.0})
    world_id: int = 0
    visibility: PlayerVisibility = PlayerVisibility.PUBLIC
    color: str = "#00ff88"  # hex color for avatar
    connected_at: float = 0.0
    last_heartbeat: float = 0.0
    last_position_update: float = 0.0
    is_moving: bool = False
    # Spatial interest: which players this player can see
    visible_players: Set[int] = field(default_factory=set)
    # Server-authoritative state
    server_position: dict = field(default_factory=lambda: {"lat": 0.0, "lon": 0.0, "alt": 0.0})
    last_valid_position: dict = field(default_factory=lambda: {"lat": 0.0, "lon": 0.0, "alt": 0.0})


class MultiplayerServer:
    """
    Production WebSocket server with spatial interest management.

    Only syncs players that are within a configurable radius of each other.
    Uses heartbeat to detect dead connections.
    Supports player visibility modes: public, friends_only, hidden.
    """

    def __init__(
        self,
        heartbeat_interval: float = 30.0,
        heartbeat_timeout: float = 60.0,
        view_radius_meters: float = 500.0,
        position_update_rate_limit: float = 0.1,
        max_speed_ms: float = 10.0,  # max movement speed in meters/second
        max_position_jump_meters: float = 50.0,  # max allowed position jump
    ):
        self.players: Dict[int, Player] = {}
        self.worlds: Dict[int, Set[int]] = {}
        self.next_player_id = 1
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.view_radius_meters = view_radius_meters
        self.position_update_rate_limit = position_update_rate_limit
        self.max_speed_ms = max_speed_ms
        self.max_position_jump_meters = max_position_jump_meters
        self._heartbeat_task: Optional[asyncio.Task] = None
        # Callbacks for friendship/blocking checks (injected by caller)
        self._is_friend_func = None
        self._is_blocked_func = None
        # Cache visibility state across reconnects (username -> visibility)
        self._player_visibility_cache: Dict[str, PlayerVisibility] = {}
        self._player_color_cache: Dict[str, str] = {}

    def set_callbacks(
        self,
        is_friend_func=None,
        is_blocked_func=None,
    ):
        """
        Set callback functions for friendship/blocking checks.

        is_friend_func(user_a_id: int, user_b_id: int) -> bool
        is_blocked_func(user_a_id: int, user_b_id: int) -> bool
        """
        self._is_friend_func = is_friend_func
        self._is_blocked_func = is_blocked_func

    async def start(self):
        """Start background tasks."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self):
        """Stop background tasks."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def connect(self, ws: WebSocket, username: str, world_id: int = 0) -> Player:
        """Accept connection and register player."""
        await ws.accept()
        now = time.time()

        # Restore cached visibility or default to PUBLIC
        cached_visibility = self._player_visibility_cache.get(username, PlayerVisibility.PUBLIC)
        cached_color = self._player_color_cache.get(username, "#00ff88")

        player = Player(
            id=self.next_player_id,
            username=username,
            ws=ws,
            world_id=world_id,
            visibility=cached_visibility,
            color=cached_color,
            connected_at=now,
            last_heartbeat=now,
        )
        self.next_player_id += 1
        self.players[player.id] = player

        if world_id not in self.worlds:
            self.worlds[world_id] = set()
        self.worlds[world_id].add(player.id)

        # Send world state to new player (respects visibility)
        await self._send_world_state(player)

        # Don't broadcast join events here — they happen on first POSITION_UPDATE
        # This lets players set visibility before appearing to others

        return player

    async def disconnect(self, player: Player):
        """Handle player disconnect."""
        # Cache visibility and color state for reconnect
        self._player_visibility_cache[player.username] = player.visibility
        self._player_color_cache[player.username] = player.color

        if player.id in self.players:
            del self.players[player.id]
        if player.world_id in self.worlds:
            self.worlds[player.world_id].discard(player.id)

        # Notify players who could see this disconnecting player
        for pid in list(self.worlds.get(player.world_id, set())):
            other = self.players.get(pid)
            if other:
                # Check if the other player had this player in their visible set
                if player.id in other.visible_players:
                    other.visible_players.discard(player.id)
                    try:
                        await other.ws.send_json({
                            "type": MessageType.PLAYER_LEAVE,
                            "player_id": player.id,
                            "player_count": len(self.worlds.get(player.world_id, set())),
                        })
                    except Exception:
                        pass

    async def handle_message(self, player: Player, data: dict):
        """Route incoming message by type."""
        msg_type = data.get("type")

        if msg_type == MessageType.POSITION_UPDATE:
            await self._handle_position_update(player, data)

        elif msg_type == MessageType.CHAT:
            await self._handle_chat(player, data)

        elif msg_type == MessageType.VOICE:
            await self._handle_voice(player, data)

        elif msg_type == MessageType.WORLD_LIST:
            await self._handle_world_list(player)

        elif msg_type == MessageType.PONG:
            player.last_heartbeat = time.time()

        elif msg_type == MessageType.SET_VISIBILITY:
            await self._handle_set_visibility(player, data)

        elif msg_type == MessageType.SET_AVATAR:
            await self._handle_set_avatar(player, data)

        elif msg_type == MessageType.DM:
            await self._handle_dm(player, data)

    def _can_see_player(self, observer: Player, target: Player) -> bool:
        """
        Determine if observer can see target based on visibility and blocking.

        Rules:
        1. Blocked players cannot see each other (bidirectional)
        2. Hidden targets are invisible to everyone
        3. Friends_only targets are only visible to friends
        4. Public targets are visible to all (default)
        """
        if observer.id == target.id:
            return False

        # Blocking check: blocked players cannot see each other
        if self._is_blocked_func:
            try:
                if self._is_blocked_func(observer.id, target.id):
                    return False
            except Exception:
                pass

        # Target visibility rules (what determines who can see them)
        if target.visibility == PlayerVisibility.HIDDEN:
            return False

        if target.visibility == PlayerVisibility.FRIENDS_ONLY:
            if not self._is_friend_func:
                return False
            try:
                return self._is_friend_func(observer.id, target.id)
            except Exception:
                return False

        # Public: visible to all (default)
        return True

    async def _handle_set_visibility(self, player: Player, data: dict):
        """Process visibility change request from client."""
        new_vis = data.get("visibility", "").lower()
        valid_visibilities = {v.value for v in PlayerVisibility}
        if new_vis not in valid_visibilities:
            await player.ws.send_json({
                "type": MessageType.ERROR,
                "detail": f"Invalid visibility. Must be one of: {valid_visibilities}",
            })
            return

        old_visibility = player.visibility
        player.visibility = PlayerVisibility(new_vis)

        # Confirm to the player
        await player.ws.send_json({
            "type": MessageType.VISIBILITY_CHANGED,
            "visibility": new_vis,
        })

        # Update spatial interest for all players in the world since visibility changed
        await self._update_all_spatial_interest(player.world_id, changed_player=player)

    async def _handle_set_avatar(self, player: Player, data: dict):
        """Process avatar customization request from client."""
        color = data.get("color", "").strip()
        # Validate hex color format (#RRGGBB or #RGB)
        if not color or not (color.startswith("#") and len(color) in (4, 7)):
            await player.ws.send_json({
                "type": MessageType.ERROR,
                "detail": "Invalid color. Must be hex format like #ff0000",
            })
            return

        player.color = color

        # Confirm to the player
        await player.ws.send_json({
            "type": "avatar_changed",
            "color": color,
        })

    async def _handle_position_update(self, player: Player, data: dict):
        """Process position update with rate limiting, speed validation, and spatial interest."""
        now = time.time()

        # Rate limiting
        if now - player.last_position_update < self.position_update_rate_limit:
            return

        new_position = data.get("position", player.position)
        new_rotation = data.get("rotation", player.rotation)

        # Initialize on first update
        is_first_update = player.last_position_update == 0

        if is_first_update:
            # First position update — accept it directly and initialize
            player.position = new_position
            player.server_position = new_position.copy()
            player.last_valid_position = new_position.copy()
            player.velocity = {"x": 0, "y": 0, "z": 0}
        else:
            # Server-authoritative movement validation
            is_valid, corrected_position = self._validate_movement(
                player, new_position, now
            )

            if not is_valid:
                await player.ws.send_json({
                    "type": MessageType.POSITION_CORRECTION,
                    "position": corrected_position,
                    "reason": "speed_exceeded",
                })
                player.position = corrected_position
                player.server_position = corrected_position.copy()
            else:
                dt = now - player.last_position_update
                if dt > 0:
                    velocity = self._calculate_velocity(player.position, new_position, dt)
                    player.velocity = velocity

                player.position = new_position
                player.server_position = new_position.copy()
                player.last_valid_position = new_position.copy()

        player.rotation = new_rotation
        player.last_position_update = now
        player.is_moving = True

        await self._update_all_spatial_interest(player.world_id)

        await self._broadcast_to_visible(player, {
            "type": MessageType.PLAYER_MOVE,
            "player_id": player.id,
            "position": player.position,
            "rotation": player.rotation,
            "velocity": player.velocity,
            "color": player.color,
            "timestamp": now,
            "server_tick": now,
        })

    async def _handle_chat(self, player: Player, data: dict):
        """Broadcast chat message to all players in world."""
        message = data.get("message", "").strip()
        if not message:
            return

        await self.broadcast(player.world_id, {
            "type": MessageType.CHAT_MSG,
            "player_id": player.id,
            "username": player.username,
            "message": message[:500],  # limit message length
            "timestamp": time.time(),
        })

    async def _handle_dm(self, player: Player, data: dict):
        """Send a direct message to a specific player by username."""
        target_username = data.get("to", "").strip()
        message = data.get("message", "").strip()
        if not target_username or not message:
            return

        # Find target player
        target = None
        for p in self.players.values():
            if p.username.lower() == target_username.lower() and p.id != player.id:
                target = p
                break

        if not target:
            await player.ws.send_json({
                "type": MessageType.ERROR,
                "detail": f"Player '{target_username}' not found or offline",
            })
            return

        # Send DM to target
        await target.ws.send_json({
            "type": MessageType.DM_MSG,
            "player_id": player.id,
            "username": player.username,
            "message": message[:500],
            "timestamp": time.time(),
        })

        # Confirm to sender
        await player.ws.send_json({
            "type": MessageType.DM_MSG,
            "player_id": player.id,
            "username": player.username,
            "message": message[:500],
            "to": target_username,
            "timestamp": time.time(),
        })

    async def _handle_voice(self, player: Player, data: dict):
        """Relay voice indicators to nearby players."""
        await self._broadcast_to_visible(player, {
            "type": MessageType.VOICE_START if data.get("active") else MessageType.VOICE_STOP,
            "player_id": player.id,
        })

    async def _handle_world_list(self, player: Player):
        """Send list of available worlds."""
        worlds = []
        for wid, pids in self.worlds.items():
            worlds.append({
                "id": wid,
                "player_count": len(pids),
                "name": f"World {wid}",
            })
        await player.ws.send_json({
            "type": MessageType.WORLD_LIST_RESP,
            "worlds": worlds,
        })

    async def _update_all_spatial_interest(self, world_id: int, changed_player: Player = None):
        """
        Update spatial interest for all players in a world.

        If changed_player is provided, also update that player's own visible set
        (since their visibility changed, they need to recompute who they can see).
        """
        pids = list(self.worlds.get(world_id, set()))
        for pid in pids:
            player = self.players.get(pid)
            if player:
                await self._update_spatial_interest(player)

        # Also update the changed player's own visible set
        if changed_player and changed_player.id in self.worlds.get(world_id, set()):
            await self._update_spatial_interest(changed_player)

    async def _update_spatial_interest(self, player: Player):
        """
        Determine which players are visible to this player.
        Uses haversine for real-world coordinates or Euclidean for local.
        Respects player visibility modes and blocking.
        """
        visible = set()

        for pid, other in self.players.items():
            if pid == player.id:
                continue
            if other.world_id != player.world_id:
                continue

            # Check visibility and blocking rules
            if not self._can_see_player(player, other):
                continue

            # Calculate distance
            dist = self._calculate_distance(player.position, other.position)
            if dist <= self.view_radius_meters:
                visible.add(pid)

        # Detect newly visible players (send join events)
        newly_visible = visible - player.visible_players
        for pid in newly_visible:
            other = self.players.get(pid)
            if other:
                await player.ws.send_json({
                    "type": MessageType.PLAYER_JOIN,
                    "player": {
                        "id": other.id,
                        "username": other.username,
                        "position": other.position,
                        "color": other.color,
                        "visibility": other.visibility.value,
                    },
                })

        # Detect players leaving view (send leave events)
        left_view = player.visible_players - visible
        for pid in left_view:
            await player.ws.send_json({
                "type": MessageType.PLAYER_LEAVE,
                "player_id": pid,
            })

        player.visible_players = visible

    def _calculate_distance(self, pos_a: dict, pos_b: dict) -> float:
        """Calculate distance between two positions (meters)."""
        a_has_geo = "lat" in pos_a and "lon" in pos_a
        b_has_geo = "lat" in pos_b and "lon" in pos_b

        if a_has_geo and b_has_geo:
            coord_a = WGS84Coordinate(latitude=pos_a["lat"], longitude=pos_a["lon"])
            coord_b = WGS84Coordinate(latitude=pos_b["lat"], longitude=pos_b["lon"])
            return haversine_distance(coord_a, coord_b)

        if a_has_geo != b_has_geo:
            return float("inf")

        dx = pos_a.get("x", 0) - pos_b.get("x", 0)
        dy = pos_a.get("y", 0) - pos_b.get("y", 0)
        dz = pos_a.get("z", 0) - pos_b.get("z", 0)
        return (dx**2 + dy**2 + dz**2) ** 0.5

    def _validate_movement(
        self, player: Player, new_position: dict, timestamp: float
    ) -> Tuple[bool, dict]:
        """
        Validate player movement against server rules.

        Returns:
            (is_valid, corrected_position) - if invalid, corrected_position
            is where the server thinks the player should be
        """
        old_position = player.last_valid_position
        dt = timestamp - player.last_position_update if player.last_position_update > 0 else 0.1

        if dt <= 0:
            return True, new_position

        # Calculate distance moved
        distance = self._calculate_distance(old_position, new_position)

        # Check max position jump (teleport detection)
        if distance > self.max_position_jump_meters:
            return False, old_position

        # Check speed
        speed = distance / dt
        if speed > self.max_speed_ms:
            # Allow movement up to max speed
            max_distance = self.max_speed_ms * dt
            if distance > 0:
                # Interpolate to max allowed position
                ratio = max_distance / distance
                corrected = self._interpolate_position(old_position, new_position, ratio)
                return False, corrected

        return True, new_position

    def _interpolate_position(self, start: dict, end: dict, t: float) -> dict:
        """Interpolate between two positions by factor t (0..1)."""
        # Handle geographic coordinates
        if "lat" in start and "lon" in start:
            return {
                "lat": start["lat"] + (end["lat"] - start["lat"]) * t,
                "lon": start["lon"] + (end["lon"] - start["lon"]) * t,
                "alt": start.get("alt", 0) + (end.get("alt", 0) - start.get("alt", 0)) * t,
            }

        # Handle local coordinates
        return {
            "x": start.get("x", 0) + (end.get("x", 0) - start.get("x", 0)) * t,
            "y": start.get("y", 0) + (end.get("y", 0) - start.get("y", 0)) * t,
            "z": start.get("z", 0) + (end.get("z", 0) - start.get("z", 0)) * t,
        }

    def _calculate_velocity(self, old_pos: dict, new_pos: dict, dt: float) -> dict:
        """Calculate velocity vector between two positions."""
        if dt <= 0:
            return {"x": 0, "y": 0, "z": 0}

        # Geographic coordinates → approximate velocity in local frame
        if "lat" in old_pos and "lon" in old_pos:
            dlat = new_pos["lat"] - old_pos["lat"]
            dlon = new_pos["lon"] - old_pos["lon"]
            dalt = new_pos.get("alt", 0) - old_pos.get("alt", 0)
            # Approximate meters per degree
            avg_lat = (old_pos["lat"] + new_pos["lat"]) / 2
            m_per_deg_lat = 111132.92
            m_per_deg_lon = 111132.92 * math.cos(math.radians(avg_lat))
            return {
                "x": (dlon * m_per_deg_lon) / dt,
                "y": (dlat * m_per_deg_lat) / dt,
                "z": dalt / dt,
            }

        # Local coordinates
        return {
            "x": (new_pos.get("x", 0) - old_pos.get("x", 0)) / dt,
            "y": (new_pos.get("y", 0) - old_pos.get("y", 0)) / dt,
            "z": (new_pos.get("z", 0) - old_pos.get("z", 0)) / dt,
        }

    async def _broadcast_to_visible(self, player: Player, data: dict):
        """Send message only to players who can see the sender (visibility + distance)."""
        dead_players = []
        for pid in list(self.worlds.get(player.world_id, set())):
            if pid == player.id:
                continue
            target = self.players.get(pid)
            if not target:
                continue
            # Check visibility rules (blocking, hidden, friends_only)
            if not self._can_see_player(target, player):
                continue
            # Check distance
            dist = self._calculate_distance(target.position, player.position)
            if dist > self.view_radius_meters:
                continue
            try:
                await target.ws.send_json(data)
            except Exception:
                dead_players.append(pid)

        for pid in dead_players:
            self.worlds.get(player.world_id, set()).discard(pid)
            self.players.pop(pid, None)

    async def _send_world_state(self, player: Player):
        """Send current world state to newly connected player, respecting visibility."""
        players_in_world = []
        for pid in self.worlds.get(player.world_id, set()):
            p = self.players.get(pid)
            if p and p.id != player.id:
                # Only include players the connecting player can see
                if self._can_see_player(player, p):
                    players_in_world.append({
                        "id": p.id,
                        "username": p.username,
                        "position": p.position,
                        "rotation": p.rotation,
                        "color": p.color,
                        "visibility": p.visibility.value,
                    })

        await player.ws.send_json({
            "type": MessageType.WORLD_STATE,
            "world_id": player.world_id,
            "players": players_in_world,
            "player_count": len(self.worlds.get(player.world_id, set())),
        })

    async def broadcast(self, world_id: int, data: dict, exclude: int = None):
        """Broadcast message to all players in a world."""
        dead_players = []
        for pid in self.worlds.get(world_id, set()):
            if pid == exclude:
                continue
            player = self.players.get(pid)
            if player:
                try:
                    await player.ws.send_json(data)
                except Exception:
                    dead_players.append(pid)

        for pid in dead_players:
            self.worlds.get(world_id, set()).discard(pid)
            self.players.pop(pid, None)

    async def _heartbeat_loop(self):
        """Periodically ping players and disconnect stale connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                now = time.time()
                stale = []

                for pid, player in self.players.items():
                    if now - player.last_heartbeat > self.heartbeat_timeout:
                        stale.append(player)
                    else:
                        try:
                            await player.ws.send_json({
                                "type": MessageType.PING,
                                "timestamp": now,
                            })
                        except Exception:
                            stale.append(player)

                for player in stale:
                    await self.disconnect(player)

            except asyncio.CancelledError:
                break
            except Exception:
                continue

    def get_player_count(self) -> int:
        return len(self.players)

    def get_world_player_count(self, world_id: int) -> int:
        return len(self.worlds.get(world_id, set()))

    def get_player(self, player_id: int) -> Optional[Player]:
        return self.players.get(player_id)


app = FastAPI(title="Recorded World WebSocket Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

server = MultiplayerServer()


@app.on_event("startup")
async def startup():
    await server.start()


@app.on_event("shutdown")
async def shutdown():
    await server.stop()


@app.websocket("/ws/{username}/{world_id}")
async def websocket_endpoint(websocket: WebSocket, username: str, world_id: int = 0):
    player = await server.connect(websocket, username, world_id)
    try:
        while True:
            data = await websocket.receive_json()
            await server.handle_message(player, data)
    except WebSocketDisconnect:
        await server.disconnect(player)
    except Exception:
        await server.disconnect(player)


@app.get("/")
def root():
    return {"message": "Recorded World WebSocket Server", "players": server.get_player_count()}


@app.get("/health")
def health():
    return {"status": "healthy", "players": server.get_player_count()}


@app.get("/worlds")
def list_worlds():
    worlds = []
    for wid, pids in server.worlds.items():
        worlds.append({"id": wid, "player_count": len(pids)})
    return {"worlds": worlds}
