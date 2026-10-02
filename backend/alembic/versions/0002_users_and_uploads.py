"""users, per-user ownership, uploaded data

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-02 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED = ("data_sources", "conversations", "query_runs")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_users_email"), ["email"], unique=True)

    for table in OWNED:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column("owner_id", sa.String(length=32), nullable=True))
            batch_op.create_index(batch_op.f(f"ix_{table}_owner_id"), ["owner_id"], unique=False)
            batch_op.create_foreign_key(f"fk_{table}_owner_id_users", "users", ["owner_id"], ["id"], ondelete="CASCADE")

    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.add_column(sa.Column("upload_data", sa.LargeBinary(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("data_sources", schema=None) as batch_op:
        batch_op.drop_column("upload_data")

    for table in reversed(OWNED):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_owner_id_users", type_="foreignkey")
            batch_op.drop_index(batch_op.f(f"ix_{table}_owner_id"))
            batch_op.drop_column("owner_id")

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_users_email"))
    op.drop_table("users")
