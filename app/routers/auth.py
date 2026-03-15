"""Auth endpoints - register, login."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_token, hash_password, verify_password
from app.database import get_db
from app.models import User
from app.schemas import Token, UserLogin, UserRegister, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db),
):
    """Create hunter user profile."""
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        display_name=data.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Login - returns JWT for API auth."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return Token(access_token=create_token(user.id))
