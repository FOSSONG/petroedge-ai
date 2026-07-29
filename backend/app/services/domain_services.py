from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.db.models import AnalyticsResultRecord, Dataset, JobStatus, User, Well
from app.db.repositories.domain import DatasetRepository, UserRepository, WellRepository


class AuthenticationService:
    def __init__(self, users: UserRepository) -> None:
        self.users = users

    def authenticate(self, email: str, password: str) -> User | None:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


class WellService:
    def __init__(self, wells: WellRepository) -> None:
        self.wells = wells

    @staticmethod
    def serialize(well: Well) -> dict[str, Any]:
        metadata = well.metadata_json or {}
        return {
            "well_id": well.well_id,
            "field": well.field_name,
            "status": well.status,
            "kb_m": metadata.get("kb_m"),
            "total_depth_m": well.total_depth_m,
            "sample_count": metadata.get("sample_count"),
            "source": metadata.get("source", "database"),
        }


class IngestionPersistenceService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.wells = WellRepository(session)
        self.datasets = DatasetRepository(session)

    def persist_dataset(
        self,
        *,
        well_public_id: str,
        source_type: str,
        filename: str | None,
        storage_path: str | None,
        row_count: int,
        metadata: dict[str, Any] | None = None,
        owner_id: str | None = None,
    ) -> Dataset:
        well = self.wells.get_or_create(well_public_id)
        dataset = Dataset(
            well_id=well.id,
            owner_id=owner_id,
            name=filename or f"{well_public_id}-{source_type}",
            source_type=source_type,
            original_filename=filename,
            storage_path=storage_path,
            row_count=row_count,
            status=JobStatus.COMPLETED.value,
            metadata_json=metadata or {},
        )
        return self.datasets.add(dataset)


class AnalyticsPersistenceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def persist_sample_result(self, result: dict[str, Any]) -> AnalyticsResultRecord:
        input_data = result.get("input", {})
        record = AnalyticsResultRecord(
            well_id=str(input_data.get("well_id", "UNKNOWN")),
            depth_m=float(input_data.get("depth_m", 0.0)),
            qc_score=float(result.get("qc_score", 0.0)),
            hydrocarbon_probability=float(result.get("hydrocarbon_probability", 0.0)),
            lithology=str(result.get("lithology", "unknown")),
            facies=str(result.get("facies", "unknown")),
            anomaly_score=float(result.get("anomaly_score", 0.0)),
            porosity=float(result.get("porosity", 0.0)),
            water_saturation=float(result.get("water_saturation", 0.0)),
            shale_volume=float(result.get("shale_volume", 0.0)),
            net_to_gross=float(result.get("net_to_gross", 0.0)),
            permeability_md=float(result.get("permeability_md", 0.0)),
            explanation=result.get("explanation", {}),
        )
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record
