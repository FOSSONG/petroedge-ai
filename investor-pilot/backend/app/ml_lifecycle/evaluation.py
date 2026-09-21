"""Audited, one-use independent evaluation for prepared-data models.

SQLite reservations survive model deletion and serialize concurrent test claims.
Scientific thresholds must be supplied in the approved training contract.
"""
from __future__ import annotations
import hashlib
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import joblib
from app.ml_lifecycle.prepared import load_prepared, locked_partitions
from app.ml_lifecycle.schemas import TrainingConfig, TaskType


def _hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def _db():
    from app.ml_lifecycle import service
    path = service.STORE_ROOT.parent / "independent_evaluation.sqlite3"
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path,timeout=15)
    conn.row_factory=sqlite3.Row
    conn.execute("CREATE TABLE IF NOT EXISTS evaluations (model_id TEXT PRIMARY KEY, identity TEXT NOT NULL, status TEXT NOT NULL, result TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS test_reservations (specimen_key TEXT PRIMARY KEY, model_id TEXT NOT NULL)")
    conn.commit()
    return conn


def _file(manifest, key):
    from app.ml_lifecycle import service
    folder=(service.STORE_ROOT/manifest["model_id"]).resolve()
    if folder.parent != service.STORE_ROOT.resolve():
        raise ValueError("Invalid model directory.")
    path=(service.BACKEND_ROOT/manifest[key]).resolve()
    if path.parent != folder or not path.is_file():
        raise ValueError("Model file is missing or outside its registered directory.")
    return path


def _inputs(model_id):
    from app.ml_lifecycle import service
    manifest=service.get_model(model_id)
    contract=manifest.get("prepared_contract")
    if not contract:
        raise ValueError("Independent evaluation requires a prepared-data model.")
    config=TrainingConfig.model_validate_json(_file(manifest,"configuration_path").read_text(encoding="utf-8"))
    if service._configuration_hash(config)!=manifest["configuration_hash"]:
        raise ValueError("Training configuration checksum mismatch.")
    artifact=_file(manifest,"artefact_path")
    artifact_bytes=artifact.read_bytes()
    if hashlib.sha256(artifact_bytes).hexdigest()!=manifest["artefact_sha256"]:
        raise ValueError("Model artifact checksum mismatch.")
    frame=load_prepared(config)
    if frame.attrs["prepared_contract"]!=contract:
        raise ValueError("Prepared contract changed since training; independent evaluation is blocked.")
    train,validation,test=locked_partitions(frame,contract["assignments"])
    policy=contract.get("evaluation_policy")
    allowed={"mae","rmse","r2"} if config.task_type==TaskType.regression else {"accuracy","precision_weighted","recall_weighted","f1_weighted"}
    if not isinstance(policy,dict) or not policy.get("policy_id") or not isinstance(policy.get("criteria"),dict) or not policy["criteria"]:
        raise ValueError("An evaluation policy must be approved before training.")
    for key in ("minimum_test_rows","minimum_test_groups"):
        if type(policy.get(key)) is not int or policy[key]<1:
            raise ValueError("Evaluation policy requires positive minimum test rows and groups.")
    for metric,bounds in policy["criteria"].items():
        if metric not in allowed or not isinstance(bounds,dict) or not bounds or not set(bounds)<= {"min","max"}:
            raise ValueError("Invalid evaluation metric or bounds.")
        if any(type(x) not in (int,float) or not math.isfinite(x) for x in bounds.values()):
            raise ValueError("Evaluation bounds must be finite numbers.")
        if "min" in bounds and "max" in bounds and bounds["min"]>bounds["max"]:
            raise ValueError("Evaluation bounds are inverted.")
    if len(test)<policy["minimum_test_rows"] or test.split_group_id.nunique()<policy["minimum_test_groups"]:
        raise ValueError("Reserved test partition does not meet the predeclared sample/group minimums.")
    identity=_hash({"artifact":manifest["artefact_sha256"],"config":manifest["configuration_hash"],"contract":contract})
    return manifest,config,artifact_bytes,train,test,policy,identity


