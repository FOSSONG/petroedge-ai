from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.repositories.jobs import BackgroundJobRepository
from app.db.repositories.domain import (
    AlertRepository,
    DatasetRepository,
    ModelRegistryRepository,
    PredictionRepository,
    UserRepository,
    WellRepository,
)
from app.db.session import get_db

DBSession = Annotated[Session, Depends(get_db)]


def get_user_repository(db: DBSession) -> UserRepository:
    return UserRepository(db)


def get_well_repository(db: DBSession) -> WellRepository:
    return WellRepository(db)


def get_dataset_repository(db: DBSession) -> DatasetRepository:
    return DatasetRepository(db)


def get_model_repository(db: DBSession) -> ModelRegistryRepository:
    return ModelRegistryRepository(db)


def get_prediction_repository(db: DBSession) -> PredictionRepository:
    return PredictionRepository(db)


def get_alert_repository(db: DBSession) -> AlertRepository:
    return AlertRepository(db)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
WellRepo = Annotated[WellRepository, Depends(get_well_repository)]
DatasetRepo = Annotated[DatasetRepository, Depends(get_dataset_repository)]
ModelRepo = Annotated[ModelRegistryRepository, Depends(get_model_repository)]
PredictionRepo = Annotated[PredictionRepository, Depends(get_prediction_repository)]
AlertRepo = Annotated[AlertRepository, Depends(get_alert_repository)]


def get_job_repository(db: DBSession) -> BackgroundJobRepository:
    return BackgroundJobRepository(db)


JobRepo = Annotated[BackgroundJobRepository, Depends(get_job_repository)]
