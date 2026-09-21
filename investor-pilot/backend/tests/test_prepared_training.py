import hashlib
import json
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest
from app.ml_lifecycle import prepared, service
from app.ml_lifecycle.schemas import TrainingConfig


def config(**kwargs):
    values = dict(display_name="Test model", dataset_id="prepared:test", algorithm="random_forest",
                  task_type="regression", target_column="target_value", feature_columns=["x"],
                  validation_strategy="grouped", group_column="split_group_id", hyperparameters={"n_estimators": 3})
    return TrainingConfig(**(values | kwargs))


@pytest.fixture
def approved(tmp_path, monkeypatch):
    frame = pd.DataFrame({"specimen_id": [f"s{i}" for i in range(30)],
                          "split_group_id": ["parent1"]*10+["parent2"]*10+["parent3"]*10,
                          "x": np.arange(30,dtype=float), "target_value": np.arange(30,dtype=float)*2,
                          "condition": ["20bar"]*30})
    path = tmp_path / "data.csv"; frame.to_csv(path,index=False)
    assignments = dict(zip(frame.specimen_id, ["train"]*10+["validation"]*10+["test"]*10))
    item = dict(name="Fixture", rows=30, path="data.csv", sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                target_definition="fixture", condition="20bar", target_column="target_value", task_type="regression",
                feature_columns=["x"], quality_approved=True, assignments=assignments, constant_columns={"condition":"20bar"})
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"datasets":{"prepared:test":item}}))
    monkeypatch.setenv("PETROEDGE_PREPARED_CATALOG",str(catalog))
    return frame, item, catalog


def test_group_leakage_is_rejected(approved):
    frame, item, _ = approved
    item["assignments"]["s0"]="test"
    with pytest.raises(ValueError,match="Parent-well leakage"):
        prepared.locked_partitions(frame,item["assignments"])


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "null", "empty_test"])
def test_invalid_assignments(approved, change):
    frame,item,_=approved; assignments=item["assignments"]
    if change=="missing": del assignments["s0"]
    if change=="extra": assignments["unknown"]="train"
    if change=="duplicate": frame.loc[1,"specimen_id"]="s0"
    if change=="null": frame.loc[0,"split_group_id"]=None
    if change=="empty_test": assignments={k:("validation" if v=="test" else v) for k,v in assignments.items()}
    with pytest.raises(ValueError): prepared.locked_partitions(frame, assignments)


def test_tamper_and_path_escape(approved):
    _,item,catalog=approved
    path=catalog.parent/'data.csv'; path.write_text(path.read_text()+'\n')
    with pytest.raises(ValueError,match="checksum"): prepared.load_prepared(config())
    item['path']='../outside.csv';catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    with pytest.raises(ValueError,match="outside"): prepared.load_prepared(config())


def test_feature_and_condition_contract(approved):
    _,item,catalog=approved
    with pytest.raises(ValueError,match="feature order"): prepared.load_prepared(config(feature_columns=['condition']))
    with pytest.raises(ValueError,match="grouped"): prepared.load_prepared(config(validation_strategy='random',group_column=None))
    item['constant_columns']['condition']='other';catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    with pytest.raises(ValueError,match="conditions"): prepared.load_prepared(config())


def test_quality_gate_before_fit(approved, monkeypatch):
    _,item,catalog=approved;item['quality_approved']=False
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    monkeypatch.setattr(service,'_build_estimator',lambda _:pytest.fail('must not construct estimator'))
    with pytest.raises(ValueError,match="blocked"): service.train_and_register(config())


def test_uploaded_qualified_data_cannot_bypass_contract(approved,monkeypatch):
    frame,_,_=approved;monkeypatch.setattr(service,'_load_dataset',lambda _:frame)
    with pytest.raises(ValueError,match="server-approved"):
        service.train_and_register(config(dataset_id='uploaded'))


def test_test_partition_never_used_for_fit_or_metrics(approved,monkeypatch,tmp_path):
    monkeypatch.setattr(service,'BACKEND_ROOT',tmp_path)
    monkeypatch.setattr(service,'STORE_ROOT',tmp_path/'models')
    monkeypatch.setattr(service,'REGISTRY_PATH',tmp_path/'models/registry.json')
    seen=[]; original=service._metrics
    def metrics(y,p,t):
        seen.extend(y.tolist()); return original(y,p,t)
    monkeypatch.setattr(service,'_metrics',metrics)
    result=service.train_and_register(config())
    manifest=service.get_model(result.model_id)
    assert result.training_rows==10 and result.validation_rows==10
    assert manifest['independent_test_rows']==10
    assert manifest['independent_test_status']=='reserved_not_evaluated'
    assert max(seen)<40
    model=service.joblib.load(tmp_path/manifest['artefact_path'])
    assert model.named_steps['imputer'].statistics_[0]==4.5
    assert model.named_steps['estimator'].estimators_[0].tree_.n_node_samples[0]<=10
    with pytest.raises(ValueError,match="promotion"):
        service.update_stage(result.model_id,service.ModelStage.production)


