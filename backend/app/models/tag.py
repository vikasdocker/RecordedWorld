from sqlalchemy import Column, String, Integer, Table, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base

# Many-to-many junction: locations <-> tags
location_tags = Table(
    "location_tags",
    Base.metadata,
    Column("location_id", Integer, ForeignKey("locations.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True),
    Column("created_by", Integer, ForeignKey("users.id"), nullable=True),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)


class Tag(Base):
    """A user-generated freeform tag for locations (e.g. 'sunset', 'hidden-gem')."""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    usage_count = Column(Integer, default=0)  # denormalized count for sorting

    locations = relationship(
        "Location",
        secondary=location_tags,
        back_populates="tags",
    )
