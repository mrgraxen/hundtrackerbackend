"""Shared hunt team membership checks."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HuntTeamMember, MembershipStatus


def _membership_status_value(m: HuntTeamMember) -> str:
    s = m.membership_status
    return getattr(s, "value", s)


async def get_membership(
    db: AsyncSession, hunt_team_id: int, user_id: int
) -> HuntTeamMember | None:
    result = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == hunt_team_id,
            HuntTeamMember.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def require_active_member(
    db: AsyncSession, hunt_team_id: int, user_id: int
) -> HuntTeamMember:
    m = await get_membership(db, hunt_team_id, user_id)
    if not m or _membership_status_value(m) != MembershipStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this hunt team",
        )
    return m


async def require_active_member_ws(
    db: AsyncSession, hunt_team_id: int, user_id: int
) -> bool:
    """Return True if user is an active member; False otherwise (no exception)."""
    m = await get_membership(db, hunt_team_id, user_id)
    return bool(m and _membership_status_value(m) == MembershipStatus.ACTIVE.value)
