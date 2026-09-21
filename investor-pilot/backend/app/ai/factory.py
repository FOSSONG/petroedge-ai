from typing import Any
from app.ai.registry import ModelRegistry,registry
class ModelFactory:
    def __init__(self,model_registry:ModelRegistry=registry): self.registry=model_registry
    def create(self,model_key:str,**parameters:Any)->Any:
        self.registry.get_capability(model_key)
        if model_key not in self.registry._adapters: raise RuntimeError(f'No executable adapter installed for {model_key}.')
        return self.registry._adapters[model_key](**parameters)
factory=ModelFactory()