def test_grouped_ann_cannot_randomly_early_stop():
    with pytest.raises(ValueError,match="early stopping"):
        service._build_estimator(config(algorithm='ann',hyperparameters={'early_stopping':True}))


def test_catalog_response_has_no_filesystem_paths(approved):
    entries=prepared.entries()
    assert entries[0]['dataset_id']=='prepared:test'
    assert 'path' not in entries[0] and 'assignments' not in entries[0]


def test_prepared_api_authentication_and_blocked_training(approved):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import training_lifecycle as routes
    _,item,catalog=approved
    item['quality_approved']=False
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    app=FastAPI(); app.include_router(routes.router)
    client=TestClient(app)
    assert client.get('/prepared-datasets').status_code in (401,403)
    app.dependency_overrides[routes.WRITE]=lambda: {'role':'engineer'}
    response=client.get('/prepared-datasets')
    assert response.status_code==200
    assert response.json()['datasets'][0]['status']=='blocked'
    response=client.post('/train',json=config().model_dump(mode='json'))
    assert response.status_code==422 and 'blocked' in response.json()['detail']


@pytest.fixture
def evaluatable(approved, monkeypatch, tmp_path):
    frame,item,catalog=approved
    item['evaluation_policy']={'policy_id':'synthetic-test-only','minimum_test_rows':5,'minimum_test_groups':1,'criteria':{'mae':{'max':1000.0}}}
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    monkeypatch.setattr(service,'BACKEND_ROOT',tmp_path)
    monkeypatch.setattr(service,'STORE_ROOT',tmp_path/'models')
    monkeypatch.setattr(service,'REGISTRY_PATH',tmp_path/'models/registry.json')
    result=service.train_and_register(config())
    return result, item, catalog


def test_evaluation_is_idempotent_and_validation_is_gated(evaluatable,monkeypatch):
    from app.ml_lifecycle import evaluation as ev
    model,_,_=evaluatable
    with pytest.raises(ValueError,match='promotion'):
        service.update_stage(model.model_id,service.ModelStage.validated)
    result=ev.evaluate_once(model.model_id,'admin-test')
    assert result['passed'] and result['test_rows']==10 and result['actor']=='admin-test'
    monkeypatch.setattr(ev.joblib,'load',lambda _:pytest.fail('must not rerun inference'))
    assert ev.evaluate_once(model.model_id,'another-admin')==result
    assert service.update_stage(model.model_id,service.ModelStage.validated)['stage']=='validated'
    with pytest.raises(ValueError,match='operational'):
        service.update_stage(model.model_id,service.ModelStage.production)


def test_failed_threshold_blocks_validation(evaluatable):
    from app.ml_lifecycle import evaluation as ev
    _,item,catalog=evaluatable
    item['evaluation_policy']['criteria']['mae']['max']=0
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    candidate=service.train_and_register(config())
    result=ev.evaluate_once(candidate.model_id,'admin-test')
    assert not result['passed'] and result['failures']==['mae above maximum']
    with pytest.raises(ValueError,match='passing'):
        service.update_stage(candidate.model_id,service.ModelStage.validated)


def test_delete_does_not_release_test_specimens(evaluatable):
    from app.ml_lifecycle import evaluation as ev
    model,_,_=evaluatable
    ev.evaluate_once(model.model_id,'admin-test')
    service.delete_model(model.model_id)
    replacement=service.train_and_register(config())
    with pytest.raises(ValueError,match='another candidate'):
        ev.evaluate_once(replacement.model_id,'admin-test')


def test_partial_test_overlap_also_blocked(evaluatable):
    from app.ml_lifecycle import evaluation as ev
    model,item,catalog=evaluatable
    ev.evaluate_once(model.model_id,'admin-test')
    # Same data with a new test group added still overlaps the consumed group.
    for i in range(10,15): item['assignments']['s'+str(i)]='test'
    frame=pd.read_csv(catalog.parent/'data.csv');frame.loc[10:14,'split_group_id']='parent4'
    frame.to_csv(catalog.parent/'data.csv',index=False)
    item['sha256']=hashlib.sha256((catalog.parent/'data.csv').read_bytes()).hexdigest()
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    replacement=service.train_and_register(config())
    with pytest.raises(ValueError,match='another candidate'):
        ev.evaluate_once(replacement.model_id,'admin-test')


