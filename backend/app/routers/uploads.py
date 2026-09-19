"""
Upload Jobs API endpoints — resumable uploads with TUS support.
"""
import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timezone, timedelta

from app.core.config import settings
from app.core.database import get_db
from app.models.upload_job import UploadJob
from app.schemas.event import EventResponse  # reuse if needed

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/", response_model=dict)
def create_upload_job(
    filename: str = Query(...),
    file_size: int = Query(..., gt=0),
    mime_type: str = Query(None),
    user_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """Create a new upload job for resumable upload."""
    job_id = f"up-{uuid.uuid4().hex[:16]}"
    job = UploadJob(
        job_id=job_id,
        user_id=user_id,
        filename=filename,
        file_size=file_size,
        mime_type=mime_type,
        status="created",
        bytes_uploaded=0,
        progress=0.0,
        upload_url=f"/api/uploads/{job_id}/data",
        tus_upload_id=job_id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "job_id": job.job_id,
        "upload_url": job.upload_url,
        "tus_upload_id": job.tus_upload_id,
        "file_size": job.file_size,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }


@router.get("/", response_model=List[dict])
def list_upload_jobs(
    user_id: int = Query(...),
    status: str = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List upload jobs for a user."""
    query = db.query(UploadJob).filter(UploadJob.user_id == user_id)
    if status:
        query = query.filter(UploadJob.status == status)
    jobs = query.order_by(UploadJob.created_at.desc()).limit(limit).all()
    return [
        {
            "job_id": j.job_id,
            "filename": j.filename,
            "file_size": j.file_size,
            "status": j.status,
            "bytes_uploaded": j.bytes_uploaded,
            "progress": j.progress,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.get("/{job_id}", response_model=dict)
def get_upload_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Get upload job status."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")
    return {
        "job_id": job.job_id,
        "filename": job.filename,
        "file_size": job.file_size,
        "status": job.status,
        "bytes_uploaded": job.bytes_uploaded,
        "progress": job.progress,
        "upload_url": job.upload_url,
        "tus_upload_id": job.tus_upload_id,
        "validation_status": job.validation_status,
        "error_message": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "expires_at": job.expires_at.isoformat() if job.expires_at else None,
    }


@router.put("/{job_id}/data")
def upload_data_chunk(
    job_id: str,
    offset: int = Query(0, ge=0),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a chunk of data (TUS-style resumable upload)."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    if job.status in ("complete", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Job is {job.status}")

    # Validate offset matches expected position
    if offset != job.bytes_uploaded:
        raise HTTPException(
            status_code=409,
            detail=f"Offset mismatch: expected {job.bytes_uploaded}, got {offset}",
        )

    # Read chunk
    chunk = file.file.read()
    chunk_size = len(chunk)

    # Append to storage
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_path = settings.UPLOAD_DIR / f"upload_{job_id}.tmp"
    mode = "ab" if offset > 0 else "wb"
    with open(upload_path, mode) as f:
        f.write(chunk)

    # Update progress
    job.bytes_uploaded += chunk_size
    job.progress = min(100.0, (job.bytes_uploaded / job.file_size) * 100) if job.file_size > 0 else 0.0
    job.status = "uploading"

    if job.bytes_uploaded >= job.file_size:
        job.status = "validating"
        job.progress = 100.0

    db.commit()

    return {
        "bytes_uploaded": job.bytes_uploaded,
        "file_size": job.file_size,
        "progress": job.progress,
        "status": job.status,
    }


@router.post("/{job_id}/complete")
def complete_upload(
    job_id: str,
    file_hash: str = Query(None, description="SHA-256 hash for integrity check"),
    db: Session = Depends(get_db),
):
    """Mark upload as complete and validate integrity."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    if job.status == "complete":
        return {"status": "already_complete", "job_id": job_id}

    if job.bytes_uploaded < job.file_size:
        raise HTTPException(
            status_code=400,
            detail=f"Incomplete upload: {job.bytes_uploaded}/{job.file_size} bytes",
        )

    # Optional hash verification
    if file_hash:
        upload_path = settings.UPLOAD_DIR / f"upload_{job_id}.tmp"
        if upload_path.exists():
            actual_hash = hashlib.sha256(upload_path.read_bytes()).hexdigest()
            if actual_hash != file_hash:
                job.status = "failed"
                job.error_message = f"Hash mismatch: expected {file_hash}, got {actual_hash}"
                job.validation_status = "failed"
                db.commit()
                raise HTTPException(status_code=400, detail="File integrity check failed")
            job.file_hash = actual_hash

    job.status = "complete"
    job.validation_status = "passed"
    job.completed_at = datetime.now(timezone.utc)
    db.commit()

    return {"status": "complete", "job_id": job_id}


@router.post("/{job_id}/cancel")
def cancel_upload(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Cancel an upload job."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    if job.status == "complete":
        raise HTTPException(status_code=400, detail="Cannot cancel completed upload")

    job.status = "cancelled"
    db.commit()

    return {"status": "cancelled", "job_id": job_id}


@router.post("/{job_id}/resume")
def resume_upload(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Resume a failed or cancelled upload."""
    job = db.query(UploadJob).filter(UploadJob.job_id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Upload job not found")

    if job.status not in ("failed", "cancelled"):
        raise HTTPException(status_code=400, detail=f"Cannot resume job in status: {job.status}")

    if job.retry_count >= job.max_retries:
        raise HTTPException(status_code=400, detail="Max retries exceeded")

    job.status = "uploading"
    job.retry_count += 1
    job.error_message = None
    db.commit()

    return {
        "status": "resumed",
        "job_id": job_id,
        "retry_count": job.retry_count,
        "bytes_uploaded": job.bytes_uploaded,
    }
