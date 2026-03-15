"""SQLAlchemy models for Hundtracker backend."""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    Text,
    DateTime,
    Float,
    Boolean,
    ForeignKey,
    Enum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
import enum


class SourceType(str, enum.Enum):
    """Position source: dog (ESP32) or hunter (app/web)."""

    DOG = "dog"
    HUNTER = "hunter"


class MemberRole(str, enum.Enum):
    """Hunt team member role."""

    OWNER = "owner"
    MEMBER = "member"


class HuntStatus(str, enum.Enum):
    """Hunt session status."""

    ACTIVE = "active"
    ENDED = "ended"


class User(Base):
    """Hunter user profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hunt_team_memberships: Mapped[list["HuntTeamMember"]] = relationship(
        "HuntTeamMember", back_populates="user"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="user"
    )
    device_tokens: Mapped[list["DeviceToken"]] = relationship(
        "DeviceToken", back_populates="user"
    )


class HuntTeam(Base):
    """Hunt team - one or more hunters."""

    __tablename__ = "hunt_teams"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    members: Mapped[list["HuntTeamMember"]] = relationship(
        "HuntTeamMember", back_populates="hunt_team"
    )
    dogs: Mapped[list["DogHuntTeam"]] = relationship(
        "DogHuntTeam", back_populates="hunt_team"
    )
    hunts: Mapped[list["Hunt"]] = relationship(
        "Hunt", back_populates="hunt_team"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="hunt_team"
    )


class HuntTeamMember(Base):
    """Hunter membership in hunt team (many-to-many)."""

    __tablename__ = "hunt_team_members"

    hunt_team_id: Mapped[int] = mapped_column(
        ForeignKey("hunt_teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[MemberRole] = mapped_column(
        String(20), default=MemberRole.MEMBER, nullable=False
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hunt_team: Mapped["HuntTeam"] = relationship(
        "HuntTeam", back_populates="members"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="hunt_team_memberships"
    )


class Dog(Base):
    """Dog with ESP32 tracker - identified by MQTT client_id."""

    __tablename__ = "dogs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hunt_teams: Mapped[list["DogHuntTeam"]] = relationship(
        "DogHuntTeam", back_populates="dog"
    )


class DogHuntTeam(Base):
    """Dog connected to hunt team (many-to-many)."""

    __tablename__ = "dog_hunt_teams"

    dog_id: Mapped[int] = mapped_column(
        ForeignKey("dogs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hunt_team_id: Mapped[int] = mapped_column(
        ForeignKey("hunt_teams.id", ondelete="CASCADE"),
        primary_key=True,
    )
    connected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    dog: Mapped["Dog"] = relationship("Dog", back_populates="hunt_teams")
    hunt_team: Mapped["HuntTeam"] = relationship(
        "HuntTeam", back_populates="dogs"
    )


class Hunt(Base):
    """Started hunt session - hunters join and share positions."""

    __tablename__ = "hunts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hunt_team_id: Mapped[int] = mapped_column(
        ForeignKey("hunt_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[HuntStatus] = mapped_column(
        String(20), default=HuntStatus.ACTIVE, nullable=False
    )

    hunt_team: Mapped["HuntTeam"] = relationship(
        "HuntTeam", back_populates="hunts"
    )
    participants: Mapped[list["HuntParticipant"]] = relationship(
        "HuntParticipant", back_populates="hunt"
    )


class HuntParticipant(Base):
    """Hunter who joined a specific hunt."""

    __tablename__ = "hunt_participants"

    hunt_id: Mapped[int] = mapped_column(
        ForeignKey("hunts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hunt: Mapped["Hunt"] = relationship(
        "Hunt", back_populates="participants"
    )


class Position(Base):
    """Position from dog or hunter."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_type: Mapped[SourceType] = mapped_column(String(20), nullable=False)
    source_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # dog client_id or str(user_id)
    hunt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("hunts.id", ondelete="SET NULL"),
        nullable=True,
    )
    lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alt: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fix: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_positions_source_time", "source_type", "source_id", "timestamp"),
        Index("ix_positions_hunt_time", "hunt_id", "timestamp"),
    )


class ChatMessage(Base):
    """Chat message in hunt team - persisted for offline retrieval."""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hunt_team_id: Mapped[int] = mapped_column(
        ForeignKey("hunt_teams.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    hunt_team: Mapped["HuntTeam"] = relationship(
        "HuntTeam", back_populates="chat_messages"
    )
    user: Mapped["User"] = relationship(
        "User", back_populates="chat_messages"
    )


class DeviceToken(Base):
    """Device token for push notifications (FCM, APNs)."""

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # android, ios, web
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship(
        "User", back_populates="device_tokens"
    )