@pytest.mark.parametrize('change',['artifact','contract','configuration'])
def test_evaluation_refuses_changed_identity(evaluatable,change):
    from app.ml_lifecycle import evaluation as ev
    model,item,catalog=evaluatable;manifest=service.get_model(model.model_id)
    if change=='artifact':
        path=service.BACKEND_ROOT/manifest['artefact_path'];path.write_bytes(path.read_bytes()+b'x')
    elif change=='configuration':
        path=service.BACKEND_ROOT/manifest['configuration_path'];payload=json.loads(path.read_text());payload['random_seed']=7;path.write_text(json.dumps(payload))
    else:
        item['evaluation_policy']['criteria']['mae']['max']=1
        catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    with pytest.raises(ValueError,match='checksum|changed'):
        ev.evaluate_once(model.model_id,'admin-test')


def test_inference_failure_retains_reservation(evaluatable,monkeypatch):
    from app.ml_lifecycle import evaluation as ev
    model,_,_=evaluatable
    monkeypatch.setattr(ev.joblib,'load',lambda _: (_ for _ in ()).throw(RuntimeError('fixture failure')))
    with pytest.raises(RuntimeError):ev.evaluate_once(model.model_id,'admin-test')
    assert ev.evaluation_result(model.model_id)['status']=='failed'
    with pytest.raises(ValueError,match='failed'):ev.evaluate_once(model.model_id,'admin-test')
    other=service.train_and_register(config())
    with pytest.raises(ValueError,match='another candidate'):ev.evaluate_once(other.model_id,'admin-test')


def test_policy_is_required_before_training(approved,monkeypatch,tmp_path):
    from app.ml_lifecycle import evaluation as ev
    monkeypatch.setattr(service,'BACKEND_ROOT',tmp_path);monkeypatch.setattr(service,'STORE_ROOT',tmp_path/'models');monkeypatch.setattr(service,'REGISTRY_PATH',tmp_path/'models/registry.json')
    model=service.train_and_register(config())
    with pytest.raises(ValueError,match='policy'):ev.evaluate_once(model.model_id,'admin-test')


def test_evaluation_api_is_admin_only(evaluatable):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.routes import training_lifecycle as routes
    from app.core.security import get_current_user
    model,_,_=evaluatable
    app=FastAPI();app.include_router(routes.router);client=TestClient(app)
    url='/registry/'+model.model_id+'/independent-evaluation'
    assert client.post(url).status_code in (401,403)
    app.dependency_overrides[get_current_user]=lambda:{'sub':'engineer1','roles':['engineer']}
    assert client.post(url).status_code==403
    app.dependency_overrides[get_current_user]=lambda:{'sub':'admin1','roles':['admin']}
    assert client.get(url).json()['policy']['policy_id']=='synthetic-test-only'
    result=client.post(url)
    assert result.status_code==200 and result.json()['actor']=='admin1'
    assert client.get(url).json()['status']=='completed'


def test_concurrent_candidates_cannot_share_test(evaluatable,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from app.ml_lifecycle import evaluation as ev
    first,_,_=evaluatable;second=service.train_and_register(config())
    entered=Event();release=Event();original=ev.joblib.load
    class WaitingModel:
        def __init__(self,stream):self.model=original(stream)
        def predict(self,x):
            entered.set()
            assert release.wait(10)
            return self.model.predict(x)
    monkeypatch.setattr(ev.joblib,'load',WaitingModel)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future=pool.submit(ev.evaluate_once,first.model_id,'admin1')
        try:
            assert entered.wait(10)
            with pytest.raises(ValueError,match='another candidate'):
                ev.evaluate_once(second.model_id,'admin2')
        finally: release.set()
        assert future.result()['passed']


def test_prepared_values_do_not_receive_legacy_sentinel_rewrites(approved,monkeypatch,tmp_path):
    frame,item,catalog=approved
    frame.loc[:9,'x']=9999.0
    path=catalog.parent/'data.csv';frame.to_csv(path,index=False)
    item['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    catalog.write_text(json.dumps({'datasets':{'prepared:test':item}}))
    monkeypatch.setattr(service,'BACKEND_ROOT',tmp_path);monkeypatch.setattr(service,'STORE_ROOT',tmp_path/'models');monkeypatch.setattr(service,'REGISTRY_PATH',tmp_path/'models/registry.json')
    result=service.train_and_register(config())
    model=service.joblib.load(tmp_path/result.artefact_path)
    assert model.named_steps['imputer'].statistics_[0]==9999.0
