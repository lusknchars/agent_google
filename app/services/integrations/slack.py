"""
Slack integration.
"""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.services.integrations.base import BaseIntegration, IntegrationData, TokenResponse

settings = get_settings()


class SlackIntegration(BaseIntegration):
    """Slack workspace integration."""
    
    provider = "slack"
    
    SCOPES = [
        "channels:history",
        "channels:read",
        "im:history",
        "im:read",
        "mpim:history",
        "mpim:read",
        "users:read",
    ]
    
    AUTH_URL = "https://slack.com/oauth/v2/authorize"
    TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    API_BASE = "https://slack.com/api"
    
    async def get_auth_url(self, state: str) -> str:
        """Generate Slack OAuth authorization URL."""
        params = {
            "client_id": settings.slack_client_id,
            "redirect_uri": settings.slack_redirect_uri,
            "scope": ",".join(self.SCOPES),
            "state": state,
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.slack_client_id,
                    "client_secret": settings.slack_client_secret,
                    "code": code,
                    "redirect_uri": settings.slack_redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        if not data.get("ok"):
            raise ValueError(f"Slack OAuth error: {data.get('error')}")
        
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=None,  # Slack tokens don't expire
            scopes=data.get("scope", "").split(","),
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh Slack access token (if rotatable tokens enabled)."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.slack_client_id,
                    "client_secret": settings.slack_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        if not data.get("ok"):
            raise ValueError(f"Slack token refresh error: {data.get('error')}")
        
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=None,
            scopes=data.get("scope", "").split(","),
        )
    
    async def fetch_data(self, access_token: str) -> IntegrationData:
        """Fetch mentions and direct messages from last 24 hours."""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get messages from last 24 hours
        oldest = (datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()
        
        messages = []
        
        async with httpx.AsyncClient() as client:
            # Get user info
            user_response = await client.get(
                f"{self.API_BASE}/auth.test",
                headers=headers,
            )
            user_data = user_response.json()
            current_user_id = user_data.get("user_id", "")
            
            # Get conversations (channels and DMs)
            convos_response = await client.get(
                f"{self.API_BASE}/conversations.list",
                headers=headers,
                params={"types": "public_channel,private_channel,im,mpim"},
            )
            
            if convos_response.status_code == 200:
                convos_data = convos_response.json()
                
                for channel in convos_data.get("channels", [])[:10]:
                    # Get recent messages from each channel
                    history_response = await client.get(
                        f"{self.API_BASE}/conversations.history",
                        headers=headers,
                        params={
                            "channel": channel["id"],
                            "oldest": oldest,
                            "limit": 20,
                        },
                    )
                    
                    if history_response.status_code == 200:
                        history_data = history_response.json()
                        
                        for msg in history_data.get("messages", []):
                            # Check for mentions or DMs
                            is_mention = f"<@{current_user_id}>" in msg.get("text", "")
                            is_dm = channel.get("is_im", False)
                            
                            if is_mention or is_dm:
                                messages.append({
                                    "channel": channel.get("name", channel["id"]),
                                    "is_dm": is_dm,
                                    "is_mention": is_mention,
                                    "user": msg.get("user"),
                                    "text": msg.get("text", ""),
                                    "timestamp": msg.get("ts"),
                                })
        
        return IntegrationData(
            provider=self.provider,
            data={
                "messages": messages[:20],  # Limit to 20 most relevant
            },
            fetched_at=datetime.now(timezone.utc),
        )
