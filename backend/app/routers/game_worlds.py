from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.game_world import GameWorld
from app.schemas.capture import CaptureResponse

router = APIRouter(prefix="/api/worlds", tags=["worlds"])


@router.get("/")
def list_worlds(db: Session = Depends(get_db)):
    return db.query(GameWorld).all()


@router.get("/{world_id}")
def get_world(world_id: int, db: Session = Depends(get_db)):
    world = db.query(GameWorld).filter(GameWorld.id == world_id).first()
    if not world:
        raise HTTPException(status_code=404, detail="World not found")
    return {
        "id": world.id,
        "name": world.name,
        "capture_id": world.capture_id,
        "spawn": {"x": world.spawn_x, "y": world.spawn_y, "z": world.spawn_z},
        "max_players": world.max_players,
        "created_at": world.created_at.isoformat(),
    }
