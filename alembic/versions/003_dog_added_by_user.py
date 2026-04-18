"""Dog registered-by user for name edits.

Revision ID: 003
Revises: 002
Create Date: 2026-04-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "dogs",
        sa.Column("added_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_dogs_added_by_user_id_users",
        "dogs",
        "users",
        ["added_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_dogs_added_by_user_id_users", "dogs", type_="foreignkey")
    op.drop_column("dogs", "added_by_user_id")
