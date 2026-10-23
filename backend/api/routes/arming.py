"""App routes for household arming (`/api/arming`, B4.7 / docs/uplevel/4n-arming.md)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas.arming import (
    ArmingChangeItemResponse,
    ArmingChangesListResponse,
    ArmingEventDecisionResponse,
    ArmingModeCamerasResponse,
    ArmingModeCamerasUpdateRequest,
    ArmingScheduleEntrySchema,
    ArmingScheduleResponse,
    ArmingScheduleUpdateRequest,
    ArmingSetModeRequest,
    ArmingStatusResponse,
)
from backend.core.database import get_db
from backend.models.event_notify import EventNotifyDecision
from backend.services.arming import (
    get_arming_status,
    get_mode_exclusions,
    get_schedule,
    list_changes,
    set_mode,
    set_mode_exclusions,
    set_schedule,
)

router = APIRouter(prefix="/api/arming", tags=["arming"])


def _user_source_name(request: Request | None) -> str:
    if request is None:
        return "user"
    state_user = getattr(getattr(request, "state", None), "user", None)
    if state_user is not None:
        uname = getattr(state_user, "username", None)
        if uname:
            return str(uname)
    return "user"


@router.get("", response_model=ArmingStatusResponse)
async def read_arming_status(
    db: AsyncSession = Depends(get_db),
) -> ArmingStatusResponse:
    """Return current household arming mode, source, timestamp, and next scheduled transition."""
    data = await get_arming_status(db)
    await db.commit()
    return ArmingStatusResponse(**data)


@router.put("/mode", response_model=ArmingStatusResponse)
async def update_arming_mode(
    payload: ArmingSetModeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ArmingStatusResponse:
    """Switch the household arming mode from the app."""
    user_name = _user_source_name(request)
    try:
        await set_mode(
            db,
            payload.mode,
            source_kind="user",
            source_name=user_name,
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    data = await get_arming_status(db)
    await db.commit()
    return ArmingStatusResponse(**data)


@router.get("/modes/{mode}/cameras", response_model=ArmingModeCamerasResponse)
async def read_mode_cameras(
    mode: str,
    db: AsyncSession = Depends(get_db),
) -> ArmingModeCamerasResponse:
    """Return the excluded camera IDs for `mode`."""
    try:
        excluded = await get_mode_exclusions(db, mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ArmingModeCamerasResponse(mode=mode.strip().lower(), excluded_camera_ids=excluded)


@router.put("/modes/{mode}/cameras", response_model=ArmingModeCamerasResponse)
async def update_mode_cameras(
    mode: str,
    payload: ArmingModeCamerasUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> ArmingModeCamerasResponse:
    """Replace the excluded camera IDs for `mode` (`home`, `away`, or `night`)."""
    user_name = _user_source_name(request)
    try:
        await set_mode_exclusions(
            db,
            mode,
            payload.excluded_camera_ids,
            source_kind="user",
            source_name=user_name,
        )
        await db.commit()
        excluded = await get_mode_exclusions(db, mode)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ArmingModeCamerasResponse(mode=mode.strip().lower(), excluded_camera_ids=excluded)


@router.get("/schedule", response_model=ArmingScheduleResponse)
async def read_arming_schedule(
    db: AsyncSession = Depends(get_db),
) -> ArmingScheduleResponse:
    """Return the weekly arming schedule."""
    rows = await get_schedule(db)
    return ArmingScheduleResponse(
        items=[
            ArmingScheduleEntrySchema(id=r.id, days=list(r.days), time=r.time, mode=r.mode)
            for r in rows
        ]
    )


@router.put("/schedule", response_model=ArmingScheduleResponse)
async def update_arming_schedule(
    payload: ArmingScheduleUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> ArmingScheduleResponse:
    """Replace the weekly arming schedule and wake the in-process scheduler."""
    try:
        rows = await set_schedule(
            db,
            [item.model_dump() for item in payload.items],
        )
        await db.commit()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return ArmingScheduleResponse(
        items=[
            ArmingScheduleEntrySchema(id=r.id, days=list(r.days), time=r.time, mode=r.mode)
            for r in rows
        ]
    )


@router.get("/changes", response_model=ArmingChangesListResponse)
async def read_arming_changes(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> ArmingChangesListResponse:
    """Return recent arming mode and camera exclusion changes."""
    rows = await list_changes(db, limit=limit)
    return ArmingChangesListResponse(
        items=[
            ArmingChangeItemResponse(
                id=r.id,
                kind=r.kind,
                from_value=r.from_value,
                to_value=r.to_value,
                mode_after=r.mode_after,
                exclusions_after=dict(r.exclusions_after or {}),
                source_kind=r.source_kind,
                source_name=r.source_name,
                changed_at=r.changed_at,
            )
            for r in rows
        ]
    )


@router.get("/events/{event_id}/decision", response_model=ArmingEventDecisionResponse)
async def read_event_notify_decision(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> ArmingEventDecisionResponse:
    """Return the persisted notify decision (`notify` and `decided_by`) for `event_id`."""
    row = (
        (
            await db.execute(
                select(EventNotifyDecision).where(EventNotifyDecision.event_id == event_id)
            )
        )
        .scalars()
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    return ArmingEventDecisionResponse(
        event_id=row.event_id,
        notify=bool(row.notify),
        decided_by=str(row.decided_by),
    )
