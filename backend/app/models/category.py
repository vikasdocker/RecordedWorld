from sqlalchemy import Column, String, Integer, Table, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base

# Many-to-many junction table
location_categories = Table(
    "location_categories",
    Base.metadata,
    Column("location_id", Integer, ForeignKey("locations.id"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id"), primary_key=True),
)


class Category(Base):
    """A category tag for locations (e.g. 'park', 'museum', 'landmark')."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    slug = Column(String, unique=True, nullable=False, index=True)
    icon = Column(String, nullable=True)  # emoji or icon identifier

    locations = relationship(
        "Location",
        secondary=location_categories,
        back_populates="categories",
    )
