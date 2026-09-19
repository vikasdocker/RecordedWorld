from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.category import location_categories
from app.models.tag import location_tags


class Location(Base):
    """
    A geographically anchored location in the world.

    Every uploaded reconstruction becomes a Location with:
    - WGS84 coordinates for persistent storage
    - Accuracy/confidence metrics
    - Visibility and moderation state
    - Creator identity
    """
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    capture_id = Column(Integer, ForeignKey("captures.id"), nullable=True)

    # Identity
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    # Geospatial (WGS84)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)  # meters above ellipsoid
    grid_cell_id = Column(String, nullable=True, index=True)  # spatial index cell

    # Orientation and scale
    rotation = Column(Float, default=0.0)  # yaw in degrees
    scale = Column(Float, default=1.0)

    # Bounding box (ENU meters relative to center)
    bbox_min_x = Column(Float, nullable=True)
    bbox_min_y = Column(Float, nullable=True)
    bbox_min_z = Column(Float, nullable=True)
    bbox_max_x = Column(Float, nullable=True)
    bbox_max_y = Column(Float, nullable=True)
    bbox_max_z = Column(Float, nullable=True)

    # 3D asset
    asset_id = Column(String, nullable=True)  # reference to asset storage
    thumbnail_id = Column(String, nullable=True)

    # Accuracy and confidence
    accuracy_meters = Column(Float, nullable=True)  # estimated position error
    confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    alignment_method = Column(String, nullable=True)  # gps, visual, map_match

    # Provenance
    reconstruction_quality = Column(String, nullable=True)  # high, medium, low
    geometry_provenance = Column(String, default="reconstructed")  # reconstructed, inferred, generated

    # Visibility
    visibility = Column(String, default="public")  # public, unlisted, private, friends_only

    # Moderation
    moderation_state = Column(String, default="pending")  # pending, approved, rejected, restricted
    moderation_notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    creator = relationship("User", backref="locations")
    capture = relationship("Capture", backref="locations")
    categories = relationship(
        "Category",
        secondary=location_categories,
        back_populates="locations",
    )
    tags = relationship(
        "Tag",
        secondary=location_tags,
        back_populates="locations",
    )
