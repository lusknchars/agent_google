"""
Briefing generation service.
"""
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.briefing import Briefing
from app.models.integration import Integration
from app.schemas.briefing import AggregatedData
from app.services.integrations import (
    GoogleIntegration,
    SlackIntegration,
    NotionIntegration,
    StripeIntegration,
)
from app.services.integrations.base import BaseIntegration

settings = get_settings()

INTEGRATIONS: dict[str, type[BaseIntegration]] = {
    "google": GoogleIntegration,
    "slack": SlackIntegration,
    "notion": NotionIntegration,
    "stripe": StripeIntegration,
}

BRIEFING_PROMPT = """You are a personal assistant for a busy startup founder. Your task is to synthesize data from multiple sources into a clear, actionable daily briefing that takes about 2 minutes to read.

Based on the following data from the founder's connected tools, generate a briefing with:

1. **Top 3 Priorities**: The most important things to focus on today, based on calendar, urgent messages, and pending tasks.

2. **Summary**: A natural language summary (2-3 paragraphs) covering:
   - Today's schedule and key meetings
   - Important messages requiring attention
   - Current business metrics status
   - Pending tasks that need progress

3. **Alerts**: Any urgent items requiring immediate attention (e.g., failed payments, urgent messages, overdue tasks). Only include if there are genuinely urgent items.

Here is the data from connected integrations:

## Calendar Events (Today)
{calendar_events}

## Unread Important Emails
{emails}

## Slack Messages (Mentions & DMs from last 24h)
{slack_messages}

## Pending Notion Tasks
{notion_tasks}

## Stripe Metrics
{stripe_metrics}

---

Respond in JSON format:
{{
    "priorities": ["Priority 1", "Priority 2", "Priority 3"],
    "summary": "Natural language summary here...",
    "alerts": ["Alert 1", "Alert 2"] // Can be empty array if no urgent items
}}

Be concise but comprehensive. Focus on actionable insights, not just listing data."""


