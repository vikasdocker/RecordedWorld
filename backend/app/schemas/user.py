from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: str


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    location_sharing: bool = False
    is_active: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class UserPublic(BaseModel):
    """Public user info (no sensitive fields)."""
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
