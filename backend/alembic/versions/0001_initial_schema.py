"""Create the initial PetroEdge AI relational schema.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-07-19

This migration is deliberately bootstrap-safe. If a PetroEdge development
SQLite database was previously created with SQLAlchemy ``create_all()``, the
migration preserves existing tables and creates only missing tables or indexes.
Alembic will then record this revision in ``alembic_version``.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    indexes = inspect(op.get_bind()).get_indexes(table_name)
    return any(item.get("name") == index_name for item in indexes)


def upgrade() -> None:
    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("email", sa.String(), nullable=False),
            sa.Column("full_name", sa.String(), nullable=False),
            sa.Column("hashed_password", sa.String(), nullable=False),
            sa.Column("role", sa.String(), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_users"),
            sa.UniqueConstraint("email", name="uq_users_email"),
        )
    if not _index_exists("users", "ix_users_email"):
        op.create_index("ix_users_email", "users", ["email"], unique=True)

    if not _table_exists("wells"):
        op.create_table(
            "wells",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("well_id", sa.String(), nullable=False),
            sa.Column("field_name", sa.String(), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=True),
            sa.Column("longitude", sa.Float(), nullable=True),
            sa.Column("total_depth_m", sa.Float(), nullable=True),
            sa.PrimaryKeyConstraint("id", name="pk_wells"),
            sa.UniqueConstraint("well_id", name="uq_wells_well_id"),
        )
    if not _index_exists("wells", "ix_wells_well_id"):
        op.create_index("ix_wells_well_id", "wells", ["well_id"], unique=True)

    if not _table_exists("log_samples"):
        op.create_table(
            "log_samples",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("well_id", sa.String(), nullable=False),
            sa.Column("depth_m", sa.Float(), nullable=False),
            sa.Column("gamma_ray_api", sa.Float(), nullable=True),
            sa.Column("resistivity_ohmm", sa.Float(), nullable=True),
            sa.Column("density_gcc", sa.Float(), nullable=True),
            sa.Column("neutron_porosity_vv", sa.Float(), nullable=True),
            sa.Column("sonic_usft", sa.Float(), nullable=True),
            sa.Column("caliper_in", sa.Float(), nullable=True),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.ForeignKeyConstraint(
                ["well_id"],
                ["wells.well_id"],
                name="fk_log_samples_well_id_wells",
            ),
            sa.PrimaryKeyConstraint("id", name="pk_log_samples"),
        )

    if not _table_exists("analytics_results"):
        op.create_table(
            "analytics_results",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("well_id", sa.String(), nullable=False),
            sa.Column("depth_m", sa.Float(), nullable=False),
            sa.Column("qc_score", sa.Float(), nullable=False),
            sa.Column("hydrocarbon_probability", sa.Float(), nullable=False),
            sa.Column("lithology", sa.String(), nullable=False),
            sa.Column("facies", sa.String(), nullable=False),
            sa.Column("anomaly_score", sa.Float(), nullable=False),
            sa.Column("porosity", sa.Float(), nullable=False),
            sa.Column("water_saturation", sa.Float(), nullable=False),
            sa.Column("shale_volume", sa.Float(), nullable=False),
            sa.Column("net_to_gross", sa.Float(), nullable=False),
            sa.Column("permeability_md", sa.Float(), nullable=False),
            sa.Column("explanation", sa.JSON(), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_analytics_results"),
        )

    if not _table_exists("alerts"):
        op.create_table(
            "alerts",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("well_id", sa.String(), nullable=False),
            sa.Column("severity", sa.String(), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("acknowledged", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id", name="pk_alerts"),
        )


def downgrade() -> None:
    # Reverse dependency order. Existing application data will be deleted.
    for table_name in (
        "alerts",
        "analytics_results",
        "log_samples",
        "wells",
        "users",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)
