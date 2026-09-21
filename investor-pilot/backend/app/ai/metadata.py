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