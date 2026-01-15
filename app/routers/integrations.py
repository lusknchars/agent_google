"""
Integrations router for OAuth flows.
"""
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.integration import Integration
from app.models.user import User
from app.schemas.integration import IntegrationRead, IntegrationProvider, OAuthURL
from app.services.auth import get_current_user
from app.services.integrations import (
    GoogleIntegration,
    SlackIntegration,
    NotionIntegration,
    StripeIntegration,
)
from app.services.integrations.base import BaseIntegration

router = APIRouter(prefix="/integrations", tags=["Integrations"])

# Map providers to their integration classes
INTEGRATIONS: dict[str, type[BaseIntegration]] = {
    "google": GoogleIntegration,
    "slack": SlackIntegration,
    "notion": NotionIntegration,
    "stripe": StripeIntegration,
}

# Simple in-memory state storage (use Redis in production)
_oauth_states: dict[str, str] = {}


def get_integration(provider: str) -> BaseIntegration:
    """Get integration instance by provider name."""
    if provider not in INTEGRATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown provider: {provider}",
        )
    return INTEGRATIONS[provider]()


@router.get("", response_model=list[IntegrationRead])
async def list_integrations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Integration]:
    """List all connected integrations for current user."""
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == current_user.id,
            Integration.is_active == True,
        )
    )
    return list(result.scalars().all())


@router.get("/{provider}/auth", response_model=OAuthURL)
async def get_oauth_url(
    provider: IntegrationProvider,
    current_user: User = Depends(get_current_user),
) -> OAuthURL:
    """Get OAuth authorization URL for a provider."""
    integration = get_integration(provider.value)
    
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = current_user.id
    
    auth_url = await integration.get_auth_url(state)
    
    return OAuthURL(auth_url=auth_url, state=state)


@router.get("/{provider}/callback")
async def oauth_callback(
    provider: IntegrationProvider,
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle OAuth callback from provider."""
    # Verify state
    user_id = _oauth_states.pop(state, None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired state",
        )
    
    integration = get_integration(provider.value)
    
    try:
        tokens = await integration.exchange_code(code)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to exchange code: {str(e)}",
        )
    
    # Check if integration already exists
    result = await db.execute(
        select(Integration).where(
            Integration.user_id == user_id,
            Integration.provider == provider.value,
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        # Update existing integration
        existing.access_token = tokens.access_token
        existing.refresh_token = tokens.refresh_token
        existing.token_expires_at = tokens.expires_at
        existing.scopes = tokens.scopes or []
        existing.is_active = True
    else:
        # Create new integration
        new_integration = Integration(
            user_id=user_id,
            provider=provider.value,
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
            token_expires_at=tokens.expires_at,
            scopes=tokens.scopes or [],
        )
        db.add(new_integration)
    
    await db.commit()
    
    # Redirect to frontend success page
    return RedirectResponse(url="/integrations/success")


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_integration(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Disconnect an integration."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    integration.is_active = False
    await db.commit()


@router.post("/{integration_id}/refresh", response_model=IntegrationRead)
async def refresh_integration_token(
    integration_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Integration:
    """Manually refresh an integration's access token."""
    result = await db.execute(
        select(Integration).where(
            Integration.id == integration_id,
            Integration.user_id == current_user.id,
        )
    )
    integration = result.scalar_one_or_none()
    
    if not integration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    
    if not integration.refresh_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No refresh token available",
        )
    
    integration_service = get_integration(integration.provider)
    
    try:
        tokens = await integration_service.refresh_token(integration.refresh_token)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This provider does not support token refresh",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to refresh token: {str(e)}",
        )
    
    integration.access_token = tokens.access_token
    if tokens.refresh_token:
        integration.refresh_token = tokens.refresh_token
    integration.token_expires_at = tokens.expires_at
    
    await db.commit()
    await db.refresh(integration)
    
    return integration
