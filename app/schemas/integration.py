"""
Integration-related Pydantic schemas.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class IntegrationProvider(str, Enum):
    """Supported integration providers."""
    GOOGLE = "google"
    SLACK = "slack"
    NOTION = "notion"
    STRIPE = "stripe"


class IntegrationBase(BaseModel):
    """Base integration schema."""
    provider: IntegrationProvider


class IntegrationCreate(IntegrationBase):
    """Schema for creating integration (internal use)."""
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: list[str] = []


class IntegrationUpdate(BaseModel):
    """Schema for updating integration."""
    is_active: bool | None = None


class IntegrationRead(BaseModel):
    """Schema for reading integration data."""
    id: str
    provider: IntegrationProvider
    is_active: bool
    scopes: list[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OAuthCallback(BaseModel):
    """OAuth callback data."""
    code: str
    state: str | None = None


class OAuthURL(BaseModel):
    """OAuth authorization URL response."""
    auth_url: str
    state: str
