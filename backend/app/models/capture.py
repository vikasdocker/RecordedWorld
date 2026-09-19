from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Capture(Base):
    __tablename__ = "captures"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    video_path = Column(String, nullable=False)
    status = Column(String, default="uploaded")  # uploaded, processing, ready, failed

    # 3D reconstruction outputs
    model_3d_path = Column(String, nullable=True)
    thumbnail_path = Column(String, nullable=True)

    # Geospatial coordinates (WGS84)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Float, nullable=True)  # meters above ellipsoid

    # Capture metadata
    device_orientation = Column(Float, nullable=True)  # heading in degrees
    video_resolution = Column(String, nullable=True)  # e.g. "1920x1080"
    video_fps = Column(Float, nullable=True)
    capture_duration = Column(Float, nullable=True)  # seconds
    device_info = Column(String, nullable=True)  # JSON string

    # Accuracy and confidence
    gps_accuracy = Column(Float, nullable=True)  # meters
    alignment_confidence = Column(Float, nullable=True)  # 0.0 to 1.0
    alignment_method = Column(String, nullable=True)  # gps, visual, map_match

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="captures")
