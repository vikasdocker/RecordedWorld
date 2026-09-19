from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CaptureBase(BaseModel):
    title: str
    description: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    altitude: Optional[float] = None
    gps_accuracy: Optional[float] = None


class CaptureCreate(CaptureBase):
    pass


class CaptureResponse(CaptureBase):
    id: int
    user_id: int
    status: str
    video_path: str
    model_3d_path: Optional[str] = None
    thumbnail_path: Optional[str] = None
    device_orientation: Optional[float] = None
    video_resolution: Optional[str] = None
    video_fps: Optional[float] = None
    capture_duration: Optional[float] = None
    alignment_confidence: Optional[float] = None
    alignment_method: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CaptureList(BaseModel):
    """Simplified capture for list views."""
    id: int
    title: str
    status: str
    thumbnail_path: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    created_at: datetime

    model_config = {"from_attributes": True}
