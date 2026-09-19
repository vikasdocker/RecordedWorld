"""
Player Service

Player profile, presence, and visibility management.
"""

from typing import Optional, Dict, Set
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.user import User


class PlayerService:
    """Handles player state, visibility, and presence."""

    # In-memory presence store (replace with Redis in production)
    _online_players: Dict[int, dict] = {}
    _player_visibility: Dict[int, str] = {}

    @staticmethod
    def set_online(user_id: int, ws_id: str, position: Optional[dict] = None):
        """Mark player as online."""
        PlayerService._online_players[user_id] = {
            "ws_id": ws_id,
            "position": position or {"x": 0, "y": 0, "z": 0},
            "connected_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def set_offline(user_id: int):
        """Mark player as offline."""
        PlayerService._online_players.pop(user_id, None)

    @staticmethod
    def is_online(user_id: int) -> bool:
        """Check if player is online."""
        return user_id in PlayerService._online_players

    @staticmethod
    def get_online_count() -> int:
        """Get number of online players."""
        return len(PlayerService._online_players)

    @staticmethod
    def get_online_player_ids() -> Set[int]:
        """Get set of all online player IDs."""
        return set(PlayerService._online_players.keys())

    @staticmethod
    def set_visibility(user_id: int, visibility: str):
        """Set player visibility (public, friends_only, hidden)."""
        valid = {"public", "friends_only", "hidden"}
        if visibility not in valid:
            raise ValueError(f"Invalid visibility: {visibility}")
        PlayerService._player_visibility[user_id] = visibility

    @staticmethod
    def get_visibility(user_id: int) -> str:
        """Get player visibility. Defaults to 'public'."""
        return PlayerService._player_visibility.get(user_id, "public")

    @staticmethod
    def can_see_player(viewer_id: int, target_id: int, are_friends: bool) -> bool:
        """
        Check if viewer can see target.
        Rules:
        - Viewer can always see themselves
        - Hidden players: only visible to themselves
        - Friends-only: visible to friends and self
        - Public: visible to everyone
        """
        if viewer_id == target_id:
            return True
        visibility = PlayerService.get_visibility(target_id)
        if visibility == "hidden":
            return False
        if visibility == "friends_only":
            return are_friends
        return True  # public

    @staticmethod
    def get_player_info(db: Session, user_id: int) -> Optional[dict]:
        """Get player profile info."""
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None
        return {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name,
            "is_online": PlayerService.is_online(user_id),
            "visibility": PlayerService.get_visibility(user_id),
        }
