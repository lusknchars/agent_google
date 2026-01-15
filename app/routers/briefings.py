"""
Briefings router.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.briefing import Briefing
from app.models.user import User
from app.schemas.briefing import BriefingRead, BriefingSummary
from app.services.auth import get_current_user
from app.services.briefing import BriefingService

router = APIRouter(prefix="/briefings", tags=["Briefings"])


@router.get("", response_model=list[BriefingSummary])
async def list_briefings(
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Briefing]:
    """List user's briefings with pagination."""
    service = BriefingService(db)
    return await service.list_briefings(current_user.id, limit, offset)


@router.post("/generate", response_model=BriefingRead, status_code=status.HTTP_201_CREATED)
async def generate_briefing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Briefing:
    """Generate a new briefing."""
    service = BriefingService(db)
    
    try:
        briefing = await service.generate_briefing(current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate briefing: {str(e)}",
        )
    
    return briefing


@router.get("/latest", response_model=BriefingRead | None)
async def get_latest_briefing(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Briefing | None:
    """Get the latest briefing."""
    service = BriefingService(db)
    briefing = await service.get_latest_briefing(current_user.id)
    
    if briefing:
        # Mark as read
        await service.mark_as_read(briefing.id, current_user.id)
    
    return briefing


@router.get("/{briefing_id}", response_model=BriefingRead)
async def get_briefing(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Briefing:
    """Get a specific briefing by ID."""
    service = BriefingService(db)
    briefing = await service.get_briefing(briefing_id, current_user.id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    return briefing


@router.post("/{briefing_id}/read", response_model=BriefingRead)
async def mark_briefing_as_read(
    briefing_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Briefing:
    """Mark a briefing as read."""
    service = BriefingService(db)
    briefing = await service.mark_as_read(briefing_id, current_user.id)
    
    if not briefing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Briefing not found",
        )
    
    return briefing
