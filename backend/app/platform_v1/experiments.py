from __future__ import annotations

import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.platform_v1.database import audit, connection, utcnow
from app.platform_v1.datasets import get_dataset_path
from app.platform_v1.schemas import ExperimentCreate, ExperimentSummary

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="petroedge-training")

def _update(experiment_id: str, *, status: str | None = None, progress: int | None = None, stage: str | None = None, metrics: dict[str, Any] | None = None, training_seconds: float | None = None, model_id: str | None = None, error: str | None = None) -> None:
    fields, values = [], []
    for key, value in (("status", status), ("progress_percent", progress), ("current_stage", stage), ("training_seconds", training_seconds), ("model_id", model_id), ("error_message", error)):
        if value is not None:
            fields.append(f"{key} = ?"); values.append(value)
    if metrics is not None:
        fields.append("metrics_json = ?"); values.append(json.dumps(metrics, default=str))
    fields.append("updated_at = ?"); values.append(utcnow())
    values.append(experiment_id)
    with connection() as conn:
        conn.execute(f"UPDATE experiments SET {', '.join(fields)} WHERE experiment_id = ?", values)

def _load_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv": return pd.read_csv(path)
    if path.suffix.lower() == ".parquet": return pd.read_parquet(path)
    if path.suffix.lower() == ".las":
        import lasio
        return lasio.read(path).df().reset_index()
    raise ValueError("Unsupported dataset type")

def _find_col(frame: pd.DataFrame, names: list[str]) -> str | None:
    lookup={str(c).lower().replace("_","").replace(" ",""): str(c) for c in frame.columns}
    for n in names:
        k=n.lower().replace("_","").replace(" ","")
        if k in lookup: return lookup[k]
    return None

def _target(frame: pd.DataFrame, task: str) -> tuple[pd.Series, str, bool]:
    candidates={
      "lithology_classification":["lithology","facies","class"],
      "hydrocarbon_classification":["hydrocarbon","fluid","hc_label","target"],
      "porosity_regression":["porosity","phi","phie"],
      "permeability_regression":["permeability","perm","k_md"],
      "water_saturation_regression":["water_saturation","sw","saturation"],
    }.get(task, ["target"])
    col=_find_col(frame,candidates)
    if col: return frame[col], col, False
    gr=_find_col(frame,["GR","gamma_ray","gamma ray"]); rt=_find_col(frame,["RT","ILD","resistivity"]); rhob=_find_col(frame,["RHOB","density"]); nphi=_find_col(frame,["NPHI","neutron"])
    numeric=lambda c: pd.to_numeric(frame[c], errors="coerce") if c else pd.Series(np.nan,index=frame.index)
    if task=="lithology_classification":
        g=numeric(gr).fillna(numeric(gr).median() if gr else 75); return pd.cut(g,[-np.inf,60,90,np.inf],labels=["Sandstone","Shaly Sand","Shale"]).astype(str),"derived_lithology",True
    if task=="hydrocarbon_classification":
        g=numeric(gr); r=numeric(rt); score=(r.fillna(r.median())>r.median()).astype(int)+(g.fillna(g.median())<g.median()).astype(int); return (score>=1).astype(int),"derived_hydrocarbon",True
    if task=="porosity_regression":
        if rhob: return ((2.65-numeric(rhob))/(2.65-1.0)).clip(0,0.45),"derived_density_porosity",True
        if nphi: return numeric(nphi).clip(0,0.45),"derived_neutron_porosity",True
    if task=="permeability_regression":
        phi=((2.65-numeric(rhob))/(1.65)).clip(.01,.4) if rhob else numeric(nphi).clip(.01,.4); return (1000*phi**3/(1-phi)**2).clip(0,5000),"derived_timur_proxy",True
    phi=((2.65-numeric(rhob))/(1.65)).clip(.03,.4) if rhob else numeric(nphi).clip(.03,.4); r=numeric(rt).clip(lower=.1); return np.sqrt(.1/(r*phi**2)).clip(0,1),"derived_archie_sw",True

