param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$BackendRoot = Join-Path $ProjectRoot 'backend'
$AppRoot = Join-Path $BackendRoot 'app'
if (-not (Test-Path (Join-Path $AppRoot 'main.py'))) { throw 'Run this script from the PetroEdge-AI-v1-demo project root.' }
$Timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot = Join-Path $ProjectRoot "backups\model-registry-$Timestamp"
New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
$modelsRoute = Join-Path $AppRoot 'api\routes\models.py'
if (Test-Path $modelsRoute) {
  $dest = Join-Path $BackupRoot 'backend\app\api\routes\models.py'
  New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
  Copy-Item $modelsRoute $dest -Force
}
function Write-Utf8File([string]$RelativePath,[string]$Content) {
  $Target = Join-Path $ProjectRoot $RelativePath
  New-Item -ItemType Directory -Force -Path (Split-Path $Target) | Out-Null
  [System.IO.File]::WriteAllText($Target,$Content,[System.Text.UTF8Encoding]::new($false))
}
Write-Utf8File 'backend\app\ai\metadata.py' @'
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
class ModelFamily(str, Enum):
    classical_ml='classical_ml'; gradient_boosting='gradient_boosting'; deep_learning='deep_learning'; sequence='sequence'; ensemble='ensemble'
class ModelTask(str, Enum):
    classification='classification'; regression='regression'; forecasting='forecasting'; anomaly_detection='anomaly_detection'; reconstruction='reconstruction'
class ModelCapability(BaseModel):
    model_config=ConfigDict(extra='forbid')
    key:str=Field(pattern=r'^[a-z0-9][a-z0-9_-]*$')
    display_name:str
    family:ModelFamily
    tasks:list[ModelTask]
    framework:str
    installed:bool=True
    trained:bool=False
    supports_cpu:bool=True
    supports_gpu:bool=False
    supports_streaming:bool=False
    causal:bool=True
    edge_ready:bool=False
    onnx_export:bool=False
    description:str
    default_parameters:dict[str,Any]=Field(default_factory=dict)
