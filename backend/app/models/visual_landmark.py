"""
Visual Landmarks Model

Stores visual features extracted from captures for visual localization.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class VisualLandmark(Base):
    """
    A visual landmark extracted from a capture.

    Stores:
      - Descriptor data (SIFT/ORB features)
      - Geographic position (WGS84)
      - Quality metrics
      - Source capture reference
    """
    __tablename__ = "visual_landmarks"

    id = Column(Integer, primary_key=True, index=True)

    # Source reference
    capture_id = Column(Integer, ForeignKey("captures.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    # Geographic position
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    altitude = Column(Float, nullable=True)

    # Visual features
    feature_type = Column(String, nullable=False, default="sift")  # sift, orb, akaze
    descriptor_count = Column(Integer, nullable=True)
    descriptor_data = Column(LargeBinary, nullable=True)  # Serialized feature descriptors
    keypoint_data = Column(LargeBinary, nullable=True)  # Serialized keypoint positions

    # Image reference
    image_path = Column(String, nullable=True)  # Source image path
    image_hash = Column(String, nullable=True, index=True)  # SHA-256 of source image

    # Quality metrics
    quality_score = Column(Float, nullable=True)  # 0.0-1.0
    uniqueness_score = Column(Float, nullable=True)  # 0.0-1.0
    visibility_range = Column(Float, nullable=True)  # meters - how far this landmark is visible

    # Usage stats
    match_count = Column(Integer, default=0)  # Times this landmark has been matched
    last_matched_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    device_info = Column(String, nullable=True)  # JSON: camera model, settings
    capture_conditions = Column(String, nullable=True)  # lighting, weather, etc.

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    capture = relationship("Capture", backref="landmarks")
    location = relationship("Location", backref="landmarks")


class LandmarkMatch(Base):
    """
    Records of landmark matching attempts.
    """
    __tablename__ = "landmark_matches"

    id = Column(Integer, primary_key=True, index=True)

    # Query info
    query_capture_id = Column(Integer, ForeignKey("captures.id"), nullable=True, index=True)
    query_image_hash = Column(String, nullable=True)

    # Match results
    matched_landmark_id = Column(Integer, ForeignKey("visual_landmarks.id"), nullable=False, index=True)
    match_score = Column(Float, nullable=False)  # 0.0-1.0 similarity
    match_distance = Column(Float, nullable=True)  # Distance in meters between query and landmark

    # Match context
    inlier_count = Column(Integer, nullable=True)
    outlier_ratio = Column(Float, nullable=True)

    # Status
    status = Column(String, default="candidate")  # candidate, confirmed, rejected

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    landmark = relationship("VisualLandmark", backref="matches")
