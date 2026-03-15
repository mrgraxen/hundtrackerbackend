"""Hunt team endpoints - create, join, list, dogs."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    Dog,
    DogHuntTeam,
    HuntTeam,
    HuntTeamMember,
    MemberRole,
    User,
)
from app.schemas import (
    DogConnect,
    DogResponse,
    HuntTeamCreate,
    HuntTeamDetailResponse,
    HuntTeamMemberResponse,
    HuntTeamResponse,
    HuntTeamSearchResult,
)

router = APIRouter(prefix="/hunt-teams", tags=["hunt-teams"])


async def _require_member(db: AsyncSession, hunt_team_id: int, user_id: int) -> HuntTeamMember:
    result = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == hunt_team_id,
            HuntTeamMember.user_id == user_id,
        )
    )
    m = result.scalar_one_or_none()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not a member of this hunt team",
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
    )
    db.add(member)
    await db.commit()
    await db.refresh(team)
    return team


@router.get("", response_model=list[HuntTeamResponse])
async def list_my_hunt_teams(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List hunt teams the current user is a member of."""
    result = await db.execute(
        select(HuntTeam)
        .join(HuntTeamMember)
        .where(HuntTeamMember.user_id == user.id)
    )
    return list(result.scalars().all())


@router.get("/search", response_model=list[HuntTeamSearchResult])
async def search_hunt_teams(
    q: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Search hunt teams by name. Returns all matching teams; is_member is true if current user is in the team."""
    if not q or not q.strip():
        return []
    term = f"%{q.strip()}%"
    result = await db.execute(
        select(HuntTeam).where(HuntTeam.name.ilike(term)).order_by(HuntTeam.name)
    )
    teams = result.scalars().all()
    # Which of these is the user a member of?
    my_team_ids = set()
    if teams:
        member_result = await db.execute(
            select(HuntTeamMember.hunt_team_id).where(
                HuntTeamMember.user_id == user.id,
                HuntTeamMember.hunt_team_id.in_(t.id for t in teams),
            )
        )
        my_team_ids = {r[0] for r in member_result.all()}
    return [
        HuntTeamSearchResult(
            id=t.id,
            name=t.name,
            created_by_user_id=t.created_by_user_id,
            created_at=t.created_at,
            is_member=t.id in my_team_ids,
        )
        for t in teams
    ]


@router.get("/{team_id}", response_model=HuntTeamDetailResponse)
async def get_hunt_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get hunt team details with members and dog count."""
    result = await db.execute(
        select(HuntTeam).where(HuntTeam.id == team_id)
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")
    await _require_member(db, team_id, user.id)

    result = await db.execute(
        select(HuntTeamMember, User.display_name)
        .join(User, User.id == HuntTeamMember.user_id)
        .where(HuntTeamMember.hunt_team_id == team_id)
    )
    members = [
        HuntTeamMemberResponse(
            user_id=m.user_id,
            display_name=dn or m.user.email,
            # m.role is now stored as a plain string in the DB
            role=getattr(m.role, "value", m.role),
            joined_at=m.joined_at,
        )
        for m, dn in result.all()
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
        created_by_user_id=team.created_by_user_id,
        created_at=team.created_at,
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
    """Remove a member from the hunt team. Only the team owner (admin) can remove members."""
    membership = await _require_member(db, team_id, user.id)
    if membership.role != MemberRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the team owner can remove members",
        )
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


@router.post("/{team_id}/join")
async def join_hunt_team(
    team_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join an existing hunt team (if open). Requires invite code in future."""
    result = await db.execute(select(HuntTeam).where(HuntTeam.id == team_id))
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="Hunt team not found")

    existing = await db.execute(
        select(HuntTeamMember).where(
            HuntTeamMember.hunt_team_id == team_id,
            HuntTeamMember.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Already a member"}

    member = HuntTeamMember(
        hunt_team_id=team_id,
        user_id=user.id,
        role=MemberRole.MEMBER,
    )
    db.add(member)
    await db.commit()
    return {"message": "Joined hunt team"}


@router.post("/{team_id}/dogs", response_model=DogResponse)
async def connect_dog(
    team_id: int,
    data: DogConnect,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Connect a dog (by MQTT client_id) to the hunt team."""
    await _require_member(db, team_id, user.id)

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
