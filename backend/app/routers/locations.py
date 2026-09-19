from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pathlib import Path

from app.core.config import settings

from app.core.database import get_db
from app.core.geospatial import WGS84Coordinate, haversine_distance
from app.core.spatial_index import compute_grid_cell_id, search_locations_sql
from app.models.location import Location
from app.models.capture import Capture
from app.models.category import Category
from app.models.tag import Tag, location_tags
from app.models.user import User
from app.schemas.location import LocationCreate, LocationResponse, LocationPublic
from app.services.friendship_service import FriendshipService

router = APIRouter(prefix="/api/locations", tags=["locations"])

DEFAULT_CELL_SIZE = 100.0  # meters


@router.post("/", response_model=LocationResponse)
def create_location(
    location: LocationCreate,
    db: Session = Depends(get_db),
):
    db_location = Location(
        creator_id=1,  # TODO: auth - will use get_current_user_id when auth is implemented
        capture_id=location.capture_id,
        title=location.title,
        description=location.description,
        latitude=location.latitude,
        longitude=location.longitude,
        altitude=location.altitude,
        rotation=location.rotation,
        scale=location.scale,
        grid_cell_id=compute_grid_cell_id(
            WGS84Coordinate(location.latitude, location.longitude, location.altitude or 0.0),
            DEFAULT_CELL_SIZE,
        ),
    )
    db.add(db_location)
    db.commit()
    db.refresh(db_location)
    return db_location