def _train(experiment_id: str, payload: ExperimentCreate) -> None:
    started=time.perf_counter()
    try:
        _update(experiment_id,status="running",progress=8,stage="Loading dataset")
        if not payload.dataset_id: raise ValueError("Select a dataset before starting training.")
        frame=_load_frame(get_dataset_path(payload.dataset_id))
        if len(frame)<8: raise ValueError("At least 8 rows are required for a training run.")
        _update(experiment_id,progress=24,stage="Preparing features")
        y,target_name,derived=_target(frame,payload.task)
        numeric=frame.select_dtypes(include=[np.number]).copy()
        numeric=numeric.drop(columns=[target_name],errors="ignore").replace([np.inf,-np.inf],np.nan)
        numeric=numeric.loc[:, numeric.notna().sum()>0].fillna(numeric.median(numeric_only=True))
        if numeric.shape[1]==0: raise ValueError("No numeric predictor columns were found.")
        valid=y.notna(); X=numeric.loc[valid]; y=y.loc[valid]
        _update(experiment_id,progress=42,stage="Splitting validation data")
        from sklearn.model_selection import train_test_split
        classification="classification" in payload.task
        stratify=y if classification and y.value_counts().min()>=2 else None
        test_size=max(2,min(int(round(len(X)*.25)),len(X)-2))
        Xtr,Xte,ytr,yte=train_test_split(X,y,test_size=test_size,random_state=42,stratify=stratify)
        _update(experiment_id,progress=58,stage=f"Training {payload.algorithm}")
        algo=payload.algorithm.lower()
        if classification:
            from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
            from sklearn.neural_network import MLPClassifier
            model=MLPClassifier(hidden_layer_sizes=(32,16),max_iter=400,random_state=42) if algo in {"ann","cnn","transformer"} else (GradientBoostingClassifier(random_state=42) if algo in {"xgboost","lightgbm","catboost"} else RandomForestClassifier(n_estimators=120,random_state=42,n_jobs=-1))
        else:
            from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
            from sklearn.neural_network import MLPRegressor
            model=MLPRegressor(hidden_layer_sizes=(32,16),max_iter=500,random_state=42) if algo in {"ann","cnn","transformer"} else (GradientBoostingRegressor(random_state=42) if algo in {"xgboost","lightgbm","catboost"} else RandomForestRegressor(n_estimators=120,random_state=42,n_jobs=-1))
        model.fit(Xtr,ytr); pred=model.predict(Xte)
        _update(experiment_id,progress=82,stage="Validating model")
        if classification:
            from sklearn.metrics import accuracy_score, f1_score
            metrics={"accuracy":round(float(accuracy_score(yte,pred)),4),"f1_weighted":round(float(f1_score(yte,pred,average="weighted",zero_division=0)),4)}
        else:
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
            metrics={"mae":round(float(mean_absolute_error(yte,pred)),5),"rmse":round(float(mean_squared_error(yte,pred)**.5),5),"r2":round(float(r2_score(yte,pred)),5) if len(yte)>1 else None}
        metrics.update({"rows":int(len(frame)),"training_rows":int(len(Xtr)),"validation_rows":int(len(Xte)),"feature_count":int(X.shape[1]),"target":target_name,"target_derived":derived,"algorithm_engine":type(model).__name__})
        _update(experiment_id,progress=94,stage="Registering result")
        model_id=f"candidate-{experiment_id[4:]}"
        _update(experiment_id,status="completed",progress=100,stage="Completed",metrics=metrics,training_seconds=round(time.perf_counter()-started,3),model_id=model_id,error="")
        audit("experiment.completed","experiment",experiment_id,None,metrics)
    except Exception as exc:
        _update(experiment_id,status="failed",progress=100,stage="Failed",training_seconds=round(time.perf_counter()-started,3),error=str(exc))
        audit("experiment.failed","experiment",experiment_id,None,{"error":str(exc)})

def create_experiment(payload: ExperimentCreate, owner_id: str | None) -> ExperimentSummary:
    experiment_id=f"exp-{uuid.uuid4().hex[:12]}"; now=utcnow()
    with connection() as conn:
        conn.execute("""INSERT INTO experiments(experiment_id,name,task,dataset_id,algorithm,model_id,status,parameters_json,metrics_json,training_seconds,model_size_bytes,validation_strategy,progress_percent,current_stage,error_message,owner_id,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(experiment_id,payload.name,payload.task,payload.dataset_id,payload.algorithm,payload.model_id,"queued",json.dumps(payload.parameters),json.dumps(payload.metrics),payload.training_seconds,payload.model_size_bytes,payload.validation_strategy,0,"Queued",None,owner_id,now,now))
    audit("experiment.created","experiment",experiment_id,owner_id,payload.model_dump())
    _EXECUTOR.submit(_train,experiment_id,payload)
    return get_experiment(experiment_id)

def _row_to_model(row) -> ExperimentSummary:
    keys=set(row.keys())
    return ExperimentSummary(experiment_id=row["experiment_id"],name=row["name"],task=row["task"],dataset_id=row["dataset_id"],algorithm=row["algorithm"],model_id=row["model_id"],status=row["status"],parameters=json.loads(row["parameters_json"]),metrics=json.loads(row["metrics_json"]),training_seconds=row["training_seconds"],model_size_bytes=row["model_size_bytes"],validation_strategy=row["validation_strategy"],progress_percent=row["progress_percent"] if "progress_percent" in keys else 0,current_stage=row["current_stage"] if "current_stage" in keys else None,error_message=row["error_message"] if "error_message" in keys else None,owner_id=row["owner_id"],created_at=row["created_at"],updated_at=row["updated_at"])

def list_experiments() -> list[ExperimentSummary]:
    with connection() as conn: rows=conn.execute("SELECT * FROM experiments ORDER BY created_at DESC").fetchall()
    return [_row_to_model(r) for r in rows]

def get_experiment(experiment_id: str) -> ExperimentSummary:
    with connection() as conn: row=conn.execute("SELECT * FROM experiments WHERE experiment_id=?",(experiment_id,)).fetchone()
    if row is None: raise KeyError(experiment_id)
    return _row_to_model(row)
