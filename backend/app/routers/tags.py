from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional

from app.core.database import get_db
from app.models.tag import Tag, location_tags
from app.models.location import Location

router = APIRouter(prefix="/api/tags", tags=["tags"])


def slugify(name: str) -> str:
    """Convert tag name to URL-friendly slug."""
    return name.lower().strip().replace(" ", "-").replace("_", "-")


@router.post("/locations/{location_id}/tags", response_model=dict)
def add_tag_to_location(
    location_id: int,
    name: str = Query(..., min_length=1, max_length=50),
    user_id: int = Query(None),
    db: Session = Depends(get_db),
):
    """Add a tag to a location (or create it if it doesn't exist)."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    slug = slugify(name)
    tag = db.query(Tag).filter(Tag.slug == slug).first()
    if not tag:
        tag = Tag(name=name, slug=slug)
        db.add(tag)
        db.commit()
        db.refresh(tag)

    # Check if tag is already on this location
    existing = (
        db.query(location_tags)
        .filter(
            location_tags.c.location_id == location_id,
            location_tags.c.tag_id == tag.id,
        )
        .first()
    )
    if existing:
        return {"id": tag.id, "name": tag.name, "slug": tag.slug, "status": "already_exists"}

    # Associate tag with location
    db.execute(location_tags.insert().values(
        location_id=location_id,
        tag_id=tag.id,
        created_by=user_id,
    ))
    tag.usage_count += 1
    db.commit()

    return {"id": tag.id, "name": tag.name, "slug": tag.slug, "status": "added"}


@router.delete("/locations/{location_id}/tags/{tag_id}")
def remove_tag_from_location(
    location_id: int,
    tag_id: int,
    db: Session = Depends(get_db),
):
    """Remove a tag from a location."""
    result = db.execute(
        location_tags.delete().where(
            location_tags.c.location_id == location_id,
            location_tags.c.tag_id == tag_id,
        )
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Tag not found on this location")

    # Decrement usage count
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if tag and tag.usage_count > 0:
        tag.usage_count -= 1
    db.commit()

    return {"status": "removed"}


@router.get("/locations/{location_id}/tags", response_model=List[dict])
def get_location_tags(location_id: int, db: Session = Depends(get_db)):
    """Get all tags for a location."""
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found")

    tags = (
        db.query(Tag)
        .join(location_tags, Tag.id == location_tags.c.tag_id)
        .filter(location_tags.c.location_id == location_id)
        .order_by(Tag.name)
        .all()
    )
    return [{"id": t.id, "name": t.name, "slug": t.slug} for t in tags]


@router.get("/search", response_model=List[dict])
def search_tags(
    q: str = Query("", description="Search prefix"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Search tags by name prefix (for autocomplete)."""
    if not q:
        # Return most popular tags
        tags = db.query(Tag).order_by(Tag.usage_count.desc()).limit(limit).all()
    else:
        tags = (
            db.query(Tag)
            .filter(Tag.name.ilike(f"{q}%"))
            .order_by(Tag.usage_count.desc())
            .limit(limit)
            .all()
        )
    return [{"id": t.id, "name": t.name, "slug": t.slug, "usage_count": t.usage_count} for t in tags]


@router.get("/popular", response_model=List[dict])
def popular_tags(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Get most popular tags across all locations."""
    tags = db.query(Tag).order_by(Tag.usage_count.desc()).limit(limit).all()
    return [{"id": t.id, "name": t.name, "slug": t.slug, "usage_count": t.usage_count} for t in tags]


@router.get("/by-slug/{slug}", response_model=dict)
def get_tag_by_slug(slug: str, db: Session = Depends(get_db)):
    """Get a tag by its slug."""
    tag = db.query(Tag).filter(Tag.slug == slug).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return {"id": tag.id, "name": tag.name, "slug": tag.slug, "usage_count": tag.usage_count}
