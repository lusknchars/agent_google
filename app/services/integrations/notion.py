"""
Notion integration.
"""
from datetime import datetime, timezone
from urllib.parse import urlencode
import base64

import httpx

from app.config import get_settings
from app.services.integrations.base import BaseIntegration, IntegrationData, TokenResponse

settings = get_settings()


class NotionIntegration(BaseIntegration):
    """Notion workspace integration."""
    
    provider = "notion"
    
    AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
    TOKEN_URL = "https://api.notion.com/v1/oauth/token"
    API_BASE = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"
    
    async def get_auth_url(self, state: str) -> str:
        """Generate Notion OAuth authorization URL."""
        params = {
            "client_id": settings.notion_client_id,
            "redirect_uri": settings.notion_redirect_uri,
            "response_type": "code",
            "state": state,
            "owner": "user",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for tokens."""
        # Notion uses basic auth for token exchange
        credentials = f"{settings.notion_client_id}:{settings.notion_client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/json",
                },
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.notion_redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=None,  # Notion doesn't use refresh tokens
            expires_at=None,
            scopes=[],
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Notion tokens don't expire, so refresh is not needed."""
        raise NotImplementedError("Notion tokens do not expire")
    
    async def fetch_data(self, access_token: str) -> IntegrationData:
        """Fetch pending tasks and recent updates from Notion."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }
        
        tasks = []
        
        async with httpx.AsyncClient() as client:
            # Search for database items (tasks)
            search_response = await client.post(
                f"{self.API_BASE}/search",
                headers=headers,
                json={
                    "filter": {"property": "object", "value": "page"},
                    "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                    "page_size": 20,
                },
            )
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                
                for page in search_data.get("results", []):
                    # Extract title from properties
                    title = "Untitled"
                    properties = page.get("properties", {})
                    
                    # Try to find title property
                    for prop_name, prop_data in properties.items():
                        if prop_data.get("type") == "title":
                            title_content = prop_data.get("title", [])
                            if title_content:
                                title = title_content[0].get("plain_text", "Untitled")
                            break
                    
                    # Check for status/checkbox properties
                    is_done = False
                    has_status = False
                    
                    for prop_name, prop_data in properties.items():
                        if prop_data.get("type") == "checkbox":
                            is_done = prop_data.get("checkbox", False)
                            has_status = True
                            break
                        elif prop_data.get("type") == "status":
                            status = prop_data.get("status", {})
                            is_done = status.get("name", "").lower() in ["done", "complete", "completed"]
                            has_status = True
                            break
                    
                    # Only include incomplete tasks
                    if has_status and not is_done:
                        tasks.append({
                            "id": page.get("id"),
                            "title": title,
                            "url": page.get("url"),
                            "last_edited": page.get("last_edited_time"),
                            "is_done": is_done,
                        })
        
        return IntegrationData(
            provider=self.provider,
            data={
                "tasks": tasks[:10],  # Limit to 10 most recent pending tasks
            },
            fetched_at=datetime.now(timezone.utc),
        )
