from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ReconstructionJob(Base):
    """
    A 3D reconstruction job.

    Job States:
      CREATED → QUEUED → PROCESSING → RECONSTRUCTING → ALIGNING → OPTIMIZING → VALIDATING → COMPLETE
                                                                                           → FAILED
                                                                                           → NEEDS_REVIEW
    """
    __tablename__ = "reconstruction_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, nullable=False, index=True)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    capture_id = Column(Integer, ForeignKey("captures.id"), nullable=True)

    # State
    status = Column(String, nullable=False, default="created")  # created, queued, processing, etc.
    progress = Column(Float, default=0.0)  # 0-100

    # Result
    result_asset_id = Column(String, nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Metadata
    pipeline_config = Column(Text, nullable=True)  # JSON config for reconstruction

    user = relationship("User", backref="reconstruction_jobs")
    capture = relationship("Capture", backref="reconstruction_jobs")
