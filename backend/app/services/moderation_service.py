"""
Moderation Service

Content moderation, queue management, and audit logging.
"""

import re
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from app.models.location import Location


# In-memory stores (replace with DB in production)
_audit_log: List[dict] = []
_audit_counter = 0


# Content policy
BLOCKED_WORDS = [
    "spam", "scam", "hack", "exploit", "cheat",
    "nsfw", "nude", "porn", "xxx",
    "kill", "murder", "attack",
    "bomb", "weapon", "drug",
]
BLOCKED_PATTERNS = [
    r"(https?://)?(www\.)?bit\.ly/\w+",
    r"@\w+",
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",
]


class ModerationService:
    """Handles content moderation and policy enforcement."""

    @staticmethod
    def check_content_policy(
        title: str,
        description: Optional[str] = None,
        max_title_length: int = 200,
        max_description_length: int = 2000,
        min_title_length: int = 3,
    ) -> List[str]:
        """Check content against policy. Returns list of violations."""
        violations = []

        if len(title) < min_title_length:
            violations.append(f"Title too short (min {min_title_length} chars)")
        if len(title) > max_title_length:
            violations.append(f"Title too long (max {max_title_length} chars)")
        if description and len(description) > max_description_length:
            violations.append(f"Description too long (max {max_description_length} chars)")

        title_lower = title.lower()
        desc_lower = (description or "").lower()
        for word in BLOCKED_WORDS:
            if word in title_lower:
                violations.append(f"Blocked word in title: '{word}'")
            if word in desc_lower:
                violations.append(f"Blocked word in description: '{word}'")

        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                violations.append(f"Blocked pattern in title: '{pattern}'")
            if description and re.search(pattern, description, re.IGNORECASE):
                violations.append(f"Blocked pattern in description: '{pattern}'")

        return violations

    @staticmethod
    def approve_location(
        db: Session,
        location_id: int,
        notes: Optional[str] = None,
        moderator_id: Optional[int] = None,
    ) -> dict:
        """Approve a location."""
        loc = db.query(Location).filter(Location.id == location_id).first()
        if not loc:
            raise ValueError("Location not found")
        prev = loc.moderation_state
        loc.moderation_state = "approved"
        loc.moderation_notes = notes
        db.commit()
        ModerationService._log("approve", location_id, moderator_id, notes, prev, "approved")
        return {"status": "approved", "location_id": location_id}

    @staticmethod
    def reject_location(
        db: Session,
        location_id: int,
        notes: Optional[str] = None,
        moderator_id: Optional[int] = None,
    ) -> dict:
        """Reject a location."""
        loc = db.query(Location).filter(Location.id == location_id).first()
        if not loc:
            raise ValueError("Location not found")
        prev = loc.moderation_state
        loc.moderation_state = "rejected"
        loc.moderation_notes = notes
        loc.visibility = "private"
        db.commit()
        ModerationService._log("reject", location_id, moderator_id, notes, prev, "rejected")
        return {"status": "rejected", "location_id": location_id}

    @staticmethod
    def restrict_location(
        db: Session,
        location_id: int,
        notes: Optional[str] = None,
        moderator_id: Optional[int] = None,
    ) -> dict:
        """Restrict a location (soft reject, friends-only)."""
        loc = db.query(Location).filter(Location.id == location_id).first()
        if not loc:
            raise ValueError("Location not found")
        if loc.moderation_state == "restricted":
            raise ValueError("Location is already restricted")
        prev = loc.moderation_state
        loc.moderation_state = "restricted"
        loc.visibility = "friends_only"
        loc.moderation_notes = notes
        db.commit()
        ModerationService._log("restrict", location_id, moderator_id, notes, prev, "restricted")
        return {"status": "restricted", "location_id": location_id}

    @staticmethod
    def get_queue(db: Session, limit: int = 50) -> List[dict]:
        """Get locations pending moderation."""
        pending = (
            db.query(Location)
            .filter(Location.moderation_state == "pending")
            .order_by(Location.created_at)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": loc.id,
                "title": loc.title,
                "creator_id": loc.creator_id,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "created_at": loc.created_at.isoformat() if loc.created_at else None,
            }
            for loc in pending
        ]

    @staticmethod
    def get_stats(db: Session) -> dict:
        """Get moderation statistics by state."""
        stats = (
            db.query(Location.moderation_state, func.count(Location.id))
            .group_by(Location.moderation_state)
            .all()
        )
        return {state: count for state, count in stats}

    @staticmethod
    def get_audit_log(
        location_id: Optional[int] = None,
        action: Optional[str] = None,
        limit: int = 50,
    ) -> List[dict]:
        """Get audit log with optional filters."""
        logs = _audit_log
        if location_id is not None:
            logs = [l for l in logs if l["location_id"] == location_id]
        if action:
            logs = [l for l in logs if l["action"] == action]
        return logs[:limit]

    @staticmethod
    def _log(
        action: str,
        location_id: int,
        moderator_id: Optional[int],
        notes: Optional[str],
        previous_state: Optional[str],
        new_state: Optional[str],
    ):
        """Record a moderation action."""
        global _audit_counter
        _audit_counter += 1
        _audit_log.append({
            "id": _audit_counter,
            "action": action,
            "location_id": location_id,
            "moderator_id": moderator_id,
            "notes": notes,
            "previous_state": previous_state,
            "new_state": new_state,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
