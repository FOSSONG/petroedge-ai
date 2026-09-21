from __future__ import annotations

import json
import platform
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from app.services.edge_temporal import (
    EdgeTemporalInferenceService,
    TemporalModelKind,
    TemporalModelManifest,
    TemporalWorkflow,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EdgeRuntimeStore:
    """Small, durable JSON store for the MVP edge-control plane.

    The store is deliberately dependency-light so Release 2 remains CPU-first,
    Docker-friendly and usable on systems with constrained local storage.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path("data/edge_runtime.json")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.inference = EdgeTemporalInferenceService()
        if not self.path.exists():
            self._write(self._initial_state())

    @staticmethod
    def _initial_state() -> dict[str, Any]:
        now = utc_now()
        return {
            "devices": [
                {
                    "device_id": "edge-demo-01",
                    "name": "Rig-site Simulator",
                    "status": "online",
                    "architecture": "linux/amd64",
                    "cpu_cores": 4,
                    "memory_mb": 2048,
                    "storage_free_mb": 8192,
                    "operating_system": "Docker Linux",
                    "runtime_version": platform.python_version(),
                    "inference_engines": ["numpy", "onnxruntime-optional"],
                    "network_state": "connected",
                    "deployed_model_id": None,
                    "model_version": None,
                    "inference_count": 0,
                    "average_latency_ms": 0.0,
                    "pending_sync_count": 0,
                    "last_seen_at": now,
                    "last_sync_at": None,
                    "created_at": now,
                }
            ],
            "deployments": [],
            "runs": [],
            "sync_queue": [],
        }

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                state = self._initial_state()
                self._write(state)
                return state

    def _write(self, state: dict[str, Any]) -> None:
        with self._lock:
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            temporary.replace(self.path)

    def list_devices(self) -> list[dict[str, Any]]:
        return self._read()["devices"]

    def register_device(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = self._read()
        device_id = str(payload.get("device_id") or f"edge-{uuid.uuid4().hex[:8]}")
        if any(item["device_id"] == device_id for item in state["devices"]):
            raise ValueError(f"Device {device_id!r} already exists")
        now = utc_now()
        device = {
            "device_id": device_id,
            "name": str(payload.get("name") or device_id),
            "status": "online",
            "architecture": str(payload.get("architecture") or "linux/amd64"),
            "cpu_cores": int(payload.get("cpu_cores") or 2),
            "memory_mb": int(payload.get("memory_mb") or 1024),
            "storage_free_mb": int(payload.get("storage_free_mb") or 4096),
            "operating_system": str(payload.get("operating_system") or "Linux"),
            "runtime_version": str(payload.get("runtime_version") or platform.python_version()),
            "inference_engines": list(payload.get("inference_engines") or ["numpy"]),
            "network_state": str(payload.get("network_state") or "connected"),
            "deployed_model_id": None,
            "model_version": None,
            "inference_count": 0,
            "average_latency_ms": 0.0,
            "pending_sync_count": 0,
            "last_seen_at": now,
            "last_sync_at": None,
            "created_at": now,
        }
        state["devices"].append(device)
        self._write(state)
        return device

    def heartbeat(self, device_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
        state = self._read()
        device = next((item for item in state["devices"] if item["device_id"] == device_id), None)
        if device is None:
            raise KeyError(device_id)
        device.update({key: value for key, value in metrics.items() if value is not None})
        device["status"] = "online"
        device["last_seen_at"] = utc_now()
        self._write(state)
        return device

    def deploy_model(self, device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        state = self._read()
        device = next((item for item in state["devices"] if item["device_id"] == device_id), None)
        if device is None:
            raise KeyError(device_id)
        kind = TemporalModelKind(str(payload.get("model_kind", "gru")).lower())
        workflow = TemporalWorkflow(str(payload.get("workflow", TemporalWorkflow.DIGITAL_TWIN.value)))
        model_id = str(payload.get("model_id") or f"petroedge-{kind.value}-{workflow.value}")
        version = str(payload.get("version") or "1.0.0")
        deployment = {
            "deployment_id": f"deploy-{uuid.uuid4().hex[:10]}",
            "device_id": device_id,
            "model_id": model_id,
            "version": version,
            "model_kind": kind.value,
            "workflow": workflow.value,
            "runtime": str(payload.get("runtime") or "onnxruntime-optional"),
            "status": "deployed",
            "deployed_at": utc_now(),
        }
        state["deployments"].append(deployment)
        device["deployed_model_id"] = model_id
        device["model_version"] = version
        self._write(state)
        return deployment

    def replay(
        self,
        device_id: str,
        values: Sequence[Sequence[float]],
        *,
        model_kind: TemporalModelKind,
        workflow: TemporalWorkflow,
        window_size: int,
        offline: bool,
    ) -> dict[str, Any]:
        state = self._read()
        device = next((item for item in state["devices"] if item["device_id"] == device_id), None)
        if device is None:
            raise KeyError(device_id)
        manifest = TemporalModelManifest(
            model_id=device.get("deployed_model_id") or f"petroedge-{model_kind.value}-{workflow.value}-baseline",
            version=device.get("model_version") or "1.0.0-baseline",
            kind=model_kind,
            workflow=workflow,
            causal=model_kind == TemporalModelKind.GRU,
            runtime="onnxruntime",
            model_path="gru_live.onnx" if model_kind == TemporalModelKind.GRU else "bigru_replay.onnx",
            window_size=window_size,
        )
        step = max(1, window_size // 4)
        predictions: list[dict[str, Any]] = []
        for end in range(window_size, len(values) + 1, step):
            result = self.inference.predict(
                manifest,
                values[:end],
                execution_mode="replay" if model_kind == TemporalModelKind.BIGRU else "live",
            )
            predictions.append({"sequence_end": end, **result})
        if not predictions:
            raise ValueError(f"At least {window_size} valid rows are required")

        latencies = [float(item["latency_ms"]) for item in predictions]
        run = {
            "run_id": f"edge-run-{uuid.uuid4().hex[:10]}",
            "device_id": device_id,
            "model_id": manifest.model_id,
            "model_kind": model_kind.value,
            "workflow": workflow.value,
            "status": "queued_for_sync" if offline else "completed",
            "offline": offline,
            "records_processed": len(values),
            "predictions_generated": len(predictions),
            "average_latency_ms": round(sum(latencies) / len(latencies), 3),
            "latest_score": predictions[-1]["score"],
            "latest_confidence": predictions[-1]["confidence"],
            "runtime": predictions[-1]["runtime"],
            "fallback": predictions[-1]["fallback"],
            "started_at": utc_now(),
            "completed_at": utc_now(),
            "predictions": predictions[-50:],
        }
        state["runs"].insert(0, run)
        state["runs"] = state["runs"][:100]
        previous_count = int(device.get("inference_count", 0))
        previous_average = float(device.get("average_latency_ms", 0.0))
        new_count = previous_count + len(predictions)
        device["inference_count"] = new_count
        device["average_latency_ms"] = round(
            ((previous_average * previous_count) + sum(latencies)) / max(new_count, 1), 3
        )
        device["last_seen_at"] = utc_now()
        if offline:
            queue_item = {
                "queue_id": f"sync-{uuid.uuid4().hex[:10]}",
                "device_id": device_id,
                "run_id": run["run_id"],
                "status": "pending",
                "created_at": utc_now(),
            }
            state["sync_queue"].append(queue_item)
            device["pending_sync_count"] = int(device.get("pending_sync_count", 0)) + 1
        else:
            device["last_sync_at"] = utc_now()
        self._write(state)
        return run

    def synchronise(self, device_id: str) -> dict[str, Any]:
        state = self._read()
        device = next((item for item in state["devices"] if item["device_id"] == device_id), None)
        if device is None:
            raise KeyError(device_id)
        synced = 0
        now = utc_now()
        for item in state["sync_queue"]:
            if item["device_id"] == device_id and item["status"] == "pending":
                item["status"] = "synced"
                item["synced_at"] = now
                synced += 1
        for run in state["runs"]:
            if run["device_id"] == device_id and run["status"] == "queued_for_sync":
                run["status"] = "completed"
        device["pending_sync_count"] = 0
        device["last_sync_at"] = now
        device["network_state"] = "connected"
        self._write(state)
        return {"device_id": device_id, "synced_items": synced, "last_sync_at": now}

    def dashboard(self) -> dict[str, Any]:
        state = self._read()
        devices = state["devices"]
        runs = state["runs"]
        total_predictions = sum(int(item.get("predictions_generated", 0)) for item in runs)
        return {
            "summary": {
                "registered_devices": len(devices),
                "online_devices": sum(item.get("status") == "online" for item in devices),
                "deployed_models": sum(bool(item.get("deployed_model_id")) for item in devices),
                "total_inferences": total_predictions,
                "pending_sync_items": sum(item.get("status") == "pending" for item in state["sync_queue"]),
                "average_latency_ms": round(
                    sum(float(item.get("average_latency_ms", 0.0)) for item in devices) / max(len(devices), 1), 3
                ),
            },
            "devices": devices,
            "deployments": state["deployments"][-20:][::-1],
            "recent_runs": runs[:20],
        }


edge_runtime_store = EdgeRuntimeStore()
