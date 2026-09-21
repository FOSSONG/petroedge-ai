import json,hashlib
from types import SimpleNamespace
import joblib,pandas as pd,pytest
from sklearn.dummy import DummyRegressor
from app.ml_lifecycle import research as r
@pytest.fixture
def setup(tmp_path,monkeypatch):
 model=DummyRegressor(strategy='mean').fit(pd.DataFrame({'gr':[1.,2.,3.]}),[.1,.2,.3]);artifact=tmp_path/'m.joblib';joblib.dump(model,artifact)
 manifest={'enabled':True,'models':[{'id':'m','name':'Research porosity','artifact':'m.joblib','sha256':hashlib.sha256(artifact.read_bytes()).hexdigest(),'source_sha256':'training','features':[{'name':'gr','unit':'API','min':1,'max':3}],'target':'porosity','condition':'190_bar','unit':'fraction','validation_mae':.03,'validation_rows':6,'limitations':['Experimental only'],'production_eligible':False}]}
 mp=tmp_path/'manifest.json';mp.write_text(json.dumps(manifest));data=tmp_path/'data.csv';data.write_text('GR\n2\n-999.25\n4\n')
 monkeypatch.setattr(r,'ROOT',tmp_path);monkeypatch.setattr(r,'get_dataset_path',lambda _:data)
 ds=SimpleNamespace(checksum_sha256=hashlib.sha256(data.read_bytes()).hexdigest(),units={'GR':'API'});monkeypatch.setattr(r,'get_dataset',lambda _:ds)
 req=r.ResearchRequest(model_id='m',dataset_id='d',mapping={'gr':'GR'},units={'gr':'API'},acknowledge_experimental=True)
 return req,manifest,mp,artifact,ds,data

def test_prediction_withholds_bad_rows_and_preserves_provenance(setup):
 req,_,_,_,_,_=setup;out=r.predict(req);assert out['predicted_rows']==1;assert out['samples'][0]['prediction']==pytest.approx(.2);assert out['samples'][1]['prediction'] is None;assert 'missing or invalid' in out['samples'][1]['reasons'][0];assert 'outside training range' in out['samples'][2]['reasons'][0];assert out['model_sha256'];assert not out['production_eligible'];assert 'artifact' not in r.catalog()['models'][0]

@pytest.mark.parametrize('change',[{'acknowledge_experimental':False},{'mapping':{'gr':'absent'}},{'units':{'gr':'unknown'}},{'model_id':'../../other'}])
def test_bad_requests_rejected(setup,change):
 req,*_=setup
 with pytest.raises(ValueError):r.predict(req.model_copy(update=change))

def test_disable_and_tamper_fail_closed(setup):
 req,c,p,artifact,_,_=setup;c['enabled']=False;p.write_text(json.dumps(c));assert r.catalog()['models']==[]
 with pytest.raises(ValueError,match='disabled'):r.predict(req)
 c['enabled']=True;p.write_text(json.dumps(c));artifact.write_bytes(b'corrupt')
 with pytest.raises(ValueError,match='integrity'):r.predict(req)

def test_changed_dataset_and_conflicting_units_rejected(setup):
 req,_,_,_,ds,data=setup;ds.units={'GR':'GAPI'}
 with pytest.raises(ValueError,match='conflicts'):r.predict(req)
 ds.units={'GR':'API'};data.write_text('GR\n2\n')
 with pytest.raises(ValueError,match='checksum'):r.predict(req)

def test_role_gate(setup):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.api.routes.training_lifecycle import router
 from app.core.security import get_current_user
 app=FastAPI();app.include_router(router);user={'roles':['viewer'],'user_id':'viewer'};app.dependency_overrides[get_current_user]=lambda:user
 with TestClient(app) as client:
  assert client.get('/research-models').status_code==403
  assert client.post('/research-predict',json=setup[0].model_dump()).status_code==403
  user['roles']=['admin'];assert client.get('/research-models').status_code==200
  assert client.post('/research-predict',json=setup[0].model_dump()).status_code==200


def test_real_shortlist_upload_to_research_result(tmp_path,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.api.routes import platform,training_lifecycle
 from app.core.security import get_current_user
 from app.core.ownership import OwnershipContextMiddleware
 from app.platform_v1 import database
 # Isolated upload store; real shortlisted artifacts, no application database writes.
 monkeypatch.chdir(tmp_path);database.initialise()
 app=FastAPI();app.add_middleware(OwnershipContextMiddleware);app.include_router(platform.router);app.include_router(training_lifecycle.router,prefix='/training')
 app.dependency_overrides[get_current_user]=lambda:{'user_id':'research-test-admin','roles':['admin']}
 with TestClient(app) as client:
  models=client.get('/training/research-models').json()['models'];assert len(models)==2
  for model in models:
   names=[f['name'] for f in model['features']];units={f['name']:f['unit'] for f in model['features']};values=[(f['min']+f['max'])/2 for f in model['features']]
   # Exercise kg/m3 and percent conversion using explicit user declarations.
   units[names[1]]='kg/m3';values[1]*=1000;units[names[2]]='%';values[2]*=100
   raw=(','.join(names)+'\n'+','.join(map(str,values))+'\n'+','.join(['-999.25']+list(map(str,values[1:])))+'\n').encode()
   upload=client.post('/platform/datasets',data={'name':'Research integration fixture'},files={'file':('fixture.csv',raw,'text/csv')});assert upload.status_code==201,upload.text
   dataset=upload.json();result=client.post('/training/research-predict',json={'model_id':model['id'],'dataset_id':dataset['dataset_id'],'mapping':dict(zip(names,names)),'units':units,'acknowledge_experimental':True});assert result.status_code==200,result.text
   out=result.json();assert out['predicted_rows']==1 and out['rows']==2;assert out['samples'][1]['status']=='withheld';assert out['dataset_sha256']==dataset['checksum_sha256'];assert out['condition'] in ['190_bar','225_bar'];assert not out['production_eligible']
   assert json.loads(json.dumps(out,allow_nan=False))==out


def test_full_well_batches_preserve_all_rows(setup,monkeypatch):
 req,_,_,artifact,ds,data=setup
 n=18373;values=['2']*n;values[2048]='-999.25';values[-1]='4';data.write_text('GR\n'+'\n'.join(values)+'\n');ds.checksum_sha256=hashlib.sha256(data.read_bytes()).hexdigest()
 model=joblib.load(artifact);sizes=[]
 class RecordingModel:
  def predict(self,x):sizes.append(len(x));return model.predict(x)
 monkeypatch.setattr(r.joblib,'load',lambda _:RecordingModel())
 out=r.predict(req);assert out['rows']==n and len(out['samples'])==n;assert out['predicted_rows']==n-2
 assert [v['source_row'] for v in out['samples']]==list(range(n))
 assert out['samples'][2048]['prediction'] is None and out['samples'][-1]['prediction'] is None
 assert max(sizes)<=2048 and len(sizes)>1 and sum(sizes)==n-2
 assert out['processing']['complete'];json.dumps(out,allow_nan=False)

def test_oversize_rejected_without_partial_predictions(setup,monkeypatch):
 req,_,_,_,_,_=setup;monkeypatch.setattr(r,'MAX_RESEARCH_ROWS',2)
 with pytest.raises(ValueError,match='no partial result'):r.predict(req)
