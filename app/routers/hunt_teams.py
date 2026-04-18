"""Hunt team endpoints - create, join, list, dogs."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.membership import get_membership, require_active_member
from app.models import (
    Dog,
    DogHuntTeam,
    HuntTeam,
    HuntTeamMember,
    JoinPolicy,
    MemberRole,
    MembershipStatus,
    User,
)
from app.schemas import (
    DogConnect,
    DogResponse,
    HuntTeamCreate,
    HuntTeamDetailResponse,
    HuntTeamListItem,
    HuntTeamMemberResponse,
    HuntTeamResponse,
    HuntTeamSearchResult,
    HuntTeamSettingsResponse,
    HuntTeamSettingsUpdate,
    JoinHuntTeamResponse,
    PendingMemberResponse,
)

router = APIRouter(prefix="/hunt-teams", tags=["hunt-teams"])


def _policy_value(team: HuntTeam) -> str:
    p = team.join_policy
    return getattr(p, "value", p)


def _status_value(m: HuntTeamMember) -> str:
    s = m.membership_status
    return getattr(s, "value", s)


async def _require_owner(db: AsyncSession, team_id: int, user_id: int) -> HuntTeamMember:
    m = await require_active_member(db, team_id, user_id)
    if m.role != MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can perform this action",
        )
    return m


@router.post("", response_model=HuntTeamResponse)
async def create_hunt_team(
    data: HuntTeamCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a hunt team. Creator becomes owner."""
    team = HuntTeam(name=data.name, created_by_user_id=user.id)
    db.add(team)
    await db.flush()
    member = HuntTeamMember(
        hunt_team_id=team.id,
        user_id=user.id,
        role=MemberRole.OWNER,
        membership_status=MembershipStatus.ACTIVE,
    )
    db.add(member)
    await db.commit()
    await db.refresh(team)
    return team


@router.get("", response_model=list[HuntTeamListItem])
async def list_my_hunt_teams(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List hunt teams the current user has a membership row for (active or pending)."""
    result = await db.execute(
        select(HuntTeam, HuntTeamMember.membership_status)
        .join(HuntTeamMember, HuntTeamMember.hunt_team_id == HuntTeam.id)
        .where(HuntTeamMember.user_id == user.id)
    )
    rows = result.all()
    items: list[HuntTeamListItem] = []
    for team, ms in rows:
        st = getattr(ms, "value", ms)
        if st == MembershipStatus.PENDING.value:
            items.append(
                HuntTeamListItem(
                    id=team.id,
                    name=team.name,
                    membership_status=MembershipStatus.PENDING.value,
                )
            )
        else:
            items.append(
                HuntTeamListItem(
                    id=team.id,
                    name=team.name,
                    membership_status=MembershipStatus.ACTIVE.value,
                    created_by_user_id=team.created_by_user_id,
                    created_at=team.created_at,
                    join_policy=_policy_value(team),
                )
            )
    return items


@router.get("/search", response_model=list[HuntTeamSearchResult])
async def search_hunt_teams(
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search hunt teams by name."""
    if not q or not q.strip():
        return []
    term = f"%{q.strip()}%"
    result = await db.execute(
        select(HuntTeam).where(HuntTeam.name.ilike(term)).order_by(HuntTeam.name)
    )
    teams = result.scalars().all()
    status_by_team: dict[int, str] = {}
    if teams:
        member_result = await db.execute(
            select(HuntTeamMember.hunt_team_id, HuntTeamMember.membership_status).where(
                HuntTeamMember.user_id == user.id,
                HuntTeamMember.hunt_team_id.in_(t.id for t in teams),
            )
        )
        for tid, ms in member_result.all():
            status_by_team[tid] = getattr(ms, "value", ms)
    out: list[HuntTeamSearchResult] = []
    for t in teams:
        st = status_by_team.get(t.id)
        is_member = st == MembershipStatus.ACTIVE.value
        membership_pending = st == MembershipStatus.PENDING.value
        if membership_pending:
            out.append(
                HuntTeamSearchResult(
                    id=t.id,
                    name=t.name,
                    is_member=False,
                    membership_pending=True,
                )
            )
        else:
            out.append(
                HuntTeamSearchResult(
                    id=t.id,
                    name=t.name,
                    created_by_user_id=t.created_by_user_id,
                    created_at=t.created_at,
                    is_member=is_member,
                    membership_pending=False,
                )
            )
    return out


@router.get("/{team_id}/settings", response_model=HuntTeamSettingsResponse)
async def get_hunt_team_settings(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Current join policy (active members only)."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")
    await require_active_member(db, team_id, user.id)
    return HuntTeamSettingsResponse(join_policy=_policy_value(team))


@router.patch("/{team_id}/settings", response_model=HuntTeamSettingsResponse)
async def update_hunt_team_settings(
    team_id: int,
    data: HuntTeamSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update join policy (team owner only)."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")
    await _require_owner(db, team_id, user.id)
    team.join_policy = JoinPolicy(data.join_policy)
    await db.commit()
    await db.refresh(team)
    return HuntTeamSettingsResponse(join_policy=_policy_value(team))


@router.get("/{team_id}/pending-members", response_model=list[PendingMemberResponse])
async def list_pending_members(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Users waiting for approval (team owner only)."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Hunt team not found")
    await _require_owner(db, team_id, user.id)

    q = await db.execute(
        select(HuntTeamMember, User.display_name, User.email)
        .join(User, User.id == HuntTeamMember.user_id)
        .where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.membership_status == MembershipStatus.PENDING,
        )
        .order_by(HuntTeamMember.joined_at)
    )
    return [
        PendingMemberResponse(
            user_id=m.user_id,
            display_name=dn or email,
            requested_at=m.joined_at,
        )
        for m, dn, email in q.all()
    ]


