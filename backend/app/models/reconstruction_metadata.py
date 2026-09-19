"""
Reconstruction Metadata Model

Stores detailed metadata about 3D reconstruction runs.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ReconstructionMetadata(Base):
    """
    Detailed metadata about a 3D reconstruction run.

    Captures pipeline configuration, quality metrics, and timing
    for reproducibility and debugging.
    """
    __tablename__ = "reconstruction_metadata"

    id = Column(Integer, primary_key=True, index=True)
    reconstruction_job_id = Column(
        Integer, ForeignKey("reconstruction_jobs.id"), nullable=False, index=True
    )

    # Pipeline config
    feature_detector = Column(String, nullable=True)  # sift, orb, akaze
    matcher_type = Column(String, nullable=True)  # brute_force, flann, homography
    depth_method = Column(String, nullable=True)  # stereo, monocular, tof

    # Input stats
    input_frame_count = Column(Integer, nullable=True)
    input_resolution = Column(String, nullable=True)  # WxH
    input_duration_seconds = Column(Float, nullable=True)

    # Feature stats
    features_detected = Column(Integer, nullable=True)
    features_matched = Column(Integer, nullable=True)
    inlier_ratio = Column(Float, nullable=True)  # 0.0-1.0

    # Camera stats
    camera_poses_estimated = Column(Integer, nullable=True)
    mean_reprojection_error = Column(Float, nullable=True)  # pixels

    # Point cloud stats
    point_count = Column(Integer, nullable=True)
    point_density = Column(Float, nullable=True)  # points per cubic meter

    # Mesh stats
    vertex_count = Column(Integer, nullable=True)
    face_count = Column(Integer, nullable=True)
    mesh_volume = Column(Float, nullable=True)  # cubic meters
    mesh_surface_area = Column(Float, nullable=True)  # square meters

    # Texture stats
    texture_resolution = Column(String, nullable=True)  # e.g. "2048x2048"
    texture_quality_score = Column(Float, nullable=True)  # 0.0-1.0

    # Quality metrics
    overall_quality = Column(String, nullable=True)  # high, medium, low
    alignment_confidence = Column(Float, nullable=True)  # 0.0-1.0
    completeness_score = Column(Float, nullable=True)  # 0.0-1.0

    # Timing (seconds)
    feature_detection_time = Column(Float, nullable=True)
    matching_time = Column(Float, nullable=True)
    sfm_time = Column(Float, nullable=True)
    mesh_generation_time = Column(Float, nullable=True)
    texture_time = Column(Float, nullable=True)
    optimization_time = Column(Float, nullable=True)
    total_time = Column(Float, nullable=True)

    # Errors and warnings
    errors = Column(Text, nullable=True)  # JSON array
    warnings = Column(Text, nullable=True)  # JSON array

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    reconstruction_job = relationship("ReconstructionJob", backref="metadata_detail")
