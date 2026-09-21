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