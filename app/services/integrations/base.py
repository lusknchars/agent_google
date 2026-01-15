"""
Base integration interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class TokenResponse:
    """OAuth token response."""
    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] | None = None


@dataclass
class IntegrationData:
    """Data fetched from an integration."""
    provider: str
    data: dict[str, Any]
    fetched_at: datetime


class BaseIntegration(ABC):
    """Abstract base class for all integrations."""
    
    provider: str = ""
    
    @abstractmethod
    async def get_auth_url(self, state: str) -> str:
        """
        Generate OAuth authorization URL.
        
        Args:
            state: Random state string for CSRF protection
            
        Returns:
            Authorization URL to redirect user to
        """
        pass
    
    @abstractmethod
    async def exchange_code(self, code: str) -> TokenResponse:
        """
        Exchange authorization code for tokens.
        
        Args:
            code: Authorization code from OAuth callback
            
        Returns:
            TokenResponse with access and refresh tokens
        """
        pass
    
    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: Current refresh token
            
        Returns:
            TokenResponse with new access token
        """
        pass
    
    @abstractmethod
    async def fetch_data(self, access_token: str) -> IntegrationData:
        """
        Fetch relevant data for briefings.
        
        Args:
            access_token: Valid access token
            
        Returns:
            IntegrationData with provider-specific data
        """
        pass
