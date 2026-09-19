"""Phase 17: Content Moderation — automated checks, policy rules, audit log, restrict workflow."""

import re
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.models.location import Location

router = APIRouter(prefix="/api/moderation", tags=["moderation"])


# =============================================================================
# Content Policy Rules
# =============================================================================

class ContentPolicy(BaseModel):
    """Defines automated content moderation rules."""
    max_title_length: int = 200
    max_description_length: int = 2000
    blocked_words: List[str] = [
        "spam", "scam", "hack", "exploit", "cheat",
        "nsfw", "nude", "porn", "xxx",
        "kill", "murder", "attack",
        "bomb", "weapon", "drug",
    ]
    blocked_patterns: List[str] = [
        r"(https?://)?(www\.)?bit\.ly/\w+",  # URL shorteners
        r"@\w+",  # @mentions
        r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",  # Phone numbers
    ]
    min_title_length: int = 3


# In-memory policy store (replace with DB in production)
_content_policy = ContentPolicy()


def check_content_policy(title: str, description: Optional[str] = None) -> List[str]:
    """
    Run automated content checks on a location's title and description.
    Returns a list of violation reasons (empty = passes).
    """
    violations = []

    # Title checks
    if len(title) < _content_policy.min_title_length:
        violations.append(f"Title too short (min {_content_policy.min_title_length} chars)")
    if len(title) > _content_policy.max_title_length:
        violations.append(f"Title too long (max {_content_policy.max_title_length} chars)")

    # Description checks
    if description and len(description) > _content_policy.max_description_length:
        violations.append(f"Description too long (max {_content_policy.max_description_length} chars)")

    # Blocked words (case-insensitive)
    title_lower = title.lower()
    desc_lower = (description or "").lower()
    for word in _content_policy.blocked_words:
        if word in title_lower:
            violations.append(f"Blocked word in title: '{word}'")
        if word in desc_lower:
            violations.append(f"Blocked word in description: '{word}'")

    # Blocked patterns (regex)
    for pattern in _content_policy.blocked_patterns:
        if re.search(pattern, title, re.IGNORECASE):
            violations.append(f"Blocked pattern in title: '{pattern}'")
        if description and re.search(pattern, description, re.IGNORECASE):
            violations.append(f"Blocked pattern in description: '{pattern}'")

    return violations


# =============================================================================
# Moderation Audit Log
# =============================================================================

# In-memory audit log (replace with DB table in production)
_audit_log: List[dict] = []
_audit_counter = 0


def log_moderation_action(
    action: str,
    location_id: int,
    moderator_id: Optional[int] = None,
    reason: Optional[str] = None,
    notes: Optional[str] = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
):
    """Record a moderation action in the audit log."""
    global _audit_counter
    _audit_counter += 1
    _audit_log.append({
        "id": _audit_counter,
        "action": action,
        "location_id": location_id,
        "moderator_id": moderator_id,
        "reason": reason,
        "notes": notes,
        "previous_state": previous_state,
        "new_state": new_state,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# =============================================================================
# Automated Content Analysis Endpoint
# =============================================================================

@router.post("/analyze")
def analyze_content(
    title: str = Query(...),
    description: Optional[str] = Query(None),
):
    """Automated content analysis — checks title/description against policy."""
    violations = check_content_policy(title, description)
    return {
        "passes": len(violations) == 0,
        "violations": violations,
        "title_length": len(title),
        "description_length": len(description) if description else 0,
    }


# =============================================================================
# Restrict Workflow (soft-reject: visible only to friends)
# =============================================================================

@router.post("/locations/{location_id}/restrict")
def restrict_location(
    location_id: int,
    notes: Optional[str] = Query(None),
    moderator_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Restrict a location — soft reject, visible only to creator's friends."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if loc.moderation_state == "restricted":
        raise HTTPException(status_code=400, detail="Location is already restricted")

    previous_state = loc.moderation_state
    loc.moderation_state = "restricted"
    loc.visibility = "friends_only"
    loc.moderation_notes = notes
    db.commit()

    log_moderation_action(
        action="restrict",
        location_id=location_id,
        moderator_id=moderator_id,
        notes=notes,
        previous_state=previous_state,
        new_state="restricted",
    )

    return {"status": "restricted", "location_id": location_id}


# =============================================================================
# Enhanced Moderation Actions with Audit Logging
# =============================================================================

@router.post("/locations/{location_id}/approve")
def approve_location(
    location_id: int,
    notes: Optional[str] = Query(None),
    moderator_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Approve a location with audit logging."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    previous_state = loc.moderation_state
    loc.moderation_state = "approved"
    loc.moderation_notes = notes
    db.commit()

    log_moderation_action(
        action="approve",
        location_id=location_id,
        moderator_id=moderator_id,
        notes=notes,
        previous_state=previous_state,
        new_state="approved",
    )

    return {"status": "approved", "location_id": location_id}


@router.post("/locations/{location_id}/reject")
def reject_location(
    location_id: int,
    notes: Optional[str] = Query(None),
    moderator_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Reject a location with audit logging."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    previous_state = loc.moderation_state
    loc.moderation_state = "rejected"
    loc.moderation_notes = notes
    loc.visibility = "private"
    db.commit()

    log_moderation_action(
        action="reject",
        location_id=location_id,
        moderator_id=moderator_id,
        notes=notes,
        previous_state=previous_state,
        new_state="rejected",
    )

    return {"status": "rejected", "location_id": location_id}


# =============================================================================
# Bulk Moderation
# =============================================================================

class BulkModerationRequest(BaseModel):
    location_ids: List[int]
    action: str  # approve, reject, restrict
    notes: Optional[str] = None
    moderator_id: Optional[int] = None


@router.post("/bulk")
def bulk_moderate(
    request: BulkModerationRequest,
    db: Session = Depends(get_db),
):
    """Bulk moderate multiple locations at once."""
    valid_actions = {"approve", "reject", "restrict"}
    if request.action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Invalid action. Must be one of: {valid_actions}")

    results = []
    for loc_id in request.location_ids:
        loc = db.query(Location).filter(Location.id == loc_id).first()
        if not loc:
            results.append({"id": loc_id, "status": "not_found"})
            continue

        previous_state = loc.moderation_state

        if request.action == "approve":
            loc.moderation_state = "approved"
        elif request.action == "reject":
            loc.moderation_state = "rejected"
            loc.visibility = "private"
        elif request.action == "restrict":
            loc.moderation_state = "restricted"
            loc.visibility = "friends_only"

        if request.notes:
            loc.moderation_notes = request.notes

        log_moderation_action(
            action=request.action,
            location_id=loc_id,
            moderator_id=request.moderator_id,
            notes=request.notes,
            previous_state=previous_state,
            new_state=loc.moderation_state,
        )

        results.append({"id": loc_id, "status": request.action})

    db.commit()
    return {"results": results}


# =============================================================================
# Moderation Audit Log
# =============================================================================

@router.get("/audit-log", response_model=List[dict])
def get_audit_log(
    location_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """Get the moderation audit log, optionally filtered by location or action."""
    logs = _audit_log
    if location_id is not None:
        logs = [l for l in logs if l["location_id"] == location_id]
    if action:
        logs = [l for l in logs if l["action"] == action]
    return logs[:limit]


# =============================================================================
# Moderation Statistics
# =============================================================================

@router.get("/stats")
def moderation_stats(db: Session = Depends(get_db)):
    """Get moderation statistics — counts by state."""
    stats = (
        db.query(Location.moderation_state, func.count(Location.id))
        .group_by(Location.moderation_state)
        .all()
    )
    return {state: count for state, count in stats}