def evaluation_result(model_id):
    from app.ml_lifecycle import service
    manifest=service.get_model(model_id)
    policy=(manifest.get("prepared_contract") or {}).get("evaluation_policy")
    conn=_db()
    try:
        row=conn.execute("SELECT status,result FROM evaluations WHERE model_id=?",(model_id,)).fetchone()
        return {"status":"not_evaluated", "policy":policy} if row is None else {"status":row["status"],"policy":policy,"result":json.loads(row["result"]) if row["result"] else None}
    finally:
        conn.close()


def evaluate_once(model_id, actor):
    from app.ml_lifecycle import service
    manifest,config,artifact_bytes,train,test,policy,identity=_inputs(model_id)
    contract=manifest["prepared_contract"]
    # Identity deliberately excludes dataset versions and model IDs: changing a
    # catalog version must not make the same held-out specimen unseen again.
    keys=[_hash({"specimen":str(row.specimen_id),"group":str(row.split_group_id),
                 "target":contract["target_definition"],"condition":contract["condition"]})
          for row in test.itertuples()]
    conn=_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        previous=conn.execute("SELECT * FROM evaluations WHERE model_id=?",(model_id,)).fetchone()
        if previous:
            conn.rollback()
            if previous["identity"]!=identity:
                raise ValueError("Model identity differs from its recorded evaluation.")
            if previous["status"]=="completed":
                return json.loads(previous["result"])
            raise ValueError("Test evaluation already claimed or failed; automatic reuse is blocked.")
        conn.execute("INSERT INTO evaluations VALUES (?,?,?,NULL)",(model_id,identity,"running"))
        try:
            conn.executemany("INSERT INTO test_reservations VALUES (?,?)",[(key,model_id) for key in keys])
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise ValueError("Test specimens have already been reserved by another candidate.") from exc
        conn.commit()
        try:
            from io import BytesIO
            model=joblib.load(BytesIO(artifact_bytes))
            predictions=model.predict(test[config.feature_columns])
            metrics=service._metrics(test[config.target_column],predictions,config.task_type)
            if not all(math.isfinite(float(v)) for v in metrics.values()):
                raise ValueError("Independent evaluation produced non-finite metrics.")
            failures=[]
            for name,bounds in policy["criteria"].items():
                value=metrics[name]
                if "min" in bounds and value<bounds["min"]: failures.append(name+" below minimum")
                if "max" in bounds and value>bounds["max"]: failures.append(name+" above maximum")
            if config.task_type==TaskType.classification and not set(train[config.target_column]).issubset(set(test[config.target_column])):
                failures.append("Test partition does not cover every training class")
            result={"model_id":model_id,"evaluated_at":datetime.now(timezone.utc).isoformat(),
                    "actor":str(actor),"identity_sha256":identity,"policy":policy,"metrics":metrics,
                    "test_rows":len(test),"test_groups":int(test.split_group_id.nunique()),
                    "passed":not failures,"failures":failures,"production_ready":False}
            conn.execute("UPDATE evaluations SET status='completed',result=? WHERE model_id=?",(json.dumps(result,allow_nan=False),model_id))
            conn.commit()
            return result
        except Exception:
            conn.execute("UPDATE evaluations SET status='failed',result=? WHERE model_id=?",(json.dumps({"message":"Evaluation failed; test reservation retained for audit."}),model_id))
            conn.commit()
            raise
    finally:
        conn.close()


def require_passed_evaluation(model_id):
    *_,identity=_inputs(model_id)
    recorded=evaluation_result(model_id)
    result=recorded.get("result") or {}
    if recorded["status"]!="completed" or not result.get("passed") or result.get("identity_sha256")!=identity:
        raise ValueError("Prepared model promotion requires a passing independent-test evaluation for this exact model.")
