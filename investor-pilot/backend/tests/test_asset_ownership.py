import io
import json
from contextlib import contextmanager
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.core.ownership import principal, OwnershipContextMiddleware
from app.core.security import get_current_user
from app.platform_v1 import database, datasets
from app.ml_lifecycle import service

ALICE={"user_id":"alice-id","username":"alice@example.test","roles":["engineer"]}
BOB={"user_id":"bob-id","username":"bob@example.test","roles":["engineer"]}
ADMIN={"user_id":"admin-id","username":"admin@example.test","roles":["admin"]}

@contextmanager
def acting(user):
    token=principal.set(user)
    try:yield
    finally:principal.reset(token)

@pytest.fixture
def assets(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);database.initialise()
    monkeypatch.setattr(service,'BACKEND_ROOT',tmp_path)
    monkeypatch.setattr(service,'STORE_ROOT',tmp_path/'models')
    monkeypatch.setattr(service,'REGISTRY_PATH',tmp_path/'models/registry.json')
    csv=b'x,y\n'+b''.join(f'{i},{i*2}\n'.encode() for i in range(30))
    with acting(ALICE):a=datasets.register_upload('Alice',None,'a.csv',io.BytesIO(csv),'spoofed')
    with acting(BOB):b=datasets.register_upload('Bob',None,'b.csv',io.BytesIO(csv),None)
    with acting(None):legacy=datasets.register_upload('Legacy',None,'legacy.csv',io.BytesIO(csv),None)
    service.STORE_ROOT.mkdir()
    registry={}
    for key,owner in [('alice-model','alice-id'),('bob-model','bob-id'),('legacy-model',None)]:
        folder=service.STORE_ROOT/key;folder.mkdir()
        registry[key]={'model_id':key,'owner_id':owner,'display_name':key,'version':1,'stage':'candidate','task_type':'regression','target_column':'y','created_at':'now','manifest_path':str((folder/'manifest.json').relative_to(tmp_path))}
    service._write_registry(registry)
    from app.api.routes import platform,training_lifecycle
    app=FastAPI();app.include_router(platform.router);app.include_router(training_lifecycle.router,prefix='/training')
    app.add_middleware(OwnershipContextMiddleware)
    user={'value':ALICE}
    app.dependency_overrides[get_current_user]=lambda:user['value']
    return a,b,legacy,TestClient(app),user


def test_upload_owner_uses_authenticated_user_id(assets):
    a,_,_,client,_=assets
    assert a.owner_id=='alice-id'
    r=client.post('/platform/datasets',data={'name':'New'},files={'file':('new.csv',b'x,y\n1,2\n','text/csv')})
    assert r.status_code==201 and r.json()['owner_id']=='alice-id'


@pytest.mark.parametrize('suffix',['','/preview','/quality','/download','/lineage'])
def test_dataset_reads_are_private(assets,suffix):
    a,b,legacy,client,user=assets
    assert client.get('/platform/datasets/'+a.dataset_id+suffix).status_code==200
    assert client.get('/platform/datasets/'+b.dataset_id+suffix).status_code==404
    assert client.get('/platform/datasets/'+legacy.dataset_id+suffix).status_code==404
    user['value']=ADMIN
    assert client.get('/platform/datasets/'+legacy.dataset_id+suffix).status_code==200


@pytest.mark.parametrize('suffix',['/prepare','/edit','/process-las'])
def test_foreign_dataset_mutations_are_blocked(assets,suffix):
    _,b,_,client,_=assets
    response=client.post('/platform/datasets/'+b.dataset_id+suffix,json={})
    assert response.status_code==404


def test_listing_overview_and_deletion_scope(assets):
    a,b,_,client,_=assets
    assert [r['dataset_id'] for r in client.get('/platform/datasets').json()]==[a.dataset_id]
    assert client.get('/platform/overview').json()['datasets']==1
    assert client.delete('/platform/datasets/'+b.dataset_id).status_code==404
    assert client.get('/platform/datasets/'+a.dataset_id).status_code==200


