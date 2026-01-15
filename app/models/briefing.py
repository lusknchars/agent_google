"""
Briefing model for generated daily briefings.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class Briefing(Base):
    """Daily briefing model."""
    
    __tablename__ = "briefings"
    
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )  # Full structured briefing data
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )  # Natural language summary
    priorities: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )  # Top 3 priorities
    alerts: Mapped[list] = mapped_column(
        JSON,
        default=list,
    )  # Urgent alerts
    raw_data: Mapped[dict] = mapped_column(
        JSON,
        default=dict,
    )  # Aggregated source data
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="briefings",
    )
    
    def __repr__(self) -> str:
        return f"<Briefing {self.id} for user {self.user_id}>"
