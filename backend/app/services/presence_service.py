"""
Presence Service — Online/Offline State and Activity Tracking

Tracks player online/offline/away status with last-seen timestamps,
activity monitoring, and friend-aware presence queries.

Integrates with MultiplayerService and FriendshipService.
"""

import time
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone


class PresenceState(str, Enum):
    """Player presence states."""
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"
    DO_NOT_DISTURB = "dnd"


@dataclass
class PlayerPresence:
    """Presence information for a single player."""
    player_id: int
    username: str
    state: PresenceState = PresenceState.OFFLINE
    last_seen: float = 0.0  # unix timestamp
    last_activity: float = 0.0  # last non-heartbeat activity
    connected_since: float = 0.0  # when current session started
    activity: str = ""  # "exploring", "building", "idle", ""
    world_id: int = 0
    party_id: Optional[str] = None
    status_text: str = ""  # custom status message

    def to_dict(self) -> dict:
        return {
            "player_id": self.player_id,
            "username": self.username,
            "state": self.state.value,
            "last_seen": self.last_seen,
            "last_activity": self.last_activity,
            "connected_since": self.connected_since,
            "activity": self.activity,
            "world_id": self.world_id,
            "party_id": self.party_id,
            "status_text": self.status_text,
            "seconds_since_seen": round(time.time() - self.last_seen) if self.last_seen else -1,
        }

    @property
    def is_online(self) -> bool:
        return self.state == PresenceState.ONLINE

    @property
    def is_available(self) -> bool:
        return self.state in (PresenceState.ONLINE, PresenceState.AWAY)


