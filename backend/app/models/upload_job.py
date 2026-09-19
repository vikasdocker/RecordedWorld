"""
Upload Job Model

Tracks file uploads with resumable support.
"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class UploadJob(Base):
    """
    Tracks file uploads with progress and resumable support.
    
    Upload States:
      CREATED → UPLOADING → VALIDATING → COMPLETE
                       → FAILED
                       → CANCELLED
    """
    __tablename__ = "upload_jobs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, nullable=False, index=True)

    # Ownership
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    capture_id = Column(Integer, ForeignKey("captures.id"), nullable=True, index=True)

    # File info
    filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    mime_type = Column(String, nullable=True)
    file_hash = Column(String, nullable=True)  # SHA-256 for integrity

    # Upload progress
    status = Column(String, nullable=False, default="created")  # created, uploading, validating, complete, failed, cancelled
    bytes_uploaded = Column(Integer, default=0)
    progress = Column(Float, default=0.0)  # 0-100

    # Resumable upload support (tus protocol)
    upload_offset = Column(Integer, default=0)
    upload_url = Column(String, nullable=True)  # URL for resumable upload
    tus_upload_id = Column(String, nullable=True, index=True)  # tus upload ID

    # Validation
    validation_status = Column(String, nullable=True)  # pending, passed, failed
    validation_errors = Column(Text, nullable=True)  # JSON array of errors

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)

    # Storage
    storage_path = Column(String, nullable=True)  # Final storage path
    storage_backend = Column(String, default="local")  # local, s3, gcs

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)  # When upload URL expires

    # Metadata
    client_info = Column(Text, nullable=True)  # JSON: user-agent, platform, etc.

    # Relationships
    user = relationship("User", backref="upload_jobs")
    capture = relationship("Capture", backref="upload_jobs")