class BriefingService:
    """Service for generating and managing briefings."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    
    async def aggregate_data(self, user_id: str) -> AggregatedData:
        """Pull data from all active integrations for a user."""
        result = await self.db.execute(
            select(Integration).where(
                Integration.user_id == user_id,
                Integration.is_active == True,
            )
        )
        integrations = result.scalars().all()
        
        aggregated = AggregatedData()
        
        for integration in integrations:
            if integration.provider not in INTEGRATIONS:
                continue
            
            service = INTEGRATIONS[integration.provider]()
            
            try:
                data = await service.fetch_data(integration.access_token)
                
                if integration.provider == "google":
                    aggregated.calendar_events = data.data.get("calendar_events", [])
                    aggregated.emails = data.data.get("emails", [])
                elif integration.provider == "slack":
                    aggregated.slack_messages = data.data.get("messages", [])
                elif integration.provider == "notion":
                    aggregated.notion_tasks = data.data.get("tasks", [])
                elif integration.provider == "stripe":
                    aggregated.stripe_metrics = data.data
                    
            except Exception as e:
                # Log error but continue with other integrations
                print(f"Error fetching data from {integration.provider}: {e}")
                continue
        
        return aggregated
    
    async def generate_briefing(self, user_id: str) -> Briefing:
        """Generate a new briefing for a user."""
        # Aggregate data from all integrations
        data = await self.aggregate_data(user_id)
        
        # Format data for prompt
        calendar_str = self._format_calendar(data.calendar_events)
        emails_str = self._format_emails(data.emails)
        slack_str = self._format_slack(data.slack_messages)
        notion_str = self._format_notion(data.notion_tasks)
        stripe_str = self._format_stripe(data.stripe_metrics)
        
        prompt = BRIEFING_PROMPT.format(
            calendar_events=calendar_str or "No calendar events today.",
            emails=emails_str or "No unread important emails.",
            slack_messages=slack_str or "No recent mentions or DMs.",
            notion_tasks=notion_str or "No pending tasks.",
            stripe_metrics=stripe_str or "Stripe not connected.",
        )
        
        # Call Claude API
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )
        
        # Parse response
        response_text = message.content[0].text
        
        # Extract JSON from response
        import json
        try:
            # Try to find JSON in the response
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            json_str = response_text[start:end]
            parsed = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            # Fallback if JSON parsing fails
            parsed = {
                "priorities": ["Review and respond to messages", "Attend scheduled meetings", "Complete pending tasks"],
                "summary": response_text,
                "alerts": [],
            }
        
        # Create briefing record
        briefing = Briefing(
            user_id=user_id,
            content=parsed,
            summary=parsed.get("summary", ""),
            priorities=parsed.get("priorities", []),
            alerts=parsed.get("alerts", []),
            raw_data=data.model_dump(),
        )
        
        self.db.add(briefing)
        await self.db.commit()
        await self.db.refresh(briefing)
        
        return briefing
    
    async def get_latest_briefing(self, user_id: str) -> Briefing | None:
        """Get the most recent briefing for a user."""
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.user_id == user_id)
            .order_by(Briefing.generated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_briefing(self, briefing_id: str, user_id: str) -> Briefing | None:
        """Get a specific briefing by ID."""
        result = await self.db.execute(
            select(Briefing).where(
                Briefing.id == briefing_id,
                Briefing.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
    
    async def list_briefings(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Briefing]:
        """List briefings for a user with pagination."""
        result = await self.db.execute(
            select(Briefing)
            .where(Briefing.user_id == user_id)
            .order_by(Briefing.generated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
    
    async def mark_as_read(self, briefing_id: str, user_id: str) -> Briefing | None:
        """Mark a briefing as read."""
        briefing = await self.get_briefing(briefing_id, user_id)
        
        if briefing and not briefing.read_at:
            briefing.read_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(briefing)
        
        return briefing
    
    def _format_calendar(self, events: list[dict]) -> str:
        """Format calendar events for prompt."""
        if not events:
            return ""
        
        lines = []
        for event in events:
            time_str = event.get("start", "TBD")
            summary = event.get("summary", "No title")
            attendees = event.get("attendees", [])
            attendee_str = f" (with {', '.join(attendees[:3])})" if attendees else ""
            lines.append(f"- {time_str}: {summary}{attendee_str}")
        
        return "\n".join(lines)
    
    def _format_emails(self, emails: list[dict]) -> str:
        """Format emails for prompt."""
        if not emails:
            return ""
        
        lines = []
        for email in emails:
            sender = email.get("from", "Unknown")
            subject = email.get("subject", "No subject")
            lines.append(f"- From: {sender}\n  Subject: {subject}")
        
        return "\n".join(lines)
    
    def _format_slack(self, messages: list[dict]) -> str:
        """Format Slack messages for prompt."""
        if not messages:
            return ""
        
        lines = []
        for msg in messages:
            channel = msg.get("channel", "Unknown")
            text = msg.get("text", "")[:200]  # Truncate long messages
            msg_type = "DM" if msg.get("is_dm") else "Mention"
            lines.append(f"- [{msg_type}] in #{channel}: {text}")
        
        return "\n".join(lines)
    
    def _format_notion(self, tasks: list[dict]) -> str:
        """Format Notion tasks for prompt."""
        if not tasks:
            return ""
        
        lines = []
        for task in tasks:
            title = task.get("title", "Untitled")
            lines.append(f"- [ ] {title}")
        
        return "\n".join(lines)
    
    def _format_stripe(self, metrics: dict) -> str:
        """Format Stripe metrics for prompt."""
        if not metrics:
            return ""
        
        mrr = metrics.get("mrr", 0)
        active = metrics.get("active_subscriptions", 0)
        new_today = metrics.get("new_subscriptions_today", 0)
        churned = metrics.get("churned_today", 0)
        
        return f"""MRR: ${mrr:,.2f}
Active Subscriptions: {active}
New Subscriptions Today: {new_today}
Churned Today: {churned}"""
