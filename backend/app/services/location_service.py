"""
Location Service

Location CRUD, nearby search, and category management.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func

from app.core.geospatial import WGS84Coordinate, haversine_distance
from app.core.spatial_index import compute_grid_cell_id, search_locations_sql
from app.models.location import Location
from app.models.category import Category
from app.models.tag import Tag, location_tags
from app.models.user import User
from app.services.friendship_service import FriendshipService

DEFAULT_CELL_SIZE = 100.0


class LocationService:
    """Handles location operations."""

    @staticmethod
    def create_location(
        db: Session,
        creator_id: int,
        title: str,
        latitude: float,
        longitude: float,
        altitude: Optional[float] = None,
        description: Optional[str] = None,
        capture_id: Optional[int] = None,
        visibility: str = "public",
    ) -> Location:
        """Create a new location."""
        grid_cell_id = compute_grid_cell_id(
            WGS84Coordinate(latitude, longitude, altitude or 0.0),
            DEFAULT_CELL_SIZE,
        )
        location = Location(
            creator_id=creator_id,
            capture_id=capture_id,
            title=title,
            description=description,
            latitude=latitude,
            longitude=longitude,
            altitude=altitude,
            grid_cell_id=grid_cell_id,
            visibility=visibility,
            moderation_state="pending",
        )
        db.add(location)
        db.commit()
        db.refresh(location)
        return location

    @staticmethod
    def get_location(db: Session, location_id: int) -> Optional[Location]:
        """Get a location by ID."""
        return db.query(Location).filter(Location.id == location_id).first()

    @staticmethod
    def delete_location(
        db: Session,
        location_id: int,
        user_id: Optional[int] = None,
    ) -> bool:
        """Delete a location. If user_id provided, only creator can delete (soft)."""
        location = db.query(Location).filter(Location.id == location_id).first()
        if not location:
            return False

        if user_id is not None:
            if location.creator_id != user_id:
                raise PermissionError("Only the creator can delete this location")
            location.moderation_state = "deleted"
            location.visibility = "private"
        else:
            db.delete(location)

        db.commit()
        return True

    @staticmethod
    def find_nearby(
        db: Session,
        latitude: float,
        longitude: float,
        radius_meters: float = 1000.0,
        limit: int = 50,
        viewer_id: Optional[int] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        creator_id: Optional[int] = None,
    ) -> List[dict]:
        """Find nearby locations with visibility enforcement."""
        center = WGS84Coordinate(latitude=latitude, longitude=longitude)
        cell_ids, min_lat, max_lat, min_lon, max_lon = search_locations_sql(
            center, radius_meters, DEFAULT_CELL_SIZE
        )

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

        if category:
            query = query.join(Location.categories).filter(Category.slug == category)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                (Location.title.ilike(pattern)) | (Location.description.ilike(pattern))
            )
        if creator_id is not None:
            query = query.filter(Location.creator_id == creator_id)

        candidates = query.options(
            joinedload(Location.categories),
            joinedload(Location.tags),
            joinedload(Location.creator),
        ).all()

        friend_ids = set()
        if viewer_id is not None:
            friend_ids = FriendshipService.get_friend_ids(db, viewer_id)

        results = []
        for loc in candidates:
            loc_coord = WGS84Coordinate(loc.latitude, loc.longitude, loc.altitude or 0.0)
            dist = haversine_distance(center, loc_coord)
            if dist > radius_meters:
                continue
            if loc.visibility == "friends_only":
                if viewer_id != loc.creator_id:
                    if viewer_id is None or loc.creator_id not in friend_ids:
                        continue
            creator = loc.creator
            if creator and not creator.location_sharing and loc.creator_id != viewer_id:
                continue

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
            if creator and creator.approximate_location and viewer_id != loc.creator_id:
                result["latitude"] = round(loc.latitude, 2)
                result["longitude"] = round(loc.longitude, 2)
            results.append(result)

        results.sort(key=lambda x: x["distance_meters"])
        return results[:limit]
