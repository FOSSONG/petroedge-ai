"""add persistent background jobs

Revision ID: 0003_background_jobs
Revises: 0002_unified_orm_schema
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_background_jobs"
down_revision: Union[str, None] = "0002_unified_orm_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_name", sa.String(length=150), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("requested_by", sa.String(length=36), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], name="fk_background_jobs_requested_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_background_jobs"),
    )
    op.create_index("ix_background_jobs_requested_by", "background_jobs", ["requested_by"], unique=False)
    op.create_index("ix_background_jobs_status_priority_created", "background_jobs", ["status", "priority", "created_at"], unique=False)
    op.create_index("ix_background_jobs_task_created", "background_jobs", ["task_name", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_background_jobs_task_created", table_name="background_jobs")
    op.drop_index("ix_background_jobs_status_priority_created", table_name="background_jobs")
    op.drop_index("ix_background_jobs_requested_by", table_name="background_jobs")
    op.drop_table("background_jobs")
