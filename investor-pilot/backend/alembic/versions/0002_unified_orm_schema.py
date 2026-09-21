"""Add the unified PetroEdge ORM schema.

Revision ID: 0002_unified_orm_schema
Revises: 0001_initial_schema
Create Date: 2026-07-19
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision: str = "0002_unified_orm_schema"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _column_names(table: str) -> set[str]:
    if not _table_exists(table):
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_columns(table)}


def _index_names(table: str) -> set[str]:
    if not _table_exists(table):
        return set()
    return {item["name"] for item in inspect(op.get_bind()).get_indexes(table)}


def _add_columns(table: str, columns: list[sa.Column]) -> None:
    existing = _column_names(table)
    with op.batch_alter_table(table) as batch:
        for column in columns:
            if column.name not in existing:
                batch.add_column(column)


def upgrade() -> None:
    _add_columns("users", [
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ])

    _add_columns("wells", [
        sa.Column("well_name", sa.String(length=200), nullable=True),
        sa.Column("operator_name", sa.String(length=200), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ])

    if not _table_exists("datasets"):
        op.create_table(
            "datasets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("well_id", sa.String(length=36), nullable=False),
            sa.Column("owner_id", sa.String(length=36), nullable=True),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("original_filename", sa.String(length=500), nullable=True),
            sa.Column("storage_path", sa.String(length=1000), nullable=True),
            sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
            sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("curve_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("min_depth_m", sa.Float(), nullable=True),
            sa.Column("max_depth_m", sa.Float(), nullable=True),
            sa.Column("qc_score", sa.Float(), nullable=True),
            sa.Column("ai_readiness_score", sa.Float(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("well_id", "name", "version", name="uq_datasets_well_name_version"),
        )
        op.create_index("ix_datasets_well_id", "datasets", ["well_id"])
        op.create_index("ix_datasets_owner_id", "datasets", ["owner_id"])
        op.create_index("ix_datasets_checksum_sha256", "datasets", ["checksum_sha256"])
        op.create_index("ix_datasets_status_created_at", "datasets", ["status", "created_at"])

    if not _table_exists("log_curves"):
        op.create_table(
            "log_curves",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("dataset_id", sa.String(length=36), nullable=False),
            sa.Column("original_name", sa.String(length=100), nullable=False),
            sa.Column("canonical_name", sa.String(length=100), nullable=False),
            sa.Column("unit", sa.String(length=50), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("minimum", sa.Float(), nullable=True),
            sa.Column("maximum", sa.Float(), nullable=True),
            sa.Column("mean", sa.Float(), nullable=True),
            sa.Column("standard_deviation", sa.Float(), nullable=True),
            sa.Column("qc_flags", sa.JSON(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("dataset_id", "canonical_name", name="uq_log_curves_dataset_canonical"),
        )
        op.create_index("ix_log_curves_dataset_id", "log_curves", ["dataset_id"])

    if not _table_exists("model_registry"):
        op.create_table(
            "model_registry",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("version", sa.String(length=100), nullable=False),
            sa.Column("task", sa.String(length=100), nullable=False),
            sa.Column("framework", sa.String(length=50), nullable=False),
            sa.Column("artifact_path", sa.String(length=1000), nullable=True),
            sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("metrics_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("feature_schema_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("name", "version", name="uq_model_registry_name_version"),
        )
        op.create_index("ix_model_registry_task_status", "model_registry", ["task", "status"])

    if not _table_exists("predictions"):
        op.create_table(
            "predictions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("well_id", sa.String(length=36), nullable=False),
            sa.Column("dataset_id", sa.String(length=36), nullable=True),
            sa.Column("model_id", sa.String(length=36), nullable=True),
            sa.Column("task", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="completed"),
            sa.Column("depth_from_m", sa.Float(), nullable=True),
            sa.Column("depth_to_m", sa.Float(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=True),
            sa.Column("runtime_ms", sa.Float(), nullable=True),
            sa.Column("input_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("output_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("explanation_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["model_id"], ["model_registry.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_predictions_well_id", "predictions", ["well_id"])
        op.create_index("ix_predictions_dataset_id", "predictions", ["dataset_id"])
        op.create_index("ix_predictions_model_id", "predictions", ["model_id"])
        op.create_index("ix_predictions_well_created_at", "predictions", ["well_id", "created_at"])
        op.create_index("ix_predictions_dataset_task", "predictions", ["dataset_id", "task"])

    if not _table_exists("analytics_runs"):
        op.create_table(
            "analytics_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("dataset_id", sa.String(length=36), nullable=True),
            sa.Column("well_id", sa.String(length=36), nullable=True),
            sa.Column("run_type", sa.String(length=100), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("progress_percent", sa.Float(), nullable=False, server_default="0"),
            sa.Column("parameters_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("result_summary_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_analytics_runs_dataset_id", "analytics_runs", ["dataset_id"])
        op.create_index("ix_analytics_runs_well_id", "analytics_runs", ["well_id"])
        op.create_index("ix_analytics_runs_dataset_status", "analytics_runs", ["dataset_id", "status"])

    _add_columns("alerts", [
        sa.Column("prediction_id", sa.String(length=36), nullable=True),
        sa.Column("alert_type", sa.String(length=100), nullable=False, server_default="general"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="open"),
        sa.Column("title", sa.String(length=255), nullable=False, server_default="PetroEdge alert"),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=36), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=100), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ])

    if not _table_exists("reports"):
        op.create_table(
            "reports",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("dataset_id", sa.String(length=36), nullable=True),
            sa.Column("prediction_id", sa.String(length=36), nullable=True),
            sa.Column("requested_by", sa.String(length=36), nullable=True),
            sa.Column("report_type", sa.String(length=100), nullable=False),
            sa.Column("format", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("storage_path", sa.String(length=1000), nullable=True),
            sa.Column("file_size_bytes", sa.Integer(), nullable=True),
            sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("parameters_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["prediction_id"], ["predictions.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_reports_dataset_id", "reports", ["dataset_id"])
        op.create_index("ix_reports_prediction_id", "reports", ["prediction_id"])
        op.create_index("ix_reports_requested_by", "reports", ["requested_by"])
        op.create_index("ix_reports_status_created_at", "reports", ["status", "created_at"])

    if not _table_exists("stream_sessions"):
        op.create_table(
            "stream_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("well_id", sa.String(length=36), nullable=False),
            sa.Column("source_type", sa.String(length=50), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_sample_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sample_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("connection_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["well_id"], ["wells.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_stream_sessions_well_id", "stream_sessions", ["well_id"])
        op.create_index("ix_stream_sessions_well_status", "stream_sessions", ["well_id", "status"])

    if not _table_exists("audit_logs"):
        op.create_table(
            "audit_logs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=36), nullable=True),
            sa.Column("action", sa.String(length=100), nullable=False),
            sa.Column("resource_type", sa.String(length=100), nullable=False),
            sa.Column("resource_id", sa.String(length=100), nullable=True),
            sa.Column("request_id", sa.String(length=100), nullable=True),
            sa.Column("ip_address", sa.String(length=64), nullable=True),
            sa.Column("user_agent", sa.String(length=500), nullable=True),
            sa.Column("details_json", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
        op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
        op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
        op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])

    for table, indexes in {
        "log_samples": [("ix_log_samples_well_depth", ["well_id", "depth_m"]), ("ix_log_samples_time", ["time"])],
        "analytics_results": [("ix_analytics_results_well_depth", ["well_id", "depth_m"]), ("ix_analytics_results_time", ["time"])],
    }.items():
        existing = _index_names(table)
        for name, columns in indexes:
            if name not in existing:
                op.create_index(name, table, columns)


def downgrade() -> None:
    for table in ("audit_logs", "stream_sessions", "reports", "analytics_runs", "predictions", "model_registry", "log_curves", "datasets"):
        if _table_exists(table):
            op.drop_table(table)

    # Existing legacy tables are deliberately retained on downgrade to avoid
    # destructive loss of operational user, well, log, analytics and alert data.
