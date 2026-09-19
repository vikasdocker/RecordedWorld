"""
Notification Service

In-memory notification system for player alerts.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class Notification:
    """A player notification."""
    id: str
    user_id: int
    type: str  # friend_request, friend_accepted, report_respected, moderation, system
    title: str
    message: str
    data: Optional[dict] = None
    read: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NotificationService:
    """In-memory notification system."""

    _notifications: Dict[int, List[Notification]] = {}  # user_id -> notifications

    @classmethod
    def create(
        cls,
        user_id: int,
        type: str,
        title: str,
        message: str,
        data: Optional[dict] = None,
    ) -> Notification:
        """Create a notification for a user."""
        notif = Notification(
            id=str(uuid.uuid4())[:12],
            user_id=user_id,
            type=type,
            title=title,
            message=message,
            data=data,
        )
        if user_id not in cls._notifications:
            cls._notifications[user_id] = []
        cls._notifications[user_id].insert(0, notif)
        return notif

    @classmethod
    def get_notifications(
        cls,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
    ) -> List[Notification]:
        """Get notifications for a user."""
        notifs = cls._notifications.get(user_id, [])
        if unread_only:
            notifs = [n for n in notifs if not n.read]
        return notifs[:limit]

    @classmethod
    def mark_read(cls, user_id: int, notification_id: str) -> bool:
        """Mark a notification as read."""
        notifs = cls._notifications.get(user_id, [])
        for n in notifs:
            if n.id == notification_id:
                n.read = True
                return True
        return False

    @classmethod
    def mark_all_read(cls, user_id: int) -> int:
        """Mark all notifications as read. Returns count marked."""
        notifs = cls._notifications.get(user_id, [])
        count = 0
        for n in notifs:
            if not n.read:
                n.read = True
                count += 1
        return count

    @classmethod
    def get_unread_count(cls, user_id: int) -> int:
        """Get count of unread notifications."""
        notifs = cls._notifications.get(user_id, [])
        return sum(1 for n in notifs if not n.read)

    @classmethod
    def delete_notification(cls, user_id: int, notification_id: str) -> bool:
        """Delete a notification."""
        notifs = cls._notifications.get(user_id, [])
        for i, n in enumerate(notifs):
            if n.id == notification_id:
                notifs.pop(i)
                return True
        return False

    @classmethod
    def clear_all(cls, user_id: int) -> int:
        """Clear all notifications for a user. Returns count cleared."""
        notifs = cls._notifications.pop(user_id, [])
        return len(notifs)