class PresenceService:
    """
    Tracks player online/offline/away status.

    - Players are ONLINE when connected via WebSocket
    - Players are OFFLINE when disconnected (with last_seen timestamp)
    - Players are AWAY after inactivity timeout
    - Players can set DO_NOT_DISTURB to suppress notifications
    """

    _presence: Dict[int, PlayerPresence] = {}  # player_id -> presence
    _username_index: Dict[str, int] = {}  # username -> player_id
    _away_timeout: float = 300.0  # 5 minutes of inactivity -> away
    _offline_expire: float = 86400.0  # 24 hours -> remove from tracking

    @classmethod
    def connect(cls, player_id: int, username: str, world_id: int = 0) -> PlayerPresence:
        """Mark player as online (called on WebSocket connect)."""
        now = time.time()
        presence = cls._presence.get(player_id)

        if presence:
            presence.state = PresenceState.ONLINE
            presence.connected_since = now
            presence.last_seen = now
            presence.last_activity = now
            presence.world_id = world_id
        else:
            presence = PlayerPresence(
                player_id=player_id,
                username=username,
                state=PresenceState.ONLINE,
                last_seen=now,
                last_activity=now,
                connected_since=now,
                world_id=world_id,
            )
            cls._presence[player_id] = presence
            cls._username_index[username.lower()] = player_id

        return presence

    @classmethod
    def disconnect(cls, player_id: int) -> Optional[PlayerPresence]:
        """Mark player as offline (called on WebSocket disconnect)."""
        presence = cls._presence.get(player_id)
        if not presence:
            return None

        now = time.time()
        presence.state = PresenceState.OFFLINE
        presence.last_seen = now
        presence.connected_since = 0
        presence.activity = ""
        return presence

    @classmethod
    def heartbeat(cls, player_id: int) -> Optional[PlayerPresence]:
        """Update last_seen on heartbeat. Returns presence if found."""
        presence = cls._presence.get(player_id)
        if presence:
            presence.last_seen = time.time()
            # Auto-set back to ONLINE if was AWAY and still receiving heartbeats
            if presence.state == PresenceState.AWAY:
                presence.state = PresenceState.ONLINE
        return presence

    @classmethod
    def update_activity(cls, player_id: int, activity: str) -> Optional[PlayerPresence]:
        """Update player's current activity (exploring, building, etc.)."""
        presence = cls._presence.get(player_id)
        if presence:
            presence.activity = activity
            presence.last_activity = time.time()
            presence.last_seen = time.time()
        return presence

    @classmethod
    def set_state(cls, player_id: int, state: PresenceState) -> Optional[PlayerPresence]:
        """Manually set presence state (online, away, dnd)."""
        presence = cls._presence.get(player_id)
        if presence:
            presence.state = state
            presence.last_seen = time.time()
        return presence

    @classmethod
    def set_status_text(cls, player_id: int, text: str) -> Optional[PlayerPresence]:
        """Set custom status text."""
        presence = cls._presence.get(player_id)
        if presence:
            presence.status_text = text[:100]  # limit length
        return presence

    @classmethod
    def set_party(cls, player_id: int, party_id: Optional[str]) -> Optional[PlayerPresence]:
        """Update player's party membership."""
        presence = cls._presence.get(player_id)
        if presence:
            presence.party_id = party_id
        return presence

    @classmethod
    def get_presence(cls, player_id: int) -> Optional[PlayerPresence]:
        """Get presence for a player."""
        return cls._presence.get(player_id)

    @classmethod
    def get_by_username(cls, username: str) -> Optional[PlayerPresence]:
        """Get presence by username."""
        player_id = cls._username_index.get(username.lower())
        if player_id is not None:
            return cls._presence.get(player_id)
        return None

    @classmethod
    def is_online(cls, player_id: int) -> bool:
        """Check if a player is currently online."""
        presence = cls._presence.get(player_id)
        return presence is not None and presence.state == PresenceState.ONLINE

    @classmethod
    def get_online_players(cls) -> List[PlayerPresence]:
        """Get all online players."""
        return [p for p in cls._presence.values() if p.state == PresenceState.ONLINE]

    @classmethod
    def get_online_count(cls) -> int:
        """Get count of online players."""
        return sum(1 for p in cls._presence.values() if p.state == PresenceState.ONLINE)

    @classmethod
    def get_friend_presences(
        cls,
        player_id: int,
        friend_ids: Set[int],
    ) -> List[PlayerPresence]:
        """Get presence for all online friends."""
        return [
            cls._presence[pid]
            for pid in friend_ids
            if pid in cls._presence and cls._presence[pid].is_online
        ]

    @classmethod
    def get_world_players(cls, world_id: int) -> List[PlayerPresence]:
        """Get all online players in a specific world."""
        return [
            p for p in cls._presence.values()
            if p.is_online and p.world_id == world_id
        ]

    @classmethod
    def check_away_timeout(cls) -> List[int]:
        """
        Check for players who should be marked AWAY due to inactivity.
        Returns list of player_ids that were transitioned to AWAY.
        """
        now = time.time()
        away_players = []
        for presence in cls._presence.values():
            if presence.state == PresenceState.ONLINE:
                idle_time = now - presence.last_activity
                if idle_time > cls._away_timeout:
                    presence.state = PresenceState.AWAY
                    away_players.append(presence.player_id)
        return away_players

    @classmethod
    def cleanup_stale(cls) -> List[int]:
        """
        Remove players who have been offline for too long.
        Returns list of removed player_ids.
        """
        now = time.time()
        to_remove = []
        for pid, presence in cls._presence.items():
            if presence.state == PresenceState.OFFLINE:
                if now - presence.last_seen > cls._offline_expire:
                    to_remove.append(pid)

        for pid in to_remove:
            presence = cls._presence.pop(pid)
            cls._username_index.pop(presence.username.lower(), None)

        return to_remove

    @classmethod
    def get_all_presence(cls) -> List[PlayerPresence]:
        """Get all tracked players."""
        return list(cls._presence.values())

    @classmethod
    def get_stats(cls) -> dict:
        """Get presence statistics."""
        states = {}
        for p in cls._presence.values():
            states[p.state.value] = states.get(p.state.value, 0) + 1
        return {
            "total_tracked": len(cls._presence),
            "online": states.get("online", 0),
            "away": states.get("away", 0),
            "offline": states.get("offline", 0),
            "dnd": states.get("dnd", 0),
        }

    @classmethod
    def clear(cls):
        """Clear all presence data (for testing)."""
        cls._presence.clear()
        cls._username_index.clear()
