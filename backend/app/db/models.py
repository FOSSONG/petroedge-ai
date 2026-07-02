from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Well(Base):
    __tablename__ = "wells"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    well_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    field_name: Mapped[str] = mapped_column(String)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    kb_m: Mapped[float | None] = mapped_column(Float)
    total_depth_m: Mapped[float | None] = mapped_column(Float)


class LogSample(Base):
    __tablename__ = "log_samples"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    well_id: Mapped[str] = mapped_column(String, ForeignKey("wells.well_id"), primary_key=True)
    depth_m: Mapped[float] = mapped_column(Float, primary_key=True)
    gamma_ray_api: Mapped[float | None] = mapped_column(Float)
    resistivity_ohmm: Mapped[float | None] = mapped_column(Float)
    density_gcc: Mapped[float | None] = mapped_column(Float)
    neutron_porosity_vv: Mapped[float | None] = mapped_column(Float)
    sonic_usft: Mapped[float | None] = mapped_column(Float)
    caliper_in: Mapped[float | None] = mapped_column(Float)
    source_type: Mapped[str] = mapped_column(String)


class AnalyticsResultRecord(Base):
    __tablename__ = "analytics_results"

    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    well_id: Mapped[str] = mapped_column(String, ForeignKey("wells.well_id"), primary_key=True)
    depth_m: Mapped[float] = mapped_column(Float, primary_key=True)
    qc_score: Mapped[float] = mapped_column(Float)
    hydrocarbon_probability: Mapped[float] = mapped_column(Float)
    lithology: Mapped[str] = mapped_column(String)
    facies: Mapped[str] = mapped_column(String)
    anomaly_score: Mapped[float] = mapped_column(Float)
    porosity: Mapped[float] = mapped_column(Float)
    water_saturation: Mapped[float] = mapped_column(Float)
    shale_volume: Mapped[float] = mapped_column(Float)
    net_to_gross: Mapped[float] = mapped_column(Float)
    permeability_md: Mapped[float] = mapped_column(Float)
    explanation: Mapped[dict] = mapped_column(JSONB)


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    well_id: Mapped[str] = mapped_column(String, ForeignKey("wells.well_id"))
    severity: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

