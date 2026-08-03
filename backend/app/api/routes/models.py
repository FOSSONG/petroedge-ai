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
# ----------------------------------------------------------------------
# Backwards compatibility for older tests and integrations
# ----------------------------------------------------------------------

def _discover_models():
    """
    Legacy compatibility wrapper.
    """
    return registry.list_capabilities()
