import json
from uuid import uuid4
import pandas as pd
import pytest
from fastapi import FastAPI,HTTPException
from fastapi.testclient import TestClient
from app.core.security import get_current_user
from app.core.ownership import OwnershipContextMiddleware
from app.services import report_service as service
from app.api.routes import reports,upload,dashboard
from test_asset_ownership import acting,ALICE,BOB,ADMIN

@pytest.fixture
def reports_api(tmp_path,monkeypatch):
    root=tmp_path/'reports';root.mkdir()
    monkeypatch.setattr(service,'REPORT_ROOT',root);monkeypatch.setattr(reports,'REPORT_ROOT',root)
    monkeypatch.setattr(service,'_report_service',None)
    ids=[]
    for owner in ['alice-id','bob-id',None]:
        rid=str(uuid4());folder=root/rid;folder.mkdir();ids.append(rid)
        (folder/'metadata.json').write_text(json.dumps({'report_id':rid,'owner_id':owner,'title':'Private','created_at':'now','metadata':{'owner_id':'alice-id'}}))
        (folder/'report.html').write_text('<p>Private result</p>')
        (folder/'report.csv').write_text('x\n1\n')
    app=FastAPI();app.include_router(reports.router,prefix='/reports');app.include_router(upload.router,prefix='/legacy');app.include_router(dashboard.router,prefix='/dashboard');app.add_middleware(OwnershipContextMiddleware)
    return ids,TestClient(app),app,root

@pytest.mark.parametrize('suffix',['','/files','/preview','/download?format=csv'])
def test_reports_require_login_and_owner(reports_api,suffix):
    ids,client,app,_=reports_api
    url='/reports/'+ids[0]+suffix
    assert client.get(url).status_code==401
    app.dependency_overrides[get_current_user]=lambda:ALICE
    assert client.get(url).status_code==200
    assert client.get('/reports/'+ids[1]+suffix).status_code==404
    assert client.get('/reports/'+ids[2]+suffix).status_code==404
    app.dependency_overrides[get_current_user]=lambda:ADMIN
    assert client.get('/reports/'+ids[2]+suffix).status_code==200


def test_report_listing_and_delete_are_scoped(reports_api):
    ids,client,app,root=reports_api
    app.dependency_overrides[get_current_user]=lambda:ALICE
    response=client.get('/reports');assert response.status_code==200,response.text
    assert response.json()['total']==1
    assert client.delete('/reports/'+ids[1]).status_code==404
    assert (root/ids[1]).exists()
    assert client.delete('/reports/'+ids[0]).status_code==200
    assert not (root/ids[0]).exists()


def test_viewer_cannot_generate_or_delete(reports_api):
    ids,client,app,_=reports_api
    app.dependency_overrides[get_current_user]=lambda:{**ALICE,'roles':['viewer']}
    assert client.get('/reports/'+ids[0]).status_code==200
    assert client.delete('/reports/'+ids[0]).status_code==403
    assert client.post('/reports/generate',json={}).status_code==403


@pytest.mark.parametrize('kind',['dataset','prediction','stream'])
def test_legacy_source_guard_precedes_records_read(tmp_path,monkeypatch,kind):
    root=tmp_path/kind;root.mkdir();rid=str(uuid4());folder=root/rid;folder.mkdir()
    monkeypatch.setattr(service,{'dataset':'DATASET_ROOT','prediction':'PREDICTION_ROOT','stream':'STREAM_ROOT'}[kind],root)
    (folder/'metadata.json').write_text(json.dumps({'owner_id':'bob-id'}))
    if kind=='dataset':(folder/'processed').mkdir();(folder/'processed/records.csv').write_text('x\n1')
    elif kind=='prediction':(folder/'predictions.csv').write_text('x\n1')
    else:(folder/'predictions.jsonl').write_text('{"x":1}\n')
    monkeypatch.setattr(service.pd,'read_csv',lambda *a,**k:pytest.fail('must not read private CSV'))
    monkeypatch.setattr(service,'_read_jsonl',lambda *a,**k:pytest.fail('must not read private JSONL'))
    with acting(ALICE):
        with pytest.raises(HTTPException) as e:service.ReportSourceLoader().load(kind,rid)
        assert e.value.status_code==404


def test_report_creation_owner_cannot_be_spoofed(reports_api,monkeypatch):
    _,_,_,root=reports_api
    svc=service.ReportService()
    monkeypatch.setattr(svc.loader,'load',lambda *a:(pd.DataFrame({'DEPTH':[1,2,3],'GR':[10,20,30]}),{'owner_id':'bob-id'}))
    with acting(ALICE):
        result=svc.generate(service.ReportRequest(source_type='dataset',source_id=str(uuid4()),formats=('json',),include_alerts=False,metadata={'owner_id':'bob-id'}))
        assert result.to_dict()['owner_id']=='alice-id'
        assert json.loads((root/result.report_id/'metadata.json').read_text())['owner_id']=='alice-id'
    with acting(BOB):
        with pytest.raises(HTTPException):svc.get_report(result.report_id)


def test_generate_preserves_access_denial(reports_api,monkeypatch):
    _,client,app,_=reports_api
    app.dependency_overrides[get_current_user]=lambda:ALICE
    svc=service.get_report_service()
    def deny(*args):raise HTTPException(status_code=404,detail='Asset not found.')
    monkeypatch.setattr(svc,'generate',deny)
    response=client.post('/reports/generate',json={'source_type':'dataset','source_id':str(uuid4()),'formats':['json']})
    assert response.status_code==404,response.text


def test_parser_and_dashboard_require_authentication(reports_api):
    _,client,_,_=reports_api
    assert client.post('/legacy/upload-las',files={'file':('a.las',b'invalid')}).status_code==401
    assert client.get('/dashboard').status_code==401


def test_dashboard_metadata_and_related_alerts_filter_owners(tmp_path,monkeypatch):
    from app.services.dashboard_metrics import _iter_metadata
    for owner in ['alice-id','bob-id',None]:
        p=tmp_path/str(uuid4());p.mkdir();(p/'metadata.json').write_text(json.dumps({'owner_id':owner}))
    monkeypatch.setattr(service,'ALERT_ROOT',tmp_path)
    (tmp_path/'alerts.jsonl').write_text('\n'.join(json.dumps({'owner_id':owner,'well_id':'W','source_id':'source'}) for owner in ['alice-id','bob-id',None]))
    with acting(ALICE):
        assert len(list(_iter_metadata(tmp_path)))==1
        assert len(service._load_related_alerts('dataset','source','W'))==1
