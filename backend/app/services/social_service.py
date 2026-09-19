"""
Social Service

Friends, reports, and social interactions.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models.friendship import Friendship
from app.models.user import User
from app.services.friendship_service import FriendshipService


class SocialService:
    """Handles social interactions: friends, reports, blocking."""

    # In-memory report store (replace with DB table in production)
    _reports: List[dict] = []
    _report_counter = 0

    @staticmethod
    def send_friend_request(db: Session, requester_id: int, addressee_id: int) -> Friendship:
        """Send a friend request."""
        return FriendshipService.send_request(db, requester_id, addressee_id)

    @staticmethod
    def accept_friend_request(db: Session, friendship_id: int, user_id: int) -> Friendship:
        """Accept a friend request."""
        return FriendshipService.accept_request(db, friendship_id, user_id)

    @staticmethod
    def reject_friend_request(db: Session, friendship_id: int, user_id: int) -> Friendship:
        """Reject a friend request."""
        return FriendshipService.reject_request(db, friendship_id, user_id)

    @staticmethod
    def remove_friend(db: Session, friendship_id: int, user_id: int) -> bool:
        """Remove a friend."""
        return FriendshipService.remove_friend(db, friendship_id, user_id)

    @staticmethod
    def block_user(db: Session, blocker_id: int, blocked_id: int) -> Friendship:
        """Block a user."""
        return FriendshipService.block_user(db, blocker_id, blocked_id)

    @staticmethod
    def unblock_user(db: Session, blocker_id: int, blocked_id: int) -> bool:
        """Unblock a user."""
        return FriendshipService.unblock_user(db, blocker_id, blocked_id)

    @staticmethod
    def get_friends(db: Session, user_id: int) -> List[User]:
        """Get all friends for a user."""
        friends = FriendshipService.get_friends(db, user_id)
        return [f[1] for f in friends]

    @staticmethod
    def are_friends(db: Session, user_a: int, user_b: int) -> bool:
        """Check if two users are friends."""
        return FriendshipService.are_friends(db, user_a, user_b)

    @staticmethod
    def is_blocked(db: Session, user_a: int, user_b: int) -> bool:
        """Check if either user has blocked the other."""
        return FriendshipService.is_blocked(db, user_a, user_b)

    # Reports

    @classmethod
    def create_report(
        cls,
        target_type: str,
        target_id: int,
        reason: str,
        description: Optional[str] = None,
    ) -> dict:
        """Create a report for a location or player."""
        valid_reasons = {"spam", "inappropriate", "harassment", "safety_concern", "other"}
        if reason not in valid_reasons:
            raise ValueError(f"Invalid reason. Must be one of: {valid_reasons}")
        valid_targets = {"location", "player"}
        if target_type not in valid_targets:
            raise ValueError(f"Invalid target_type. Must be one of: {valid_targets}")

        cls._report_counter += 1
        report = {
            "id": cls._report_counter,
            "target_type": target_type,
            "target_id": target_id,
            "reason": reason,
            "description": description,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        cls._reports.append(report)
        return report

    @classmethod
    def get_reports(
        cls,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get reports, optionally filtered by status."""
        results = cls._reports
        if status:
            results = [r for r in results if r["status"] == status]
        return results[:limit]

    @classmethod
    def update_report_status(cls, report_id: int, status: str) -> dict:
        """Update a report's status."""
        valid_statuses = {"pending", "reviewed", "resolved", "dismissed"}
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        for report in cls._reports:
            if report["id"] == report_id:
                report["status"] = status
                return report
        raise ValueError("Report not found")
