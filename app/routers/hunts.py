"""Hunt session endpoints - start, join, positions."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Dog,
    DogHuntTeam,
    Hunt,
    HuntParticipant,
    HuntStatus,
    HuntTeam,
    HuntTeamMember,
    Position,
    SourceType,
    User,
)
from app.schemas import (
    HuntDetailResponse,
    HuntResponse,
    PositionReport,
    PositionResponse,
    UserResponse,
)

router = APIRouter(prefix="/hunts", tags=["hunts"])


async def _require_team_member(db: AsyncSession, team_id: int, user_id: int) -> None:
    result = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this hunt team",
        )


async def _require_participant(db: AsyncSession, hunt_id: int, user_id: int) -> None:
    result = await db.execute(
        select(HuntParticipant).where(
            HuntParticipant.hunt_id == hunt_id,
            HuntParticipant.user_id == user_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a participant in this hunt",
        )


@router.get("/teams/{team_id}", response_model=list[HuntResponse])
async def list_hunts(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List hunts for a hunt team."""
    await _require_team_member(db, team_id, user.id)
    result = await db.execute(
        select(Hunt).where(Hunt.hunt_team_id == team_id).order_by(Hunt.started_at.desc())
    )
    return list(result.scalars().all())


@router.post("/teams/{team_id}/start", response_model=HuntResponse)
async def start_hunt(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a hunt for the hunt team."""
    await _require_team_member(db, team_id, user.id)

    result = await db.execute(
        select(Hunt).where(
            Hunt.hunt_team_id == team_id,
            Hunt.status == HuntStatus.ACTIVE,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An active hunt already exists for this team",
        )

    hunt = Hunt(hunt_team_id=team_id, status=HuntStatus.ACTIVE)
    db.add(hunt)
    await db.commit()
    await db.refresh(hunt)
    return hunt


@router.post("/{hunt_id}/join")
async def join_hunt(
    hunt_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a hunt - start sharing position and see others on map."""
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    if hunt.status != HuntStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hunt is not active",
        )
    await _require_team_member(db, hunt.hunt_team_id, user.id)

    existing = await db.execute(
        select(HuntParticipant).where(
            HuntParticipant.hunt_id == hunt_id,
            HuntParticipant.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Already joined"}

    p = HuntParticipant(hunt_id=hunt_id, user_id=user.id)
    db.add(p)
    await db.commit()
    return {"message": "Joined hunt"}


@router.post("/{hunt_id}/end")
async def end_hunt(
    hunt_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """End an active hunt."""
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    await _require_team_member(db, hunt.hunt_team_id, user.id)
    if hunt.status != HuntStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hunt is not active",
        )
    hunt.status = HuntStatus.ENDED
    hunt.ended_at = datetime.utcnow()
    await db.commit()
    return {"message": "Hunt ended"}


@router.get("/{hunt_id}", response_model=HuntDetailResponse)
async def get_hunt(
    hunt_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get hunt details with participants."""
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    await _require_team_member(db, hunt.hunt_team_id, user.id)

    result = await db.execute(
        select(User).join(HuntParticipant).where(
            HuntParticipant.hunt_id == hunt_id,
            User.id == HuntParticipant.user_id,
        )
    )
    participants = [
        UserResponse(id=u.id, email=u.email, display_name=u.display_name, created_at=u.created_at)
        for u in result.scalars().all()
    ]

    return HuntDetailResponse(
        id=hunt.id,
        hunt_team_id=hunt.hunt_team_id,
        started_at=hunt.started_at,
        ended_at=hunt.ended_at,
        status=hunt.status.value,
        participants=participants,
    )


@router.post("/{hunt_id}/position")
async def report_position(
    hunt_id: int,
    data: PositionReport,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Hunter reports position (from app/web). Must be hunt participant."""
    await _require_participant(db, hunt_id, user.id)

    pos = Position(
        source_type=SourceType.HUNTER,
        source_id=str(user.id),
        hunt_id=hunt_id,
        lat=data.lat,
        lon=data.lon,
        alt=data.alt,
        speed=data.speed,
        accuracy=data.accuracy,
        fix=True,
        timestamp=datetime.utcnow(),
    )
    db.add(pos)
    await db.commit()

    # Broadcast to WebSocket clients
    try:
        from app.websocket_manager import manager
        await manager.broadcast_position(hunt_id, {
            "source_type": "hunter",
            "source_id": str(user.id),
            "lat": data.lat,
            "lon": data.lon,
            "alt": data.alt,
            "speed": data.speed,
            "accuracy": data.accuracy,
            "fix": True,
            "timestamp": pos.timestamp.isoformat(),
        })
    except Exception:
        pass

    return {"ok": True}


@router.get("/{hunt_id}/positions", response_model=list[PositionResponse])
async def get_positions(
    hunt_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    since_minutes: Optional[int] = Query(60, ge=1, le=1440),
):
    """Get positions for hunt - hunters + dogs. Last N minutes."""
    result = await db.execute(select(Hunt).where(Hunt.id == hunt_id))
    hunt = result.scalar_one_or_none()
    if not hunt:
        raise HTTPException(status_code=404, detail="Hunt not found")
    await _require_team_member(db, hunt.hunt_team_id, user.id)

    cutoff = datetime.utcnow() - timedelta(minutes=since_minutes)

    # Hunter positions (participants)
    hunter_ids = await db.execute(
        select(HuntParticipant.user_id).where(HuntParticipant.hunt_id == hunt_id)
    )
    hunter_id_set = {str(uid) for uid, in hunter_ids.all()}

    # Dog client_ids for this team
    dog_result = await db.execute(
        select(Dog.client_id).join(DogHuntTeam).where(
            DogHuntTeam.hunt_team_id == hunt.hunt_team_id
        )
    )
    dog_ids = {row[0] for row in dog_result.all()}

    # Latest position per source (within cutoff)
    result = await db.execute(
        select(Position)
        .where(Position.timestamp >= cutoff)
        .where(
            or_(
                and_(Position.source_type == SourceType.HUNTER, Position.source_id.in_(hunter_id_set)),
                and_(Position.source_type == SourceType.DOG, Position.source_id.in_(dog_ids)),
            )
        )
        .order_by(Position.timestamp.desc())
    )
    positions = result.scalars().all()

    # Deduplicate by source - keep latest
    seen = set()
    unique = []
    for p in positions:
        key = (p.source_type.value, p.source_id)
        if key not in seen:
            seen.add(key)
            unique.append(p)

    return [
        PositionResponse(
            source_type=p.source_type.value,
            source_id=p.source_id,
            lat=p.lat,
            lon=p.lon,
            alt=p.alt,
            speed=p.speed,
            accuracy=p.accuracy,
            fix=p.fix,
            timestamp=p.timestamp,
        )
        for p in unique
    ]
