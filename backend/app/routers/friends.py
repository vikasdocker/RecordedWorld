from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.core.auth import get_current_user_id
from app.models.user import User
from app.models.friendship import Friendship
from app.schemas.friendship import (
    FriendRequestCreate,
    FriendshipResponse,
    FriendshipDetail,
    FriendStatusResponse,
)
from app.services.friendship_service import FriendshipService

router = APIRouter(prefix="/api/friends", tags=["friends"])


def _get_user_id(
    user_id: Optional[int] = Query(None, description="User ID (query param fallback)"),
    x_user_id: Optional[str] = Header(None),
) -> int:
    """Get user ID from header or query param."""
    if x_user_id is not None:
        try:
            uid = int(x_user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="X-User-ID must be an integer")
        if uid <= 0:
            raise HTTPException(status_code=400, detail="X-User-ID must be positive")
        return uid
    if user_id is not None:
        if user_id <= 0:
            raise HTTPException(status_code=400, detail="user_id must be positive")
        return user_id
    raise HTTPException(status_code=401, detail="user_id query param or X-User-ID header required")


@router.post("/request", response_model=FriendshipResponse)
def send_friend_request(
    body: FriendRequestCreate,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        friendship = FriendshipService.send_request(db, user_id, body.addressee_id)
        return friendship
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/accept/{friendship_id}", response_model=FriendshipResponse)
def accept_friend_request(
    friendship_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        friendship = FriendshipService.accept_request(db, friendship_id, user_id)
        return friendship
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reject/{friendship_id}", response_model=FriendshipResponse)
def reject_friend_request(
    friendship_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        friendship = FriendshipService.reject_request(db, friendship_id, user_id)
        return friendship
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{friendship_id}")
def remove_friend(
    friendship_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        FriendshipService.remove_friend(db, friendship_id, user_id)
        return {"status": "removed"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=List[FriendshipDetail])
def list_friends(
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    friends = FriendshipService.get_friends(db, user_id)
    return [
        FriendshipDetail(
            id=f.id,
            user_id=u.id,
            username=u.username,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            status=f.status,
            created_at=f.created_at,
        )
        for f, u in friends
    ]


@router.get("/pending", response_model=List[FriendshipDetail])
def list_pending_requests(
    direction: str = "received",
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    if direction not in ("received", "sent"):
        raise HTTPException(status_code=400, detail="direction must be 'received' or 'sent'")
    requests = FriendshipService.get_pending_requests(db, user_id, direction)
    return [
        FriendshipDetail(
            id=f.id,
            user_id=u.id,
            username=u.username,
            display_name=u.display_name,
            avatar_url=u.avatar_url,
            status=f.status,
            created_at=f.created_at,
        )
        for f, u in requests
    ]


@router.post("/block/{target_user_id}")
def block_user(
    target_user_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        FriendshipService.block_user(db, user_id, target_user_id)
        return {"status": "blocked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/block/{target_user_id}")
def unblock_user(
    target_user_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    try:
        FriendshipService.unblock_user(db, user_id, target_user_id)
        return {"status": "unblocked"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/blocked", response_model=List[FriendshipDetail])
def list_blocked_users(
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    blocked = FriendshipService.get_blocked_users(db, user_id)
    results = []
    for f in blocked:
        u = db.query(User).filter(User.id == f.addressee_id).first()
        if u:
            results.append(FriendshipDetail(
                id=f.id,
                user_id=u.id,
                username=u.username,
                display_name=u.display_name,
                avatar_url=u.avatar_url,
                status=f.status,
                created_at=f.created_at,
            ))
    return results


@router.get("/check/{target_user_id}", response_model=FriendStatusResponse)
def check_friend_status(
    target_user_id: int,
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    if user_id == target_user_id:
        return FriendStatusResponse(
            user_id=target_user_id,
            are_friends=False,
            pending_request=None,
            blocked=False,
        )

    are_friends = FriendshipService.are_friends(db, user_id, target_user_id)
    blocked = FriendshipService.is_blocked(db, user_id, target_user_id)

    pending = None
    if not are_friends and not blocked:
        existing = FriendshipService.get_friendship(db, user_id, target_user_id)
        if existing and existing.status == "pending":
            pending = "sent" if existing.requester_id == user_id else "received"

    return FriendStatusResponse(
        user_id=target_user_id,
        are_friends=are_friends,
        pending_request=pending,
        blocked=blocked,
    )


# =============================================================================
# Search users (for adding friends)
# =============================================================================

@router.get("/search")
def search_users(
    q: str = Query(..., min_length=1, description="Search username or display name"),
    user_id: int = Depends(_get_user_id),
    db: Session = Depends(get_db),
):
    """Search for users by username or display name."""
    pattern = f"%{q}%"
    users = db.query(User).filter(
        (User.username.ilike(pattern)) | (User.display_name.ilike(pattern)),
        User.id != user_id,
    ).limit(20).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name,
            "avatar_url": u.avatar_url,
        }
        for u in users
    ]
