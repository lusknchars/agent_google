"""
Briefing-related Pydantic schemas.
"""
from datetime import datetime
from pydantic import BaseModel


class BriefingBase(BaseModel):
    """Base briefing schema."""
    summary: str
    priorities: list[str]
    alerts: list[str]


class BriefingCreate(BriefingBase):
    """Schema for creating a briefing (internal use)."""
    content: dict
    raw_data: dict


class BriefingRead(BriefingBase):
    """Schema for reading full briefing data."""
    id: str
    content: dict
    raw_data: dict
    generated_at: datetime
    read_at: datetime | None
    
    class Config:
        from_attributes = True


class BriefingSummary(BaseModel):
    """Schema for briefing list items."""
    id: str
    summary: str
    priorities: list[str]
    generated_at: datetime
    read_at: datetime | None
    
    class Config:
        from_attributes = True


class GenerateBriefingRequest(BaseModel):
    """Request to generate a new briefing."""
    pass  # No parameters needed, uses current user


class AggregatedData(BaseModel):
    """Aggregated data from all integrations."""
    calendar_events: list[dict] = []
    emails: list[dict] = []
    slack_messages: list[dict] = []
    notion_tasks: list[dict] = []
    stripe_metrics: dict = {}
