"""Phase 16: Player Privacy + Safety — deletion, reporting, moderation, restrictions."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel

from app.core.database import get_db
from app.models.location import Location
from app.models.user import User

router = APIRouter(prefix="/api/privacy", tags=["privacy"])


# =============================================================================
# Report Model (in-memory or DB-backed)
# =============================================================================

class ReportCreate(BaseModel):
    target_type: str  # "location" or "player"
    target_id: int
    reason: str  # spam, inappropriate, harassment, safety_concern, other
    description: Optional[str] = None


# In-memory report store (for MVP; replace with DB table in production)
_reports: List[dict] = []
_report_counter = 0


# =============================================================================
# Location Deletion (soft delete, creator-only)
# =============================================================================

@router.delete("/locations/{location_id}")
def soft_delete_location(
    location_id: int,
    user_id: int = Query(..., description="User requesting deletion"),
    db: Session = Depends(get_db),
):
    """Soft-delete a location. Only the creator can delete their own location.

    Soft delete: sets moderation_state to 'deleted' and visibility to 'private'.
    The record is preserved for audit purposes but hidden from all views.
    """
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if loc.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only the creator can delete this location")

    loc.moderation_state = "deleted"
    loc.visibility = "private"
    db.commit()

    return {"status": "deleted", "location_id": location_id}


@router.post("/locations/{location_id}/restore")
def restore_location(
    location_id: int,
    user_id: int = Query(..., description="User requesting restore"),
    db: Session = Depends(get_db),
):
    """Restore a soft-deleted location. Only the creator can restore."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    if loc.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only the creator can restore this location")

    if loc.moderation_state != "deleted":
        raise HTTPException(status_code=400, detail="Location is not deleted")

    loc.moderation_state = "pending"
    loc.visibility = "public"
    db.commit()

    return {"status": "restored", "location_id": location_id}


# =============================================================================
# Reporting System
# =============================================================================

@router.post("/reports", response_model=dict)
def create_report(report: ReportCreate):
    """Report a location or player for policy violations."""
    global _report_counter

    valid_reasons = {"spam", "inappropriate", "harassment", "safety_concern", "other"}
    if report.reason not in valid_reasons:
        raise HTTPException(status_code=400, detail=f"Invalid reason. Must be one of: {valid_reasons}")

    valid_targets = {"location", "player"}
    if report.target_type not in valid_targets:
        raise HTTPException(status_code=400, detail=f"Invalid target_type. Must be one of: {valid_targets}")

    _report_counter += 1
    new_report = {
        "id": _report_counter,
        "target_type": report.target_type,
        "target_id": report.target_id,
        "reason": report.reason,
        "description": report.description,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _reports.append(new_report)
    return new_report


@router.get("/reports", response_model=List[dict])
def list_reports(
    status: Optional[str] = Query(None, description="Filter by status: pending, reviewed, resolved, dismissed"),
    limit: int = Query(50, ge=1, le=200),
):
    """List all reports (admin/moderation endpoint)."""
    results = _reports
    if status:
        results = [r for r in results if r["status"] == status]
    return results[:limit]


@router.patch("/reports/{report_id}")
def update_report(
    report_id: int,
    status: str = Query(..., description="New status: reviewed, resolved, dismissed"),
):
    """Update a report's status (admin/moderation endpoint)."""
    valid_statuses = {"pending", "reviewed", "resolved", "dismissed"}
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    for report in _reports:
        if report["id"] == report_id:
            report["status"] = status
            return report

    raise HTTPException(status_code=404, detail="Report not found")


# =============================================================================
# Moderation Tools (admin review queue)
# =============================================================================

@router.get("/moderation/queue", response_model=List[dict])
def moderation_queue(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Get locations pending moderation review."""
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


@router.post("/moderation/locations/{location_id}/approve")
def approve_location(
    location_id: int,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Approve a location (admin/moderation endpoint)."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    loc.moderation_state = "approved"
    loc.moderation_notes = notes
    db.commit()

    return {"status": "approved", "location_id": location_id}


@router.post("/moderation/locations/{location_id}/reject")
def reject_location(
    location_id: int,
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Reject a location (admin/moderation endpoint)."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    loc.moderation_state = "rejected"
    loc.moderation_notes = notes
    loc.visibility = "private"
    db.commit()

    return {"status": "rejected", "location_id": location_id}


# =============================================================================
# Sensitive Location Restrictions (GPS-denied zones)
# =============================================================================

# Pre-defined sensitive zones (military, government, etc.)
# In production, load from a database or external API
SENSITIVE_ZONES = [
    {"name": "Area 51", "lat": 37.235, "lon": -115.810, "radius_meters": 5000},
    {"name": "White House", "lat": 38.8977, "lon": -77.0365, "radius_meters": 200},
    {"name": "Pentagon", "lat": 38.8719, "lon": -77.0563, "radius_meters": 500},
]


def is_in_sensitive_zone(latitude: float, longitude: float) -> Optional[str]:
    """Check if a coordinate falls within a sensitive zone. Returns zone name or None."""
    import math

    for zone in SENSITIVE_ZONES:
        # Haversine check
        lat1 = math.radians(latitude)
        lat2 = math.radians(zone["lat"])
        dlat = math.radians(zone["lat"] - latitude)
        dlon = math.radians(zone["lon"] - longitude)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.asin(math.sqrt(a))
        distance = 6371000 * c  # Earth radius in meters

        if distance <= zone["radius_meters"]:
            return zone["name"]
    return None


@router.get("/sensitive-zones/check")
def check_sensitive_zone(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
):
    """Check if a location is in a restricted zone."""
    zone_name = is_in_sensitive_zone(latitude, longitude)
    if zone_name:
        return {"restricted": True, "zone_name": zone_name}
    return {"restricted": False}


@router.get("/sensitive-zones/list", response_model=List[dict])
def list_sensitive_zones():
    """List all known sensitive zones."""
    return [
        {"name": z["name"], "latitude": z["lat"], "longitude": z["lon"], "radius_meters": z["radius_meters"]}
        for z in SENSITIVE_ZONES
    ]
