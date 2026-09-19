from fastapi import Header, HTTPException
from typing import Optional


def get_current_user_id(x_user_id: Optional[str] = Header(None)) -> int:
    """
    Extract user ID from request header.

    Temporary auth mechanism until JWT is implemented.
    Clients must send X-User-ID header.
    """
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-ID header required")
    try:
        user_id = int(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="X-User-ID must be an integer")
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="X-User-ID must be positive")
    return user_id