@router.get("/", response_model=List[LocationResponse])
def list_locations(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return db.query(Location).offset(skip).limit(limit).all()


@router.get("/nearby", response_model=List[dict])
def find_nearby_locations(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_meters: float = Query(1000.0, gt=0, le=100000),
    limit: int = Query(50, ge=1, le=200),
    viewer_id: Optional[int] = Query(None),
    category: Optional[str] = Query(None, description="Filter by category slug"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    creator_id: Optional[int] = Query(None, description="Filter by creator"),
    db: Session = Depends(get_db),
):
    center = WGS84Coordinate(latitude=latitude, longitude=longitude)
    cell_ids, min_lat, max_lat, min_lon, max_lon = search_locations_sql(
        center, radius_meters, DEFAULT_CELL_SIZE
    )

    # Phase 1: coarse filter by grid cell + bounding box
    query = (
        db.query(Location)
        .filter(
            Location.grid_cell_id.in_(cell_ids),
            Location.latitude.between(min_lat, max_lat),
            Location.longitude.between(min_lon, max_lon),
            Location.moderation_state == "approved",
            Location.visibility.in_(["public", "friends_only"]),
        )
    )

    # Category filter
    if category:
        query = query.join(Location.categories).filter(Category.slug == category)

    # Text search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (Location.title.ilike(search_pattern)) | (Location.description.ilike(search_pattern))
        )

    # Creator filter
    if creator_id is not None:
        query = query.filter(Location.creator_id == creator_id)

    candidates = query.options(
        joinedload(Location.categories),
        joinedload(Location.tags),
        joinedload(Location.creator),
    ).all()

    # Pre-fetch friend IDs if viewer is authenticated
    friend_ids = set()
    if viewer_id is not None:
        friend_ids = FriendshipService.get_friend_ids(db, viewer_id)

    # Phase 2: exact haversine distance filter + visibility enforcement
    results = []
    for loc in candidates:
        loc_coord = WGS84Coordinate(loc.latitude, loc.longitude, loc.altitude or 0.0)
        dist = haversine_distance(center, loc_coord)
        if dist > radius_meters:
            continue

        # Enforce visibility rules
        if loc.visibility == "friends_only":
            if viewer_id != loc.creator_id:
                if viewer_id is None or loc.creator_id not in friend_ids:
                    continue

        # Apply creator privacy settings
        creator = loc.creator
        if creator and not creator.location_sharing and loc.creator_id != viewer_id:
            continue

        # Build response with privacy adjustments
        result = {
            "id": loc.id,
            "title": loc.title,
            "description": loc.description,
            "creator_id": loc.creator_id,
            "creator_name": creator.display_name or creator.username if creator else None,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "altitude": loc.altitude,
            "distance_meters": round(dist, 2),
            "accuracy_meters": loc.accuracy_meters,
            "confidence": loc.confidence,
            "thumbnail_id": loc.thumbnail_id,
            "categories": [{"id": c.id, "name": c.name, "slug": c.slug} for c in loc.categories],
            "tags": [{"id": t.id, "name": t.name, "slug": t.slug} for t in loc.tags],
            "created_at": loc.created_at.isoformat() if loc.created_at else None,
        }

        # Apply approximate_location for non-creators
        if creator and creator.approximate_location and viewer_id != loc.creator_id:
            result["latitude"] = round(loc.latitude, 2)
            result["longitude"] = round(loc.longitude, 2)

        results.append(result)

    # Sort by distance
    results.sort(key=lambda x: x["distance_meters"])
    return results[:limit]


@router.get("/{location_id}", response_model=LocationResponse)
def get_location(location_id: int, db: Session = Depends(get_db)):
    db_location = db.query(Location).filter(Location.id == location_id).first()
    if not db_location:
        raise HTTPException(status_code=404, detail="Location not found")
    return db_location


@router.delete("/{location_id}")
def delete_location(
    location_id: int,
    user_id: int = Query(None, description="User requesting deletion (required for authorization)"),
    db: Session = Depends(get_db),
):
    """Delete a location. If user_id is provided, only the creator can delete (soft delete).
    Without user_id, performs hard delete (legacy/admin behavior)."""
    db_location = db.query(Location).filter(Location.id == location_id).first()
    if not db_location:
        raise HTTPException(status_code=404, detail="Location not found")

    if user_id is not None:
        if db_location.creator_id != user_id:
            raise HTTPException(status_code=403, detail="Only the creator can delete this location")
        # Soft delete
        db_location.moderation_state = "deleted"
        db_location.visibility = "private"
        db.commit()
        return {"status": "deleted", "location_id": location_id}

    # Hard delete (legacy)
    db.delete(db_location)
    db.commit()
    return {"status": "deleted"}


# =============================================================================
# Visibility Management
# =============================================================================

@router.put("/{location_id}/visibility")
def update_visibility(
    location_id: int,
    visibility: str = Query(..., description="new visibility: public, unlisted, private, friends_only"),
    user_id: int = Query(..., description="User requesting change"),
    db: Session = Depends(get_db),
):
    """Update a location's visibility. Only the creator can change visibility."""
    valid = {"public", "unlisted", "private", "friends_only"}
    if visibility not in valid:
        raise HTTPException(status_code=400, detail=f"visibility must be one of: {valid}")

    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    if loc.creator_id != user_id:
        raise HTTPException(status_code=403, detail="Only the creator can change visibility")

    loc.visibility = visibility
    db.commit()
    db.refresh(loc)
    return {"visibility": loc.visibility, "location_id": loc.id}


# =============================================================================
# Moderation State Management
# =============================================================================

@router.put("/{location_id}/moderation")
def update_moderation(
    location_id: int,
    state: str = Query(..., alias="state", description="moderation_state: approved, rejected, restricted, pending"),
    notes: str = Query(None, description="Moderation notes"),
    db: Session = Depends(get_db),
):
    """Update a location's moderation state (admin/moderator action)."""
    valid = {"pending", "approved", "rejected", "restricted"}
    if state not in valid:
        raise HTTPException(status_code=400, detail=f"state must be one of: {valid}")

    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    loc.moderation_state = state
    if notes:
        loc.moderation_notes = notes
    db.commit()
    db.refresh(loc)
    return {"moderation_state": loc.moderation_state, "location_id": loc.id}


@router.get("/moderated/list", response_model=List[dict])
def list_moderated_locations(
    state: str = Query("pending", description="Filter by moderation state"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List locations by moderation state (admin view)."""
    query = db.query(Location).filter(Location.moderation_state == state)
    locs = query.offset(skip).limit(limit).all()
    return [
        {
            "id": loc.id,
            "title": loc.title,
            "creator_id": loc.creator_id,
            "latitude": loc.latitude,
            "longitude": loc.longitude,
            "moderation_state": loc.moderation_state,
            "moderation_notes": loc.moderation_notes,
            "created_at": loc.created_at.isoformat() if loc.created_at else None,
        }
        for loc in locs
    ]


# =============================================================================
# Categories
# =============================================================================

@router.get("/categories/list", response_model=List[dict])
def list_categories(db: Session = Depends(get_db)):
    """List all available location categories."""
    cats = db.query(Category).order_by(Category.name).all()
    return [{"id": c.id, "name": c.name, "slug": c.slug, "icon": c.icon} for c in cats]


# =============================================================================
# Thumbnails
# =============================================================================

@router.get("/{location_id}/thumbnail")
def get_location_thumbnail(location_id: int, db: Session = Depends(get_db)):
    """Serve a location's thumbnail image."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    if not loc.thumbnail_id:
        raise HTTPException(status_code=404, detail="No thumbnail available")

    # thumbnail_id maps to uploads/thumbnails/{thumbnail_id}
    thumb_path = settings.UPLOAD_DIR / "thumbnails" / loc.thumbnail_id
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file not found")

    return FileResponse(thumb_path, media_type="image/jpeg")


# =============================================================================
# 3D Model Serving
# =============================================================================

@router.get("/{location_id}/model")
def get_location_model(location_id: int, db: Session = Depends(get_db)):
    """Serve a location's 3D model (.glb file)."""
    loc = db.query(Location).filter(Location.id == location_id).first()
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")

    # Try to find the model via capture -> model_3d_path
    model_path = None
    if loc.capture_id:
        capture = db.query(Capture).filter(Capture.id == loc.capture_id).first()
        if capture and capture.model_3d_path:
            model_path = Path(capture.model_3d_path)

    # Fallback: try asset_id as a relative path under uploads
    if not model_path and loc.asset_id:
        candidate = settings.UPLOAD_DIR / loc.asset_id
        if candidate.exists():
            model_path = candidate

    # Fallback: try uploads/capture_{capture_id}/model.glb
    if not model_path and loc.capture_id:
        candidate = settings.UPLOAD_DIR / f"capture_{loc.capture_id}" / "model.glb"
        if candidate.exists():
            model_path = candidate

    if not model_path or not model_path.exists():
        raise HTTPException(status_code=404, detail="3D model not available for this location")

    return FileResponse(model_path, media_type="model/gltf-binary", filename=f"location_{location_id}.glb")


# =============================================================================
# Cities (preset locations for world exploration)
# =============================================================================

# Predefined cities the player can travel to
CITIES = [
    {"id": "nyc", "name": "New York City", "country": "USA", "lat": 40.785, "lon": -73.968, "description": "Central Park & Manhattan skyline"},
    {"id": "paris", "name": "Paris", "country": "France", "lat": 48.8566, "lon": 2.3522, "description": "Eiffel Tower & Champs-Élysées"},
    {"id": "tokyo", "name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503, "description": "Shibuya & Tokyo Tower"},
    {"id": "london", "name": "London", "country": "UK", "lat": 51.5074, "lon": -0.1278, "description": "Big Ben & Westminster"},
    {"id": "dubai", "name": "Dubai", "country": "UAE", "lat": 25.2048, "lon": 55.2708, "description": "Burj Khalifa & Marina"},
    {"id": "sydney", "name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093, "description": "Opera House & Harbour Bridge"},
    {"id": "rio", "name": "Rio de Janeiro", "country": "Brazil", "lat": -22.9068, "lon": -43.1729, "description": "Christ the Redeemer & Copacabana"},
    {"id": "mumbai", "name": "Mumbai", "country": "India", "lat": 19.0760, "lon": 72.8777, "description": "Gateway of India & Marine Drive"},
]


@router.get("/cities/list")
def list_cities():
    """List predefined cities available for exploration."""
    return CITIES
