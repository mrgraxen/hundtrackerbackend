"""Notification endpoints - register device for push."""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select

from app.auth import get_current_user
from app.database import get_db
from app.models import DeviceToken, User
from app.schemas import DeviceTokenRegister
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/register")
async def register_device(
    data: DeviceTokenRegister,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register device token for push notifications (FCM, APNs, Web Push).
    Chat messages trigger notifications to team members - use this to enable them.
    """
    result = await db.execute(
        select(DeviceToken).where(
            DeviceToken.user_id == user.id,
            DeviceToken.token == data.token,
            DeviceToken.platform == data.platform,
        )
    )
    if result.scalar_one_or_none():
        return {"message": "Already registered"}

    token = DeviceToken(
        user_id=user.id,
        token=data.token,
        platform=data.platform,
    )
    db.add(token)
    await db.commit()
    return {"message": "Device registered for notifications"}