class ModelArtifact(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str; path:str; suffix:str; framework:str; size_bytes:int; modified_at:str
    registry_metadata:dict[str,Any]=Field(default_factory=dict)
'@
Write-Utf8File 'backend\app\ai\base.py' @'
from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar
from app.ai.metadata import ModelCapability
InputT=TypeVar('InputT'); OutputT=TypeVar('OutputT')
class BaseAIModel(ABC,Generic[InputT,OutputT]):
    capability:ModelCapability
    @abstractmethod
    def train(self,features:InputT,target:Any,**kwargs:Any)->dict[str,Any]: ...
    @abstractmethod
    def predict(self,features:InputT,**kwargs:Any)->OutputT: ...
    @abstractmethod
    def evaluate(self,features:InputT,target:Any,**kwargs:Any)->dict[str,float]: ...
    @abstractmethod
    def save(self,path:Path)->Path: ...
    @classmethod
    @abstractmethod
    def load(cls,path:Path)->'BaseAIModel[Any,Any]': ...
    def export_onnx(self,path:Path,**kwargs:Any)->Path:
        raise NotImplementedError(f'{self.capability.display_name} does not implement ONNX export.')
'@
Write-Utf8File 'backend\app\ai\catalogue.py' @'
from app.ai.metadata import ModelCapability,ModelFamily,ModelTask
BUILTIN_CAPABILITIES=(
ModelCapability(key='random_forest',display_name='Random Forest',family=ModelFamily.classical_ml,tasks=[ModelTask.classification,ModelTask.regression],framework='scikit-learn',edge_ready=True,onnx_export=True,description='Robust tree ensemble for lithology and petrophysical prediction.'),
ModelCapability(key='gradient_boosting',display_name='Gradient Boosting',family=ModelFamily.gradient_boosting,tasks=[ModelTask.classification,ModelTask.regression],framework='scikit-learn',edge_ready=True,onnx_export=True,description='Sequential boosted trees for structured subsurface data.'),
ModelCapability(key='xgboost',display_name='XGBoost',family=ModelFamily.gradient_boosting,tasks=[ModelTask.classification,ModelTask.regression,ModelTask.forecasting],framework='xgboost',supports_gpu=True,edge_ready=True,onnx_export=True,description='Boosted trees for hydrocarbon detection and forecasting.'),
ModelCapability(key='lightgbm',display_name='LightGBM',family=ModelFamily.gradient_boosting,tasks=[ModelTask.classification,ModelTask.regression],framework='lightgbm',supports_gpu=True,edge_ready=True,onnx_export=True,description='Efficient boosting for large well-log datasets.'),
ModelCapability(key='catboost',display_name='CatBoost',family=ModelFamily.gradient_boosting,tasks=[ModelTask.classification,ModelTask.regression],framework='catboost',supports_gpu=True,onnx_export=True,description='Boosting with categorical-feature support.'),
ModelCapability(key='ann',display_name='Artificial Neural Network',family=ModelFamily.deep_learning,tasks=[ModelTask.classification,ModelTask.regression],framework='PyTorch/TensorFlow',supports_gpu=True,edge_ready=True,onnx_export=True,description='Dense neural network for nonlinear petrophysical relationships.'),
ModelCapability(key='cnn',display_name='Convolutional Neural Network',family=ModelFamily.deep_learning,tasks=[ModelTask.classification,ModelTask.reconstruction],framework='PyTorch/TensorFlow',supports_gpu=True,edge_ready=True,onnx_export=True,description='Convolutional architecture for log windows and seismic imagery.'),
ModelCapability(key='lstm',display_name='LSTM',family=ModelFamily.sequence,tasks=[ModelTask.forecasting,ModelTask.reconstruction],framework='PyTorch/TensorFlow',supports_gpu=True,supports_streaming=True,causal=True,edge_ready=True,onnx_export=True,description='Sequence model for temporal forecasting.'),
ModelCapability(key='gru',display_name='GRU',family=ModelFamily.sequence,tasks=[ModelTask.forecasting,ModelTask.classification,ModelTask.anomaly_detection],framework='PyTorch/TensorFlow/ONNX Runtime',supports_gpu=True,supports_streaming=True,causal=True,edge_ready=True,onnx_export=True,description='Causal low-latency sequence model for live and edge inference.'),
ModelCapability(key='bigru',display_name='Bidirectional GRU',family=ModelFamily.sequence,tasks=[ModelTask.classification,ModelTask.reconstruction,ModelTask.forecasting],framework='PyTorch/TensorFlow/ONNX Runtime',supports_gpu=True,supports_streaming=False,causal=False,edge_ready=False,onnx_export=True,description='Bidirectional model for historical replay and contextual interpretation.'),
ModelCapability(key='voting_ensemble',display_name='Voting Ensemble',family=ModelFamily.ensemble,tasks=[ModelTask.classification,ModelTask.regression],framework='PetroEdge ensemble',description='Combines compatible estimators.'),
ModelCapability(key='stacked_ensemble',display_name='Stacked Ensemble',family=ModelFamily.ensemble,tasks=[ModelTask.classification,ModelTask.regression,ModelTask.forecasting],framework='PetroEdge ensemble',description='Out-of-fold stacking with a meta-learner.'),)
'@
Write-Utf8File 'backend\app\ai\registry.py' @'
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
'@
Write-Utf8File 'backend\app\ai\factory.py' @'
from typing import Any
from app.ai.registry import ModelRegistry,registry
class ModelFactory:
    def __init__(self,model_registry:ModelRegistry=registry): self.registry=model_registry
    def create(self,model_key:str,**parameters:Any)->Any:
        self.registry.get_capability(model_key)
        if model_key not in self.registry._adapters: raise RuntimeError(f'No executable adapter installed for {model_key}.')
        return self.registry._adapters[model_key](**parameters)
factory=ModelFactory()
'@
Write-Utf8File 'backend\app\ai\__init__.py' @'
from app.ai.factory import ModelFactory,factory
from app.ai.metadata import ModelArtifact,ModelCapability,ModelFamily,ModelTask
from app.ai.registry import ModelNotFoundError,ModelRegistry,RegistryError,registry
__all__=['ModelArtifact','ModelCapability','ModelFactory','ModelFamily','ModelNotFoundError','ModelRegistry','ModelTask','RegistryError','factory','registry']
'@
Write-Utf8File 'backend\app\ai\models\__init__.py' @'
"""Executable model adapters register from this package."""
'@
Write-Utf8File 'backend\app\api\routes\models.py' @'
from __future__ import annotations
from typing import Any
from fastapi import APIRouter,Depends,HTTPException,Query,status
from app.ai.registry import ModelNotFoundError,registry
from app.core.rbac import require_roles
router=APIRouter(); READ_ROLES=('admin','geoscientist','engineer','viewer')
@router.get('')
async def list_models(family:str|None=Query(default=None),task:str|None=Query(default=None),edge_ready:bool|None=Query(default=None),streaming:bool|None=Query(default=None),_:dict[str,Any]=Depends(require_roles(*READ_ROLES))):
    models=registry.list_capabilities(family=family,task=task,edge_ready=edge_ready,streaming=streaming)
    return {'summary':registry.summary(),'models':[m.model_dump(mode='json') for m in models]}
@router.get('/status')
async def model_status(_:dict[str,Any]=Depends(require_roles(*READ_ROLES))):
    models=registry.list_capabilities(); return {'status':'healthy','registered_models':[m.display_name for m in models],'summary':registry.summary()}
@router.get('/artifacts')
async def list_artifacts(_:dict[str,Any]=Depends(require_roles(*READ_ROLES))):
    artifacts=registry.discover_artifacts(); return {'count':len(artifacts),'artifacts':[a.model_dump(mode='json') for a in artifacts]}
@router.get('/{model_key}')
async def get_model(model_key:str,_:dict[str,Any]=Depends(require_roles(*READ_ROLES))):
    try: return registry.get_capability(model_key).model_dump(mode='json')
    except ModelNotFoundError as exc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=str(exc)) from exc