def test_lifecycle_foreign_reads_mutations_and_training_blocked(assets):
    a,b,_,client,_=assets
    assert [m['model_id'] for m in client.get('/training/registry').json()['models']]==['alice-model']
    assert client.get('/training/registry/bob-model').status_code==404
    assert client.delete('/training/registry/bob-model').status_code==404
    assert client.patch('/training/registry/bob-model/stage',json={'stage':'validated'}).status_code==404
    assert client.post('/training/registry/bob-model/retrain',json={}).status_code==404
    payload={'display_name':'test','dataset_id':b.dataset_id,'algorithm':'random_forest','task_type':'regression','target_column':'y','feature_columns':['x']}
    assert client.post('/training/train',json=payload).status_code==404
    assert client.post('/training/predict',json={'model_id':'bob-model','dataset_id':a.dataset_id}).status_code==404
    assert client.post('/training/predict',json={'model_id':'alice-model','dataset_id':b.dataset_id}).status_code==404


def test_new_model_owned_and_predictions_private(assets):
    a,_,_,client,user=assets
    payload={'display_name':'owned','dataset_id':a.dataset_id,'algorithm':'random_forest','task_type':'regression','target_column':'y','feature_columns':['x'],'hyperparameters':{'n_estimators':3}}
    response=client.post('/training/train',json=payload);assert response.status_code==200,response.text
    mid=response.json()['model_id']
    assert client.get('/training/registry/'+mid).json()['owner_id']=='alice-id'
    result=client.post('/training/predict',json={'model_id':mid,'dataset_id':a.dataset_id});assert result.status_code==200,result.text
    name=result.json()['output_path'].split('/')[-1]
    url='/training/predictions/'+name+'/download'
    assert client.get(url).status_code==200
    user['value']=BOB;assert client.get(url).status_code==404
    user['value']=ADMIN;assert client.get(url).status_code==200


def test_direct_service_paths_and_reports_cannot_bypass_owner(assets):
    _,b,_,_,_=assets
    with acting(ALICE):
        with pytest.raises(HTTPException):datasets.get_dataset_path(b.dataset_id)
        with pytest.raises(HTTPException):datasets.delete_dataset(b.dataset_id)
        with pytest.raises(HTTPException):service.get_model('bob-model')
        from app.services.report_service import ReportSourceLoader
        with pytest.raises(HTTPException):ReportSourceLoader()._load_dataset(b.dataset_id)
    with acting({}):
        with pytest.raises(HTTPException):datasets.get_dataset(b.dataset_id)


def test_request_context_does_not_leak_between_requests(assets):
    a,b,_,client,user=assets
    user['value']=ALICE;assert client.get('/platform/datasets/'+a.dataset_id).status_code==200
    user['value']=BOB;assert client.get('/platform/datasets/'+a.dataset_id).status_code==404
    assert client.get('/platform/datasets/'+b.dataset_id).status_code==200
    assert principal.get() is None


def test_experiment_checks_source_before_dispatch(assets,monkeypatch):
    from app.platform_v1 import experiments
    from app.platform_v1.schemas import ExperimentCreate
    _,b,_,_,_=assets
    monkeypatch.setattr(experiments._EXECUTOR,'submit',lambda *args:pytest.fail('foreign job must not be dispatched'))
    with acting(ALICE):
        with pytest.raises(HTTPException):
            experiments.create_experiment(ExperimentCreate(name='test',task='regression',dataset_id=b.dataset_id,algorithm='random_forest'),None)


def test_experiment_background_job_keeps_request_owner(assets,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.platform_v1 import experiments
    from app.platform_v1.schemas import ExperimentCreate
    from app.core.ownership import owner_id
    a,b,_,_,_=assets
    captured=[]
    monkeypatch.setattr(experiments._EXECUTOR,'submit',lambda *args:captured.append(args))
    def fake_train(*args):
        assert owner_id()=='alice-id'
        with pytest.raises(HTTPException):datasets.get_dataset_path(b.dataset_id)
    monkeypatch.setattr(experiments,'_train',fake_train)
    with acting(ALICE):
        record=experiments.create_experiment(ExperimentCreate(name='test',task='regression',dataset_id=a.dataset_id,algorithm='random_forest'),None)
        assert record.owner_id=='alice-id'
    with ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(captured[0][0],*captured[0][1:]).result(timeout=5)
    with acting(BOB):
        assert experiments.list_experiments()==[]
        with pytest.raises(HTTPException):experiments.get_experiment(record.experiment_id)
