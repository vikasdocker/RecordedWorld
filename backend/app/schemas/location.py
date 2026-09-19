from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class LocationBase(BaseModel):
    title: str
    description: Optional[str] = None
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    altitude: Optional[float] = None
    rotation: float = 0.0
    scale: float = 1.0


class LocationCreate(LocationBase):
    capture_id: Optional[int] = None


class LocationResponse(LocationBase):
    id: int
    creator_id: int
    capture_id: Optional[int] = None

    # Bounding box
    bbox_min_x: Optional[float] = None
    bbox_min_y: Optional[float] = None
    bbox_min_z: Optional[float] = None
    bbox_max_x: Optional[float] = None
    bbox_max_y: Optional[float] = None
    bbox_max_z: Optional[float] = None

    # Asset
    asset_id: Optional[str] = None
    thumbnail_id: Optional[str] = None

    # Accuracy
    accuracy_meters: Optional[float] = None
    confidence: Optional[float] = None
    alignment_method: Optional[str] = None
    reconstruction_quality: Optional[str] = None

    # Visibility and moderation
    visibility: str = "public"
    moderation_state: str = "pending"

    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class LocationPublic(BaseModel):
    """Public location info for discovery."""
    id: int
    title: str
    description: Optional[str] = None
    creator_id: int
    creator_username: Optional[str] = None
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    thumbnail_id: Optional[str] = None
    accuracy_meters: Optional[float] = None
    confidence: Optional[float] = None
    visibility: str = "public"
    created_at: datetime

    model_config = {"from_attributes": True}


class LocationSearch(BaseModel):
    """Search parameters for nearby locations."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(1000, gt=0, le=100000)
    limit: int = Field(50, gt=0, le=200)