@router.get('/{model_key}/health')
async def model_health(model_key:str,_:dict[str,Any]=Depends(require_roles(*READ_ROLES))):
    try: capability=registry.get_capability(model_key)
    except ModelNotFoundError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    artifacts=[a for a in registry.discover_artifacts() if a.name==model_key or model_key in a.name.lower()]
    return {'model':model_key,'display_name':capability.display_name,'status':'ready' if artifacts else 'capability_only','artifact_count':len(artifacts),'edge_ready':capability.edge_ready,'supports_streaming':capability.supports_streaming,'causal':capability.causal}
'@
Write-Utf8File 'backend\tests\test_ai_registry.py' @'
from pathlib import Path
import pytest
from app.ai.registry import ModelNotFoundError,ModelRegistry
def test_required_models(tmp_path:Path):
    keys={m.key for m in ModelRegistry(tmp_path).list_capabilities()}
    assert {'random_forest','xgboost','lightgbm','catboost','ann','cnn','lstm','gru','bigru','voting_ensemble','stacked_ensemble'}.issubset(keys)
def test_gru_bigru_semantics(tmp_path:Path):
    registry=ModelRegistry(tmp_path); gru=registry.get_capability('gru'); bigru=registry.get_capability('bigru')
    assert gru.supports_streaming and gru.causal and gru.edge_ready
    assert not bigru.supports_streaming and not bigru.causal
def test_unknown_model(tmp_path:Path):
    with pytest.raises(ModelNotFoundError): ModelRegistry(tmp_path).get_capability('missing')
'@
Write-Host "Model Registry installed. Backup: $BackupRoot" -ForegroundColor Green
Write-Host 'Next: python -m pytest backend\tests\test_ai_registry.py -q' -ForegroundColor Yellow
