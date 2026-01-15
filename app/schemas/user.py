"""
User-related Pydantic schemas.
"""
from datetime import datetime, time
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """Schema for updating user."""
    full_name: str | None = None
    timezone: str | None = None
    briefing_time: time | None = None


class UserRead(UserBase):
    """Schema for reading user data."""
    id: str
    timezone: str
    briefing_time: time
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT token response schema."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """JWT token payload schema."""
    sub: str  # User ID
    exp: datetime
    type: str  # "access" or "refresh"


class LoginRequest(BaseModel):
    """Login request schema."""
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request schema."""
    refresh_token: str
