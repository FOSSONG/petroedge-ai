from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.core.rbac import require_roles
from app.ml_lifecycle.schemas import (
    PredictionRequest,
    RetrainRequest,
    StageUpdate,
    TrainingConfig,
    TrainingResult,
)
from app.ml_lifecycle.service import (
    algorithm_catalog,
    delete_model,
    get_model,
    list_models,
    predict_dataset,
    prediction_output_path,
    retrain,
    train_and_register,
    update_stage,
)

router = APIRouter()
READ = require_roles("admin", "geoscientist", "engineer", "viewer")
WRITE = require_roles("admin", "geoscientist", "engineer")


@router.get("/algorithms")
def algorithms(_: dict[str, Any] = Depends(READ)):
    return {"algorithms": algorithm_catalog()}


@router.post("/train", response_model=TrainingResult)
def train(payload: TrainingConfig, _: dict[str, Any] = Depends(WRITE)):
    try:
        return train_and_register(payload)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/registry")
def registry(_: dict[str, Any] = Depends(READ)):
    return {"models": list_models()}


@router.get("/registry/{model_id}")
def model(model_id: str, _: dict[str, Any] = Depends(READ)):
    try:
        return get_model(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Registered model not found.") from exc


@router.delete("/registry/{model_id}")
def remove_model(model_id: str, _: dict[str, Any] = Depends(WRITE)):
    try:
        return delete_model(model_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Registered model not found.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not remove model artefacts: {exc}") from exc


@router.patch("/registry/{model_id}/stage")
def stage(model_id: str, payload: StageUpdate, _: dict[str, Any] = Depends(WRITE)):
    try:
        return update_stage(model_id, payload.stage)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Registered model not found.") from exc


@router.post("/predict")
def predict(payload: PredictionRequest, _: dict[str, Any] = Depends(WRITE)):
    try:
        return predict_dataset(payload.model_id, payload.dataset_id, payload.output_column)
    except (KeyError, ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/registry/{model_id}/retrain", response_model=TrainingResult)
def retrain_model(model_id: str, payload: RetrainRequest, _: dict[str, Any] = Depends(WRITE)):
    try:
        return retrain(model_id, payload.dataset_id, payload.display_name, payload.hyperparameters)
    except (KeyError, ValueError, RuntimeError, FileNotFoundError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/predictions/{output_name}/download")
def download_prediction(output_name: str, _: dict[str, Any] = Depends(READ)):
    try:
        path = prediction_output_path(output_name)
        return FileResponse(path, filename=path.name, media_type="text/csv")
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
