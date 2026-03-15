"""Pydantic schemas for API request/response."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, constr


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

    class Config:
        from_attributes = True


class HuntTeamSearchResult(BaseModel):
    """Team search hit with membership flag."""
    id: int
    name: str
    created_by_user_id: int
    created_at: datetime
    is_member: bool

    class Config:
        from_attributes = True


class HuntTeamMemberResponse(BaseModel):
    user_id: int
    display_name: Optional[str] = None
    role: str
    joined_at: datetime


class HuntTeamDetailResponse(HuntTeamResponse):
    members: list[HuntTeamMemberResponse]
    dog_count: int


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
