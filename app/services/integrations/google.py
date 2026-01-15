"""
Google integration (Calendar + Gmail).
"""
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.services.integrations.base import BaseIntegration, IntegrationData, TokenResponse

settings = get_settings()


class GoogleIntegration(BaseIntegration):
    """Google Calendar and Gmail integration."""
    
    provider = "google"
    
    SCOPES = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
    ]
    
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    CALENDAR_API = "https://www.googleapis.com/calendar/v3"
    GMAIL_API = "https://www.googleapis.com/gmail/v1"
    
    async def get_auth_url(self, state: str) -> str:
        """Generate Google OAuth authorization URL."""
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": settings.google_redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str) -> TokenResponse:
        """Exchange authorization code for tokens."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.google_redirect_uri,
                },
            )
            response.raise_for_status()
            data = response.json()
        
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + __import__("datetime").timedelta(seconds=data["expires_in"])
        
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
            scopes=data.get("scope", "").split(),
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Refresh Google access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()
        
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + __import__("datetime").timedelta(seconds=data["expires_in"])
        
        return TokenResponse(
            access_token=data["access_token"],
            refresh_token=refresh_token,  # Google doesn't return new refresh token
            expires_at=expires_at,
            scopes=data.get("scope", "").split(),
        )
    
    async def fetch_data(self, access_token: str) -> IntegrationData:
        """Fetch calendar events and important emails."""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            # Fetch today's calendar events
            now = datetime.now(timezone.utc)
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            time_max = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
            
            calendar_response = await client.get(
                f"{self.CALENDAR_API}/calendars/primary/events",
                headers=headers,
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": "true",
                    "orderBy": "startTime",
                },
            )
            
            events = []
            if calendar_response.status_code == 200:
                calendar_data = calendar_response.json()
                events = [
                    {
                        "id": event.get("id"),
                        "summary": event.get("summary", "No title"),
                        "start": event.get("start", {}).get("dateTime") or event.get("start", {}).get("date"),
                        "end": event.get("end", {}).get("dateTime") or event.get("end", {}).get("date"),
                        "attendees": [a.get("email") for a in event.get("attendees", [])],
                        "location": event.get("location"),
                    }
                    for event in calendar_data.get("items", [])
                ]
            
            # Fetch unread important emails
            gmail_response = await client.get(
                f"{self.GMAIL_API}/users/me/messages",
                headers=headers,
                params={
                    "q": "is:unread is:important",
                    "maxResults": 10,
                },
            )
            
            emails = []
            if gmail_response.status_code == 200:
                gmail_data = gmail_response.json()
                
                # Fetch details for each message
                for msg in gmail_data.get("messages", [])[:10]:
                    msg_response = await client.get(
                        f"{self.GMAIL_API}/users/me/messages/{msg['id']}",
                        headers=headers,
                        params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                    )
                    
                    if msg_response.status_code == 200:
                        msg_data = msg_response.json()
                        headers_dict = {
                            h["name"]: h["value"]
                            for h in msg_data.get("payload", {}).get("headers", [])
                        }
                        emails.append({
                            "id": msg["id"],
                            "from": headers_dict.get("From", "Unknown"),
                            "subject": headers_dict.get("Subject", "No subject"),
                            "date": headers_dict.get("Date"),
                            "snippet": msg_data.get("snippet", ""),
                        })
        
        return IntegrationData(
            provider=self.provider,
            data={
                "calendar_events": events,
                "emails": emails,
            },
            fetched_at=datetime.now(timezone.utc),
        )
