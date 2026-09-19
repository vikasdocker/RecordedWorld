import shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.capture import Capture
from app.schemas.capture import CaptureCreate, CaptureResponse
from app.services.file_validator import validate_video_file
from app.services.metadata_extractor import extract_video_metadata

router = APIRouter(prefix="/api/captures", tags=["captures"])

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/", response_model=CaptureResponse)
async def upload_capture(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = "Untitled Capture",
    description: str = "",
    user_id: int = 1,
    latitude: float = None,
    longitude: float = None,
    heading: float = None,
    db: Session = Depends(get_db),
):
    # Save to temp location first for validation
    capture_dir = settings.UPLOAD_DIR / f"capture_{user_id}"
    capture_dir.mkdir(parents=True, exist_ok=True)
    file_path = capture_dir / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Validate video file
    validation = validate_video_file(str(file_path))
    if not validation.valid:
        # Remove invalid file
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=422,
            detail={"errors": validation.errors, "warnings": validation.warnings},
        )

    # Extract metadata
    try:
        metadata = extract_video_metadata(str(file_path))
        resolution = f"{metadata.width}x{metadata.height}"
        fps = metadata.fps
        duration = metadata.duration_seconds
    except Exception:
        resolution = None
        fps = None
        duration = None

    capture = Capture(
        user_id=user_id,
        title=title,
        description=description,
        video_path=str(file_path),
        status="uploaded",
        video_resolution=resolution,
        video_fps=fps,
        capture_duration=duration,
        latitude=latitude,
        longitude=longitude,
        device_orientation=heading,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    return capture


@router.get("/", response_model=list[CaptureResponse])
def list_captures(user_id: int = 1, db: Session = Depends(get_db)):
    return db.query(Capture).filter(Capture.user_id == user_id).all()


@router.get("/{capture_id}", response_model=CaptureResponse)
def get_capture(capture_id: int, db: Session = Depends(get_db)):
    capture = db.query(Capture).filter(Capture.id == capture_id).first()
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    return capture
