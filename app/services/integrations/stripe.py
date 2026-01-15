"""
Stripe integration.
"""
from datetime import datetime, timezone, timedelta

import httpx

from app.config import get_settings
from app.services.integrations.base import BaseIntegration, IntegrationData, TokenResponse

settings = get_settings()


class StripeIntegration(BaseIntegration):
    """Stripe integration for revenue metrics."""
    
    provider = "stripe"
    
    API_BASE = "https://api.stripe.com/v1"
    
    async def get_auth_url(self, state: str) -> str:
        """
        Stripe uses API keys, not OAuth.
        Return a form URL where users enter their API key.
        """
        # In production, you'd redirect to a form in your frontend
        # For now, return a placeholder
        return f"/integrations/stripe/setup?state={state}"
    
    async def exchange_code(self, code: str) -> TokenResponse:
        """
        For Stripe, the 'code' is actually the API key entered by user.
        """
        # Validate the API key by making a simple request
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE}/balance",
                headers={"Authorization": f"Bearer {code}"},
            )
            
            if response.status_code != 200:
                raise ValueError("Invalid Stripe API key")
        
        return TokenResponse(
            access_token=code,  # Store API key as access token
            refresh_token=None,
            expires_at=None,
            scopes=["read"],
        )
    
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Stripe API keys don't expire."""
        raise NotImplementedError("Stripe API keys do not expire")
    
    async def fetch_data(self, access_token: str) -> IntegrationData:
        """Fetch MRR, recent charges, and subscription changes."""
        headers = {"Authorization": f"Bearer {access_token}"}
        
        metrics = {
            "mrr": 0,
            "active_subscriptions": 0,
            "new_subscriptions_today": 0,
            "churned_today": 0,
            "recent_charges": [],
        }
        
        async with httpx.AsyncClient() as client:
            # Get active subscriptions for MRR calculation
            subs_response = await client.get(
                f"{self.API_BASE}/subscriptions",
                headers=headers,
                params={"status": "active", "limit": 100},
            )
            
            if subs_response.status_code == 200:
                subs_data = subs_response.json()
                subscriptions = subs_data.get("data", [])
                
                metrics["active_subscriptions"] = len(subscriptions)
                
                # Calculate MRR (simplified)
                for sub in subscriptions:
                    for item in sub.get("items", {}).get("data", []):
                        price = item.get("price", {})
                        amount = price.get("unit_amount", 0) / 100  # Convert cents to dollars
                        interval = price.get("recurring", {}).get("interval", "month")
                        
                        # Normalize to monthly
                        if interval == "year":
                            amount = amount / 12
                        elif interval == "week":
                            amount = amount * 4
                        
                        metrics["mrr"] += amount
            
            # Get recent charges
            charges_response = await client.get(
                f"{self.API_BASE}/charges",
                headers=headers,
                params={"limit": 10},
            )
            
            if charges_response.status_code == 200:
                charges_data = charges_response.json()
                
                for charge in charges_data.get("data", []):
                    metrics["recent_charges"].append({
                        "id": charge.get("id"),
                        "amount": charge.get("amount", 0) / 100,
                        "currency": charge.get("currency", "usd"),
                        "status": charge.get("status"),
                        "customer": charge.get("customer"),
                        "created": datetime.fromtimestamp(
                            charge.get("created", 0), 
                            tz=timezone.utc
                        ).isoformat(),
                    })
            
            # Get subscription events from today
            today_start = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            
            events_response = await client.get(
                f"{self.API_BASE}/events",
                headers=headers,
                params={
                    "type": "customer.subscription.created",
                    "created[gte]": int(today_start.timestamp()),
                    "limit": 100,
                },
            )
            
            if events_response.status_code == 200:
                events_data = events_response.json()
                metrics["new_subscriptions_today"] = len(events_data.get("data", []))
            
            # Get churn events from today
            churn_response = await client.get(
                f"{self.API_BASE}/events",
                headers=headers,
                params={
                    "type": "customer.subscription.deleted",
                    "created[gte]": int(today_start.timestamp()),
                    "limit": 100,
                },
            )
            
            if churn_response.status_code == 200:
                churn_data = churn_response.json()
                metrics["churned_today"] = len(churn_data.get("data", []))
        
        return IntegrationData(
            provider=self.provider,
            data=metrics,
            fetched_at=datetime.now(timezone.utc),
        )
