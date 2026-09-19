"""Pipeline API endpoints for end-to-end flow."""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.capture import Capture
from app.models.location import Location
from app.core.spatial_index import compute_grid_cell_id
from app.core.geospatial import WGS84Coordinate
from app.services.e2e_pipeline import pipeline
from app.services.testing import testing

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post("/process/{capture_id}")
async def start_pipeline(
    capture_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start the full E2E pipeline for a capture."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    if capture.status == "processing":
        return {"status": "already_processing", "capture_id": capture_id}

    capture.status = "processing"
    db.commit()

    background_tasks.add_task(
        _run_pipeline_task,
        capture_id,
        capture.video_path,
    )

    return {"status": "pipeline_started", "capture_id": capture_id}


async def _run_pipeline_task(capture_id: int, video_path: str):
    """Background task to run the pipeline."""
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        result = await pipeline.run_pipeline(capture_id, video_path)

        capture = db.query(Capture).filter(Capture.id == capture_id).first()
        if capture:
            capture.status = result.status
            if result.model_path:
                capture.model_3d_path = result.model_path
            db.commit()

            # Auto-create Location from capture after successful processing
            if capture.status == "ready" and capture.latitude and capture.longitude:
                existing_loc = db.query(Location).filter(Location.capture_id == capture_id).first()
                if not existing_loc:
                    loc = Location(
                        creator_id=capture.user_id,
                        capture_id=capture_id,
                        title=capture.title or f"Capture {capture_id}",
                        description=capture.description,
                        latitude=capture.latitude,
                        longitude=capture.longitude,
                        altitude=capture.altitude,
                        grid_cell_id=compute_grid_cell_id(
                            WGS84Coordinate(capture.latitude, capture.longitude, capture.altitude or 0.0),
                            100.0,
                        ),
                        asset_id=f"capture_{capture_id}/model.glb",
                        accuracy_meters=capture.gps_accuracy,
                        confidence=capture.alignment_confidence,
                        alignment_method=capture.alignment_method,
                        visibility="public",
                        moderation_state="approved",
                    )
                    db.add(loc)
                    db.commit()
    finally:
        db.close()


@router.get("/status/{capture_id}")
async def get_pipeline_status(capture_id: int):
    """Get current pipeline processing status."""
    status = pipeline.get_job_status(capture_id)
    if not status:
        return {"status": "not_found", "capture_id": capture_id}
    return {"capture_id": capture_id, **status}


@router.get("/status")
async def get_all_pipeline_status():
    """Get status of all active pipeline jobs."""
    return {"jobs": pipeline.get_all_jobs()}


@router.post("/retry/{capture_id}")
async def retry_pipeline(
    capture_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Retry a failed pipeline."""
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    capture.status = "processing"
    db.commit()

    background_tasks.add_task(
        _run_pipeline_task,
        capture_id,
        capture.video_path,
    )

    return {"status": "retry_started", "capture_id": capture_id}
