"""Testing and feedback API endpoints."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.services.testing import testing

router = APIRouter(prefix="/api/testing", tags=["testing"])


class FeedbackSubmit(BaseModel):
    user_id: int
    category: str
    severity: str
    title: str
    description: str
    screenshot_path: Optional[str] = None
    device_info: Optional[dict] = None


class SessionEnd(BaseModel):
    session_id: int
    captures_created: int = 0
    worlds_explored: int = 0
    errors_encountered: int = 0
    avg_fps: float = 0
    avg_latency_ms: float = 0


@router.post("/feedback")
def submit_feedback(feedback: FeedbackSubmit):
    """Submit user feedback."""
    entry = testing.submit_feedback(**feedback.model_dump())
    return {"id": entry.id, "status": "submitted"}


@router.get("/feedback")
def list_feedback(category: Optional[str] = None, severity: Optional[str] = None):
    """List all feedback, optionally filtered."""
    if category:
        entries = testing.get_feedback_by_category(category)
    elif severity:
        entries = testing.get_feedback_by_severity(severity)
    else:
        entries = testing.feedback
    return {"feedback": [{"id": e.id, "title": e.title, "category": e.category, "severity": e.severity, "status": e.status} for e in entries]}


@router.post("/session/start")
def start_session(user_id: int):
    """Start a testing session."""
    session = testing.start_session(user_id)
    return {"session_id": session.id, "start_time": session.start_time}


@router.post("/session/end")
def end_session(data: SessionEnd):
    """End a testing session with stats."""
    testing.end_session(**data.model_dump())
    return {"status": "ended"}


@router.get("/summary")
def get_summary():
    """Get testing summary statistics."""
    return testing.get_summary()
