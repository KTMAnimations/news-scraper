"""Alert routes."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from backend.api.dependencies import CurrentUser, DBSession
from backend.storage.timescale.models import Alert

router = APIRouter()


class AlertCreate(BaseModel):
    """Create alert request."""

    name: str
    ticker: str | None = None
    event_types: list[str] | None = None
    min_alpha_score: float | None = None
    urgency_levels: list[str] | None = None
    direction: str | None = None
    delivery_method: str = "push"


class AlertUpdate(BaseModel):
    """Update alert request."""

    name: str | None = None
    ticker: str | None = None
    event_types: list[str] | None = None
    min_alpha_score: float | None = None
    urgency_levels: list[str] | None = None
    direction: str | None = None
    delivery_method: str | None = None
    is_active: bool | None = None


class AlertResponse(BaseModel):
    """Alert response."""

    id: str
    name: str
    ticker: str | None
    event_types: list[str] | None
    min_alpha_score: float | None
    urgency_levels: list[str] | None
    direction: str | None
    delivery_method: str
    is_active: bool
    created_at: datetime | None
    last_triggered_at: datetime | None


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    db: DBSession,
    current_user: CurrentUser,
):
    """List user's alert rules."""
    result = await db.execute(
        select(Alert).where(Alert.user_id == current_user.id)
    )
    alerts = result.scalars().all()

    return [
        AlertResponse(
            id=str(a.id),
            name=a.name,
            ticker=a.ticker,
            event_types=a.event_types,
            min_alpha_score=a.min_alpha_score,
            urgency_levels=a.urgency_levels,
            direction=a.direction,
            delivery_method=a.delivery_method,
            is_active=a.is_active,
            created_at=a.created_at,
            last_triggered_at=a.last_triggered_at,
        )
        for a in alerts
    ]


@router.post("", response_model=AlertResponse)
async def create_alert(
    data: AlertCreate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Create a new alert rule."""
    alert = Alert(
        user_id=current_user.id,
        name=data.name,
        ticker=data.ticker.upper() if data.ticker else None,
        event_types=data.event_types,
        min_alpha_score=data.min_alpha_score,
        urgency_levels=data.urgency_levels,
        direction=data.direction,
        delivery_method=data.delivery_method,
    )

    db.add(alert)
    await db.commit()
    await db.refresh(alert)

    return AlertResponse(
        id=str(alert.id),
        name=alert.name,
        ticker=alert.ticker,
        event_types=alert.event_types,
        min_alpha_score=alert.min_alpha_score,
        urgency_levels=alert.urgency_levels,
        direction=alert.direction,
        delivery_method=alert.delivery_method,
        is_active=alert.is_active,
        created_at=alert.created_at,
        last_triggered_at=alert.last_triggered_at,
    )


@router.put("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: UUID,
    data: AlertUpdate,
    db: DBSession,
    current_user: CurrentUser,
):
    """Update an alert rule."""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    # Update fields
    if data.name is not None:
        alert.name = data.name
    if data.ticker is not None:
        alert.ticker = data.ticker.upper() if data.ticker else None
    if data.event_types is not None:
        alert.event_types = data.event_types
    if data.min_alpha_score is not None:
        alert.min_alpha_score = data.min_alpha_score
    if data.urgency_levels is not None:
        alert.urgency_levels = data.urgency_levels
    if data.direction is not None:
        alert.direction = data.direction
    if data.delivery_method is not None:
        alert.delivery_method = data.delivery_method
    if data.is_active is not None:
        alert.is_active = data.is_active

    await db.commit()
    await db.refresh(alert)

    return AlertResponse(
        id=str(alert.id),
        name=alert.name,
        ticker=alert.ticker,
        event_types=alert.event_types,
        min_alpha_score=alert.min_alpha_score,
        urgency_levels=alert.urgency_levels,
        direction=alert.direction,
        delivery_method=alert.delivery_method,
        is_active=alert.is_active,
        created_at=alert.created_at,
        last_triggered_at=alert.last_triggered_at,
    )


@router.delete("/{alert_id}")
async def delete_alert(
    alert_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
):
    """Delete an alert rule."""
    result = await db.execute(
        select(Alert).where(
            Alert.id == alert_id,
            Alert.user_id == current_user.id,
        )
    )
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alert not found",
        )

    await db.delete(alert)
    await db.commit()

    return {"status": "deleted", "id": str(alert_id)}
