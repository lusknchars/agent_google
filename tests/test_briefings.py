"""
Tests for briefings endpoints.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import Briefing


@pytest.mark.asyncio
async def test_list_briefings_empty(client: AsyncClient, auth_headers):
    """Test listing briefings when none exist."""
    response = await client.get(
        "/api/v1/briefings",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_get_latest_briefing_none(client: AsyncClient, auth_headers):
    """Test getting latest briefing when none exist."""
    response = await client.get(
        "/api/v1/briefings/latest",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    assert response.json() is None


@pytest.mark.asyncio
async def test_list_briefings_with_data(client: AsyncClient, auth_headers, db: AsyncSession, test_user):
    """Test listing briefings with existing data."""
    # Create a briefing
    briefing = Briefing(
        user_id=test_user.id,
        content={"test": "content"},
        summary="Test summary",
        priorities=["Priority 1", "Priority 2"],
        alerts=[],
        raw_data={},
    )
    db.add(briefing)
    await db.commit()
    
    response = await client.get(
        "/api/v1/briefings",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["summary"] == "Test summary"


@pytest.mark.asyncio
async def test_get_briefing_by_id(client: AsyncClient, auth_headers, db: AsyncSession, test_user):
    """Test getting a specific briefing by ID."""
    # Create a briefing
    briefing = Briefing(
        user_id=test_user.id,
        content={"test": "content"},
        summary="Test summary",
        priorities=["Priority 1"],
        alerts=["Alert 1"],
        raw_data={},
    )
    db.add(briefing)
    await db.commit()
    await db.refresh(briefing)
    
    response = await client.get(
        f"/api/v1/briefings/{briefing.id}",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == briefing.id
    assert data["summary"] == "Test summary"
    assert data["priorities"] == ["Priority 1"]
    assert data["alerts"] == ["Alert 1"]


@pytest.mark.asyncio
async def test_get_briefing_not_found(client: AsyncClient, auth_headers):
    """Test getting non-existent briefing returns 404."""
    response = await client.get(
        "/api/v1/briefings/nonexistent-id",
        headers=auth_headers,
    )
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_briefing_as_read(client: AsyncClient, auth_headers, db: AsyncSession, test_user):
    """Test marking a briefing as read."""
    # Create a briefing
    briefing = Briefing(
        user_id=test_user.id,
        content={},
        summary="Test",
        priorities=[],
        alerts=[],
        raw_data={},
    )
    db.add(briefing)
    await db.commit()
    await db.refresh(briefing)
    
    assert briefing.read_at is None
    
    response = await client.post(
        f"/api/v1/briefings/{briefing.id}/read",
        headers=auth_headers,
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["read_at"] is not None
