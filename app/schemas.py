"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, constr, Field


# ----- Auth -----
class UserRegister(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=72)
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: constr(min_length=8, max_length=72)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    display_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ----- Hunt Team -----
class HuntTeamCreate(BaseModel):
    name: str


class HuntTeamResponse(BaseModel):
    id: int
    name: str
    created_by_user_id: int
    created_at: datetime
    join_policy: str

    class Config:
        from_attributes = True


class HuntTeamListItem(BaseModel):
    """My teams: full row for active members; pending users only get id, name, status."""

    id: int
    name: str
    membership_status: str
    created_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    join_policy: Optional[str] = None


class HuntTeamSearchResult(BaseModel):
    """Team search hit with membership flag.

    For pending membership, only id/name are set (no other team metadata).
    """

    id: int
    name: str
    created_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    is_member: bool
    membership_pending: bool = False

    class Config:
        from_attributes = True


class HuntTeamMemberResponse(BaseModel):
    user_id: int
    display_name: Optional[str] = None
    role: str
    joined_at: datetime
    membership_status: str


class HuntTeamDetailResponse(BaseModel):
    id: int
    name: str
    membership_status: str
    created_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None
    join_policy: Optional[str] = None
    members: list[HuntTeamMemberResponse] = Field(default_factory=list)
    dog_count: Optional[int] = None


class HuntTeamSettingsResponse(BaseModel):
    join_policy: str


class HuntTeamSettingsUpdate(BaseModel):
    join_policy: Literal["open", "approval_required"]


class PendingMemberResponse(BaseModel):
    user_id: int
    display_name: Optional[str] = None
    requested_at: datetime


class JoinHuntTeamResponse(BaseModel):
    message: str
    membership_status: str


# ----- Dog -----
class DogConnect(BaseModel):
    client_id: str


class DogResponse(BaseModel):
    id: int
    client_id: str
    name: Optional[str] = None
    connected_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ----- Hunt -----
class HuntStart(BaseModel):
    pass  # No body needed


class HuntResponse(BaseModel):
    id: int
    hunt_team_id: int
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str

    class Config:
        from_attributes = True


class HuntDetailResponse(HuntResponse):
    participants: list[UserResponse]


# ----- Position -----
class PositionReport(BaseModel):
    lat: float
    lon: float
    alt: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None


class PositionResponse(BaseModel):
    source_type: str
    source_id: str
    lat: Optional[float] = None
    lon: Optional[float] = None
    alt: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    fix: Optional[bool] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ----- Chat -----
class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    id: int
    hunt_team_id: int
    user_id: int
    display_name: Optional[str] = None
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ----- Notification -----
class DeviceTokenRegister(BaseModel):
    token: str
    platform: str  # android, ios, web
