from __future__ import annotations
import json,threading
from datetime import datetime,timezone
from pathlib import Path
from typing import Any,Iterable
from app.ai.catalogue import BUILTIN_CAPABILITIES
from app.ai.metadata import ModelArtifact,ModelCapability
class RegistryError(RuntimeError): pass
class ModelNotFoundError(RegistryError): pass
class ModelRegistry:
    SUPPORTED_SUFFIXES={'.pkl','.joblib','.onnx','.pt','.pth','.keras','.h5'}
    def __init__(self,backend_root:Path):
        self.backend_root=backend_root.resolve(); self.model_root=self.backend_root/'models'; self._lock=threading.RLock(); self._capabilities={}; self._adapters={}; self.register_capabilities(BUILTIN_CAPABILITIES)
    def register_capability(self,capability:ModelCapability,replace:bool=False):
        with self._lock:
            if capability.key in self._capabilities and not replace: raise RegistryError(f'Model capability already registered: {capability.key}')
            self._capabilities[capability.key]=capability
    def register_capabilities(self,capabilities:Iterable[ModelCapability]):
        for capability in capabilities: self.register_capability(capability,replace=True)
    def get_capability(self,key:str)->ModelCapability:
        if key not in self._capabilities: raise ModelNotFoundError(f'Model capability not found: {key}')
        return self._capabilities[key]
    def list_capabilities(self,family:str|None=None,task:str|None=None,edge_ready:bool|None=None,streaming:bool|None=None):
        models=list(self._capabilities.values())
        if family: models=[m for m in models if m.family.value==family]
        if task: models=[m for m in models if task in {t.value for t in m.tasks}]
        if edge_ready is not None: models=[m for m in models if m.edge_ready is edge_ready]
        if streaming is not None: models=[m for m in models if m.supports_streaming is streaming]
        return sorted(models,key=lambda m:(m.family.value,m.display_name.lower()))
    def discover_artifacts(self):
        payload=self._load_registry_json(); artifacts=[]
        if not self.model_root.exists(): return artifacts
        for path in sorted(self.model_root.rglob('*')):
            if not path.is_file() or path.suffix.lower() not in self.SUPPORTED_SUFFIXES: continue
            stat=path.stat(); meta=payload.get(path.stem,{})
            artifacts.append(ModelArtifact(name=path.stem,path=str(path.relative_to(self.backend_root)),suffix=path.suffix.lower(),framework=self._framework(path.suffix),size_bytes=stat.st_size,modified_at=datetime.fromtimestamp(stat.st_mtime,tz=timezone.utc).isoformat(),registry_metadata=meta if isinstance(meta,dict) else {}))
        return artifacts
    def summary(self):
        caps=self.list_capabilities(); arts=self.discover_artifacts()
        return {'capability_count':len(caps),'artifact_count':len(arts),'edge_ready_count':sum(m.edge_ready for m in caps),'streaming_count':sum(m.supports_streaming for m in caps),'adapter_count':len(self._adapters),'families':sorted({m.family.value for m in caps})}
    def _load_registry_json(self):
        for path in (self.model_root/'registry.json',self.backend_root/'data'/'models'/'registry.json'):
            if path.exists():
                try:
                    payload=json.loads(path.read_text(encoding='utf-8'))
                    if isinstance(payload,dict): return payload
                except (OSError,json.JSONDecodeError): pass
        return {}
    @staticmethod
    def _framework(suffix): return {'.pkl':'scikit-learn/joblib','.joblib':'scikit-learn/joblib','.onnx':'onnxruntime','.pt':'pytorch','.pth':'pytorch','.keras':'tensorflow/keras','.h5':'tensorflow/keras'}.get(suffix.lower(),'unknown')
registry=ModelRegistry(Path(__file__).resolve().parents[2])