@router.post("/{team_id}/members/{member_user_id}/approve")
async def approve_pending_member(
    team_id: int,
    member_user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending membership (team owner only)."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Hunt team not found")
    await _require_owner(db, team_id, user.id)

    target = await get_membership(db, team_id, member_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Member not found")
    if _status_value(target) != MembershipStatus.PENDING.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not pending approval",
        )
    target.membership_status = MembershipStatus.ACTIVE
    await db.commit()
    return {"message": "Membership approved"}


@router.get("/{team_id}", response_model=HuntTeamDetailResponse)
async def get_hunt_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get hunt team details. Pending members only receive id and name."""
    result = await db.execute(
        select(HuntTeam).where(HuntTeam.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")

    membership = await get_membership(db, team_id, user.id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this hunt team",
        )

    if _status_value(membership) == MembershipStatus.PENDING.value:
        return HuntTeamDetailResponse(
            id=team.id,
            name=team.name,
            membership_status=MembershipStatus.PENDING.value,
        )

    result = await db.execute(
        select(HuntTeamMember, User.display_name, User.email)
        .join(User, User.id == HuntTeamMember.user_id)
        .where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.membership_status == MembershipStatus.ACTIVE,
        )
        .order_by(HuntTeamMember.joined_at)
    )
    members = [
        HuntTeamMemberResponse(
            user_id=m.user_id,
            display_name=dn or email,
            role=getattr(m.role, "value", m.role),
            joined_at=m.joined_at,
            membership_status=_status_value(m),
        )
        for m, dn, email in result.all()
    ]

    dog_count_result = await db.execute(
        select(func.count()).select_from(DogHuntTeam).where(
            DogHuntTeam.hunt_team_id == team_id
        )
    )
    dog_count = dog_count_result.scalar() or 0

    return HuntTeamDetailResponse(
        id=team.id,
        name=team.name,
        membership_status=MembershipStatus.ACTIVE.value,
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
        join_policy=_policy_value(team),
        members=members,
        dog_count=dog_count,
    )


@router.delete("/{team_id}/members/{user_id}")
async def remove_member(
    team_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a member or reject a pending request. Only the team owner."""
    await _require_owner(db, team_id, user.id)
    target = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.user_id == user_id,
        )
    )
    target_member = target.scalar_one_or_none()
    if not target_member:
        raise HTTPException(status_code=404, detail="Member not found")
    if target_member.role == MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the team owner",
        )
    await db.delete(target_member)
    await db.commit()
    return {"message": "Member removed"}


@router.post("/{team_id}/join", response_model=JoinHuntTeamResponse)
async def join_hunt_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a hunt team: immediate member if open, otherwise pending until owner approves."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")

    existing = await get_membership(db, team_id, user.id)
    if existing:
        st = _status_value(existing)
        if st == MembershipStatus.PENDING.value:
            return JoinHuntTeamResponse(
                message="Membership request pending",
                membership_status=MembershipStatus.PENDING.value,
            )
        return JoinHuntTeamResponse(
            message="Already a member",
            membership_status=MembershipStatus.ACTIVE.value,
        )

    policy = _policy_value(team)
    if policy == JoinPolicy.APPROVAL_REQUIRED.value:
        member = HuntTeamMember(
            hunt_team_id=team_id,
            user_id=user.id,
            role=MemberRole.MEMBER,
            membership_status=MembershipStatus.PENDING,
        )
        db.add(member)
        await db.commit()
        return JoinHuntTeamResponse(
            message="Request sent; waiting for team owner approval",
            membership_status=MembershipStatus.PENDING.value,
        )

    member = HuntTeamMember(
        hunt_team_id=team_id,
        user_id=user.id,
        role=MemberRole.MEMBER,
        membership_status=MembershipStatus.ACTIVE,
    )
    db.add(member)
    await db.commit()
    return JoinHuntTeamResponse(
        message="Joined hunt team",
        membership_status=MembershipStatus.ACTIVE.value,
    )


@router.post("/{team_id}/dogs", response_model=DogResponse)
async def connect_dog(
    team_id: int,
    data: DogConnect,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a dog (by MQTT client_id) to the hunt team."""
    await require_active_member(db, team_id, user.id)

    result = await db.execute(select(Dog).where(Dog.client_id == data.client_id))
    dog = result.scalar_one_or_none()
    if not dog:
        dog = Dog(client_id=data.client_id)
        db.add(dog)
        await db.flush()

    existing = await db.execute(
        select(DogHuntTeam).where(
            DogHuntTeam.dog_id == dog.id,
            DogHuntTeam.hunt_team_id == team_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dog already connected to this team",
        )

    link = DogHuntTeam(dog_id=dog.id, hunt_team_id=team_id)
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return DogResponse(
        id=dog.id,
        client_id=dog.client_id,
        name=dog.name,
        connected_at=link.connected_at,
    )
