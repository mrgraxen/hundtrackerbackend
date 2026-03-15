"""Initial schema - users, hunt teams, dogs, hunts, positions, chat.

Revision ID: 001
Revises:
Create Date: 2025-03-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "hunt_teams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dogs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_dogs_client_id"), "dogs", ["client_id"], unique=True)

    op.create_table(
        "hunt_team_members",
        sa.Column("hunt_team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hunt_team_id"], ["hunt_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("hunt_team_id", "user_id"),
    )

    op.create_table(
        "dog_hunt_teams",
        sa.Column("dog_id", sa.Integer(), nullable=False),
        sa.Column("hunt_team_id", sa.Integer(), nullable=False),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["dog_id"], ["dogs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hunt_team_id"], ["hunt_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("dog_id", "hunt_team_id"),
    )

    op.create_table(
        "hunts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hunt_team_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.ForeignKeyConstraint(["hunt_team_id"], ["hunt_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hunt_participants",
        sa.Column("hunt_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hunt_id"], ["hunts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("hunt_id", "user_id"),
    )

    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("hunt_id", sa.Integer(), nullable=True),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lon", sa.Float(), nullable=True),
        sa.Column("alt", sa.Float(), nullable=True),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("fix", sa.Boolean(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hunt_id"], ["hunts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_positions_source_time", "positions", ["source_type", "source_id", "timestamp"]
    )
    op.create_index("ix_positions_hunt_time", "positions", ["hunt_id", "timestamp"])

    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hunt_team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hunt_team_id"], ["hunt_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "device_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sa.String(512), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("device_tokens")
    op.drop_table("chat_messages")
    op.drop_table("positions")
    op.drop_table("hunt_participants")
    op.drop_table("hunts")
    op.drop_table("dog_hunt_teams")
    op.drop_table("hunt_team_members")
    op.drop_table("dogs")
    op.drop_table("hunt_teams")
    op.drop_table("users")
