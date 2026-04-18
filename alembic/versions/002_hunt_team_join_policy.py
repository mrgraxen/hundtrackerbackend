"""Hunt team join policy and membership status.

Revision ID: 002
Revises: 001
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hunt_teams",
        sa.Column(
            "join_policy",
            sa.String(length=20),
            nullable=False,
            server_default="open",
        ),
    )
    op.add_column(
        "hunt_team_members",
        sa.Column(
            "membership_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )
    op.alter_column("hunt_teams", "join_policy", server_default=None)
    op.alter_column("hunt_team_members", "membership_status", server_default=None)


def downgrade() -> None:
    op.drop_column("hunt_team_members", "membership_status")
    op.drop_column("hunt_teams", "join_policy")
