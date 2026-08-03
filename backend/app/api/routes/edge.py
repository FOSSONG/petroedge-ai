from __future__ import annotations

from typing import Any, Literal
import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.edge_runtime import edge_runtime_store
from app.services.edge_petrophysics import EdgePetrophysicalInterpreter, load_dataset
from app.platform_v1.datasets import get_dataset_path
from app.services.edge_temporal import (
    EdgeTemporalInferenceService,
    TemporalModelKind,
    TemporalModelManifest,
    TemporalWorkflow,
    default_manifests,
)

router = APIRouter()
service = EdgeTemporalInferenceService()
_replay_jobs: dict[str, dict[str, Any]] = {}


class TemporalInferenceRequest(BaseModel):
    model_kind: TemporalModelKind = TemporalModelKind.GRU
    workflow: TemporalWorkflow = TemporalWorkflow.DIGITAL_TWIN
    execution_mode: Literal["live", "batch", "replay", "historical"] = "live"
    values: list[list[float]] = Field(min_length=4)
    window_size: int = Field(default=4, ge=4, le=512)


class DeviceCreate(BaseModel):
    device_id: str | None = None
    name: str
    architecture: str = "linux/amd64"
    cpu_cores: int = Field(default=2, ge=1, le=256)
    memory_mb: int = Field(default=1024, ge=256)
    storage_free_mb: int = Field(default=4096, ge=128)
    operating_system: str = "Linux"
    runtime_version: str | None = None
    inference_engines: list[str] = Field(default_factory=lambda: ["numpy"])
    network_state: Literal["connected", "offline", "limited"] = "connected"


class DeviceHeartbeat(BaseModel):
    status: str | None = None
    network_state: str | None = None
    memory_mb: int | None = None
    storage_free_mb: int | None = None


class DeploymentCreate(BaseModel):
    model_id: str | None = None
    version: str = "1.0.0"
    model_kind: TemporalModelKind = TemporalModelKind.GRU
    workflow: TemporalWorkflow = TemporalWorkflow.DIGITAL_TWIN
    runtime: str = "onnxruntime-optional"


class ReplayRequest(BaseModel):
    model_kind: TemporalModelKind = TemporalModelKind.GRU
    workflow: TemporalWorkflow = TemporalWorkflow.DIGITAL_TWIN
    values: list[list[float]] = Field(min_length=4)
    window_size: int = Field(default=16, ge=4, le=512)
    offline: bool = False




class RealTimeReplayRequest(BaseModel):
    dataset_id: str
    model_kind: TemporalModelKind = TemporalModelKind.GRU
    workflow: TemporalWorkflow = TemporalWorkflow.DIGITAL_TWIN
    offline: bool = False
    interval_ms: int = Field(default=250, ge=0, le=5000)


