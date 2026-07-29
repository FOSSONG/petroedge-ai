from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AlertRecord, Dataset, ModelRegistry, Prediction, User, Well
from app.db.repositories.base import Repository


class UserRepository(Repository[User]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, User)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(
            select(User).where(User.email == email.strip().lower())
        )


class WellRepository(Repository[Well]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Well)

    def get_by_well_id(self, well_id: str) -> Well | None:
        return self.session.scalar(
            select(Well).where(Well.well_id == well_id.strip())
        )

    def list_ordered(self, *, offset: int = 0, limit: int = 100) -> Sequence[Well]:
        statement = (
            select(Well)
            .order_by(Well.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return self.session.scalars(statement).all()

    def get_or_create(
        self,
        well_id: str,
        *,
        field_name: str = "Unassigned field",
        status: str = "active",
    ) -> Well:
        existing = self.get_by_well_id(well_id)
        if existing is not None:
            return existing
        return self.add(
            Well(
                well_id=well_id.strip(),
                well_name=well_id.strip(),
                field_name=field_name,
                status=status,
                metadata_json={},
            )
        )


class DatasetRepository(Repository[Dataset]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Dataset)

    def list_for_well(self, well_db_id: str, *, limit: int = 100) -> Sequence[Dataset]:
        statement = (
            select(Dataset)
            .where(Dataset.well_id == well_db_id)
            .order_by(Dataset.created_at.desc())
            .limit(limit)
        )
        return self.session.scalars(statement).all()


class ModelRegistryRepository(Repository[ModelRegistry]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ModelRegistry)

    def get_default(self, task: str) -> ModelRegistry | None:
        statement = select(ModelRegistry).where(
            ModelRegistry.task == task,
            ModelRegistry.is_default.is_(True),
            ModelRegistry.status == "active",
        )
        return self.session.scalar(statement)

    def get_by_name_version(self, name: str, version: str) -> ModelRegistry | None:
        return self.session.scalar(
            select(ModelRegistry).where(
                ModelRegistry.name == name,
                ModelRegistry.version == version,
            )
        )


class PredictionRepository(Repository[Prediction]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Prediction)

    def recent_for_well(self, well_db_id: str, *, limit: int = 100) -> Sequence[Prediction]:
        statement = (
            select(Prediction)
            .where(Prediction.well_id == well_db_id)
            .order_by(Prediction.created_at.desc())
            .limit(limit)
        )
        return self.session.scalars(statement).all()


class AlertRepository(Repository[AlertRecord]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, AlertRecord)

    def filtered(
        self,
        *,
        well_db_id: str | None = None,
        severity: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> Sequence[AlertRecord]:
        statement = select(AlertRecord)
        if well_db_id is not None:
            statement = statement.where(AlertRecord.well_id == well_db_id)
        if severity:
            statement = statement.where(AlertRecord.severity == severity.lower())
        if status:
            statement = statement.where(AlertRecord.status == status.lower())
        statement = statement.order_by(AlertRecord.created_at.desc()).limit(limit)
        return self.session.scalars(statement).all()

    def open_alerts(self, *, well_db_id: str | None = None, limit: int = 100) -> Sequence[AlertRecord]:
        return self.filtered(well_db_id=well_db_id, status="open", limit=limit)

    def acknowledge(self, alert_id: str, *, user_id: str | None = None) -> AlertRecord:
        alert = self.require(alert_id)
        alert.status = "acknowledged"
        alert.acknowledged = True
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = user_id
        self.session.commit()
        self.session.refresh(alert)
        return alert

    def resolve(self, alert_id: str) -> AlertRecord:
        alert = self.require(alert_id)
        alert.status = "resolved"
        alert.resolved_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(alert)
        return alert
