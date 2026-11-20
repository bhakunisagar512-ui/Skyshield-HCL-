"""measure follow-up after closing

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("measures", sa.Column("completion_note", sa.Text(), nullable=True))
    op.add_column("measures", sa.Column("completed_by_id", sa.Integer(), nullable=True))
    op.add_column("measures", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_measures_completed_by", "measures", "users", ["completed_by_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_measures_completed_by", "measures", type_="foreignkey")
    op.drop_column("measures", "completed_at")
    op.drop_column("measures", "completed_by_id")
    op.drop_column("measures", "completion_note")
