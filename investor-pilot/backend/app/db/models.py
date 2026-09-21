from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def uuid_str() -> str:
    return str(uuid4())


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    GEOSCIENTIST = "geoscientist"
    ENGINEER = "engineer"
    VIEWER = "viewer"


class RecordStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(40), default=UserRole.VIEWER.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    datasets: Mapped[list[Dataset]] = relationship(back_populates="owner")
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="user")


class Well(TimestampMixin, Base):
    __tablename__ = "wells"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    well_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    well_name: Mapped[str | None] = mapped_column(String(200))
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    operator_name: Mapped[str | None] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    total_depth_m: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default=RecordStatus.ACTIVE.value, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    datasets: Mapped[list[Dataset]] = relationship(back_populates="well", cascade="all, delete-orphan")
    log_samples: Mapped[list[LogSample]] = relationship(back_populates="well")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="well")
    alerts: Mapped[list[AlertRecord]] = relationship(back_populates="well")
    stream_sessions: Mapped[list[StreamSession]] = relationship(back_populates="well")


class Dataset(TimestampMixin, Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("well_id", "name", "version", name="uq_datasets_well_name_version"),
        Index("ix_datasets_status_created_at", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    well_id: Mapped[str] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    curve_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    min_depth_m: Mapped[float | None] = mapped_column(Float)
    max_depth_m: Mapped[float | None] = mapped_column(Float)
    qc_score: Mapped[float | None] = mapped_column(Float)
    ai_readiness_score: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    well: Mapped[Well] = relationship(back_populates="datasets")
    owner: Mapped[User | None] = relationship(back_populates="datasets")
    curves: Mapped[list[LogCurve]] = relationship(back_populates="dataset", cascade="all, delete-orphan")
    predictions: Mapped[list[Prediction]] = relationship(back_populates="dataset")
    analytics_runs: Mapped[list[AnalyticsRun]] = relationship(back_populates="dataset")
    reports: Mapped[list[Report]] = relationship(back_populates="dataset")


class LogCurve(TimestampMixin, Base):
    __tablename__ = "log_curves"
    __table_args__ = (
        UniqueConstraint("dataset_id", "canonical_name", name="uq_log_curves_dataset_canonical"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True, nullable=False)
    original_name: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_name: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    minimum: Mapped[float | None] = mapped_column(Float)
    maximum: Mapped[float | None] = mapped_column(Float)
    mean: Mapped[float | None] = mapped_column(Float)
    standard_deviation: Mapped[float | None] = mapped_column(Float)
    qc_flags: Mapped[list[Any]] = mapped_column(JSON, default=list, nullable=False)

    dataset: Mapped[Dataset] = relationship(back_populates="curves")


class LogSample(Base):
    __tablename__ = "log_samples"
    __table_args__ = (
        Index("ix_log_samples_well_depth", "well_id", "depth_m"),
        Index("ix_log_samples_time", "time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    well_id: Mapped[str] = mapped_column(ForeignKey("wells.well_id", ondelete="CASCADE"), nullable=False)
    depth_m: Mapped[float] = mapped_column(Float, nullable=False)
    gamma_ray_api: Mapped[float | None] = mapped_column(Float)
    resistivity_ohmm: Mapped[float | None] = mapped_column(Float)
    density_gcc: Mapped[float | None] = mapped_column(Float)
    neutron_porosity_vv: Mapped[float | None] = mapped_column(Float)
    sonic_usft: Mapped[float | None] = mapped_column(Float)
    caliper_in: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)

    well: Mapped[Well] = relationship(back_populates="log_samples", primaryjoin="LogSample.well_id == Well.well_id")


class ModelRegistry(TimestampMixin, Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_model_registry_name_version"),
        Index("ix_model_registry_task_status", "task", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    task: Mapped[str] = mapped_column(String(100), nullable=False)
    framework: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(String(1000))
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default=RecordStatus.ACTIVE.value, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    feature_schema_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    predictions: Mapped[list[Prediction]] = relationship(back_populates="model")


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (
        Index("ix_predictions_well_created_at", "well_id", "created_at"),
        Index("ix_predictions_dataset_task", "dataset_id", "task"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    well_id: Mapped[str] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True, nullable=False)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("model_registry.id", ondelete="SET NULL"), index=True)
    task: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.COMPLETED.value, nullable=False)
    depth_from_m: Mapped[float | None] = mapped_column(Float)
    depth_to_m: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    runtime_ms: Mapped[float | None] = mapped_column(Float)
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    explanation_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    well: Mapped[Well] = relationship(back_populates="predictions")
    dataset: Mapped[Dataset | None] = relationship(back_populates="predictions")
    model: Mapped[ModelRegistry | None] = relationship(back_populates="predictions")
    alerts: Mapped[list[AlertRecord]] = relationship(back_populates="prediction")


class AnalyticsRun(TimestampMixin, Base):
    __tablename__ = "analytics_runs"
    __table_args__ = (Index("ix_analytics_runs_dataset_status", "dataset_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    well_id: Mapped[str | None] = mapped_column(ForeignKey("wells.id", ondelete="SET NULL"), index=True)
    run_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_summary_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset | None] = relationship(back_populates="analytics_runs")


class AnalyticsResultRecord(Base):
    __tablename__ = "analytics_results"
    __table_args__ = (
        Index("ix_analytics_results_well_depth", "well_id", "depth_m"),
        Index("ix_analytics_results_time", "time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    well_id: Mapped[str] = mapped_column(String(100), nullable=False)
    depth_m: Mapped[float] = mapped_column(Float, nullable=False)
    qc_score: Mapped[float] = mapped_column(Float, nullable=False)
    hydrocarbon_probability: Mapped[float] = mapped_column(Float, nullable=False)
    lithology: Mapped[str] = mapped_column(String(100), nullable=False)
    facies: Mapped[str] = mapped_column(String(100), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    porosity: Mapped[float] = mapped_column(Float, nullable=False)
    water_saturation: Mapped[float] = mapped_column(Float, nullable=False)
    shale_volume: Mapped[float] = mapped_column(Float, nullable=False)
    net_to_gross: Mapped[float] = mapped_column(Float, nullable=False)
    permeability_md: Mapped[float] = mapped_column(Float, nullable=False)
    explanation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)


class AlertRecord(TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_severity_created", "status", "severity", "created_at"),
        Index("ix_alerts_well_created", "well_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    well_id: Mapped[str | None] = mapped_column(ForeignKey("wells.id", ondelete="SET NULL"), index=True)
    prediction_id: Mapped[str | None] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"), index=True)
    alert_type: Mapped[str] = mapped_column(String(100), default="general", nullable=False)
    severity: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=AlertStatus.OPEN.value, nullable=False)
    title: Mapped[str] = mapped_column(String(255), default="PetroEdge alert", nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(100))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    well: Mapped[Well | None] = relationship(back_populates="alerts")
    prediction: Mapped[Prediction | None] = relationship(back_populates="alerts")


class Report(TimestampMixin, Base):
    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_status_created_at", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    dataset_id: Mapped[str | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"), index=True)
    prediction_id: Mapped[str | None] = mapped_column(ForeignKey("predictions.id", ondelete="SET NULL"), index=True)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    report_type: Mapped[str] = mapped_column(String(100), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    dataset: Mapped[Dataset | None] = relationship(back_populates="reports")


class StreamSession(TimestampMixin, Base):
    __tablename__ = "stream_sessions"
    __table_args__ = (Index("ix_stream_sessions_well_status", "well_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    well_id: Mapped[str] = mapped_column(ForeignKey("wells.id", ondelete="CASCADE"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sample_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sample_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    connection_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)

    well: Mapped[Well] = relationship(back_populates="stream_sessions")


class BackgroundJob(TimestampMixin, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        Index("ix_background_jobs_status_priority_created", "status", "priority", "created_at"),
        Index("ix_background_jobs_task_created", "task_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    task_name: Mapped[str] = mapped_column(String(150), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.PENDING.value, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(100))
    request_id: Mapped[str | None] = mapped_column(String(100), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(500))
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User | None] = relationship(back_populates="audit_logs")


__all__ = [
    "AlertRecord", "AlertStatus", "AnalyticsResultRecord", "AnalyticsRun", "AuditLog", "BackgroundJob",
    "Dataset", "JobStatus", "LogCurve", "LogSample", "ModelRegistry", "Prediction",
    "RecordStatus", "Report", "StreamSession", "User", "UserRole", "Well",
]
