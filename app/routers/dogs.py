"""Dog endpoints — update display name (registered owner only)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import Dog, User
from app.schemas import DogResponse, DogUpdate

router = APIRouter(prefix="/dogs", tags=["dogs"])


@router.patch("/{dog_id}", response_model=DogResponse)
async def update_dog(
    dog_id: int,
    data: DogUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set or clear display name. Only the user who registered the dog (via connect) may edit."""
    result = await db.execute(select(Dog).where(Dog.id == dog_id))
    dog = result.scalar_one_or_none()
    if not dog:
        raise HTTPException(status_code=404, detail="Dog not found")
    if dog.added_by_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dog has no registered owner; connect it via POST /hunt-teams/{team_id}/dogs first",
        )
    if dog.added_by_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the user who registered this dog can edit its name",
        )

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    if "name" in updates:
        raw = updates["name"]
        if raw is None:
            dog.name = None
        else:
            s = raw.strip()
            dog.name = s if s else None

    await db.commit()
    await db.refresh(dog)
    return DogResponse(
        id=dog.id,
        client_id=dog.client_id,
        name=dog.name,
        connected_at=None,
    )