async def _run_realtime_replay(job_id: str, device_id: str, payload: RealTimeReplayRequest) -> None:
    job = _replay_jobs[job_id]
    try:
        frame = load_dataset(get_dataset_path(payload.dataset_id))
        interpreter = EdgePetrophysicalInterpreter(frame)
        job.update(
            status="running",
            total_predictions=int(len(frame)),
            curve_mapping=interpreter.columns,
            runtime="industry-standard-deterministic-petrophysics",
            fallback=False,
            recent_results=[],
            plot_points=[],
        )
        latencies: list[float] = []
        valid_count = 0
        skipped_count = 0
        pay_count = 0
        anomaly_count = 0
        plot_stride = max(1, len(frame) // 1200)
        for index in range(len(frame)):
            try:
                result = interpreter.interpret_row(index)
            except ValueError:
                skipped_count += 1
                job.update(rows_examined=index + 1, skipped_rows=skipped_count)
                continue
            valid_count += 1
            latencies.append(float(result["latency_ms"]))
            pay_count += int(result["pay_zone"])
            anomaly_count += int(result["anomaly"])
            recent = [*job.get("recent_results", []), result][-60:]
            plot_points = job.get("plot_points", [])
            if index % plot_stride == 0 or index == len(frame) - 1:
                plot_points = [*plot_points, {
                    "depth": result["depth"], "gr": result["gr"], "rt": result["rt"],
                    "reservoir_class": result["reservoir_class"], "pay_zone": result["pay_zone"],
                }][-1200:]
            job.update(
                status="running",
                rows_examined=index + 1,
                predictions_completed=valid_count,
                skipped_rows=skipped_count,
                progress_percent=round((index + 1) * 100 / max(len(frame), 1), 1),
                current_depth=result["depth"],
                latest_result=result,
                latest_latency_ms=result["latency_ms"],
                recent_results=recent,
                plot_points=plot_points,
                pay_zone_count=pay_count,
                anomaly_count=anomaly_count,
            )
            if payload.interval_ms > 0:
                await asyncio.sleep(payload.interval_ms / 1000)
            elif index % 100 == 0:
                await asyncio.sleep(0)

        if not valid_count:
            raise ValueError("No valid depth, GR and RT rows were found in the dataset")
        run = {
            "run_id": f"edge-run-{uuid.uuid4().hex[:10]}",
            "device_id": device_id,
            "model_id": "petroedge-deterministic-petrophysics-v1",
            "model_kind": payload.model_kind.value,
            "workflow": payload.workflow.value,
            "status": "queued_for_sync" if payload.offline else "completed",
            "offline": payload.offline,
            "records_processed": int(len(frame)),
            "predictions_generated": valid_count,
            "skipped_rows": skipped_count,
            "average_latency_ms": round(sum(latencies) / len(latencies), 3),
            "runtime": "industry-standard-deterministic-petrophysics",
            "fallback": False,
            "pay_zone_count": pay_count,
            "anomaly_count": anomaly_count,
            "curve_mapping": interpreter.columns,
            "predictions": job.get("recent_results", []),
        }
        # Persist through the existing runtime store without re-running inference.
        state = edge_runtime_store._read()
        from app.services.edge_runtime import utc_now
        run["started_at"] = utc_now()
        run["completed_at"] = utc_now()
        state["runs"].insert(0, run)
        state["runs"] = state["runs"][:100]
        device = next(item for item in state["devices"] if item["device_id"] == device_id)
        device["inference_count"] = int(device.get("inference_count", 0)) + valid_count
        device["average_latency_ms"] = run["average_latency_ms"]
        device["last_seen_at"] = utc_now()
        if payload.offline:
            queue_item = {"queue_id": f"sync-{uuid.uuid4().hex[:10]}", "device_id": device_id, "run_id": run["run_id"], "status": "pending", "created_at": utc_now()}
            state["sync_queue"].append(queue_item)
            device["pending_sync_count"] = int(device.get("pending_sync_count", 0)) + 1
        else:
            device["last_sync_at"] = utc_now()
        edge_runtime_store._write(state)
        job.update(status="completed", progress_percent=100.0, run=run)
    except Exception as exc:
        job.update(status="failed", error=str(exc))


@router.post("/devices/{device_id}/replay/start", status_code=202)
async def start_realtime_edge_replay(device_id: str, payload: RealTimeReplayRequest) -> dict[str, Any]:
    if device_id not in {item["device_id"] for item in edge_runtime_store.list_devices()}:
        raise HTTPException(status_code=404, detail=f"Unknown edge device: {device_id}")
    job_id = f"edge-job-{uuid.uuid4().hex[:10]}"
    _replay_jobs[job_id] = {
        "job_id": job_id,
        "device_id": device_id,
        "status": "queued",
        "predictions_completed": 0,
        "total_predictions": 0,
        "rows_examined": 0,
        "skipped_rows": 0,
        "progress_percent": 0.0,
        "runtime": None,
        "fallback": None,
        "recent_results": [],
        "plot_points": [],
    }
    asyncio.create_task(_run_realtime_replay(job_id, device_id, payload))
    return _replay_jobs[job_id]


@router.get("/replay/jobs/{job_id}")
async def realtime_edge_replay_status(job_id: str) -> dict[str, Any]:
    job = _replay_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown replay job: {job_id}")
    return job


@router.get("/capabilities")
async def edge_capabilities() -> dict[str, Any]:
    return {
        "edge_ready": True,
        "architectures": ["linux/amd64", "linux/arm64"],
        "accelerators": ["CPU", "CUDA", "NVIDIA Jetson/TensorRT profile"],
        "connectors": ["file-replay", "TCP", "UDP", "WebSocket", "MQTT", "REST"],
        "temporal_models": ["GRU", "BiGRU"],
        "policy": {
            "GRU": "causal live, replay, historical and batch inference",
            "BiGRU": "historical, replay and batch inference only",
        },
        "workflows": [workflow.value for workflow in TemporalWorkflow],
        "installed_manifests": [manifest.__dict__ for manifest in default_manifests()],
        "release": "2.2.0",
        "persistence": "data/edge_runtime.json",
    }


@router.get("/dashboard")
async def edge_dashboard() -> dict[str, Any]:
    return edge_runtime_store.dashboard()


@router.get("/devices")
async def edge_devices() -> list[dict[str, Any]]:
    return edge_runtime_store.list_devices()


@router.post("/devices", status_code=201)
async def register_edge_device(payload: DeviceCreate) -> dict[str, Any]:
    try:
        return edge_runtime_store.register_device(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/devices/{device_id}/heartbeat")
async def edge_device_heartbeat(device_id: str, payload: DeviceHeartbeat) -> dict[str, Any]:
    try:
        return edge_runtime_store.heartbeat(device_id, payload.model_dump(exclude_none=True))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown edge device: {device_id}") from exc


@router.post("/devices/{device_id}/deployments", status_code=201)
async def deploy_edge_model(device_id: str, payload: DeploymentCreate) -> dict[str, Any]:
    try:
        return edge_runtime_store.deploy_model(device_id, payload.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown edge device: {device_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/devices/{device_id}/replay")
async def replay_edge_stream(device_id: str, payload: ReplayRequest) -> dict[str, Any]:
    try:
        return edge_runtime_store.replay(
            device_id,
            payload.values,
            model_kind=payload.model_kind,
            workflow=payload.workflow,
            window_size=payload.window_size,
            offline=payload.offline,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown edge device: {device_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/devices/{device_id}/sync")
async def synchronise_edge_device(device_id: str) -> dict[str, Any]:
    try:
        return edge_runtime_store.synchronise(device_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown edge device: {device_id}") from exc


@router.post("/temporal/predict")
async def temporal_predict(payload: TemporalInferenceRequest) -> dict[str, Any]:
    manifest = TemporalModelManifest(
        model_id=f"petroedge-{payload.model_kind.value}-{payload.workflow.value}-demo",
        version="1.0.0-demo",
        kind=payload.model_kind,
        workflow=payload.workflow,
        causal=payload.model_kind == TemporalModelKind.GRU,
        runtime="onnxruntime",
        model_path="gru_live.onnx" if payload.model_kind == TemporalModelKind.GRU else "bigru_replay.onnx",
        window_size=payload.window_size,
    )
    try:
        return service.predict(manifest, payload.values, execution_mode=payload.execution_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
