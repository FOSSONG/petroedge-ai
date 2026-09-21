import io,time,json
from types import SimpleNamespace
import pytest
from fastapi import HTTPException,Response
from app.services import phone_approval as phone
from app.services.measured_evidence import snapshot,answer
from app.platform_v1 import database,datasets
from test_asset_ownership import acting,ALICE,BOB

@pytest.fixture
def phone_env(tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path)
 monkeypatch.setattr(phone.settings,"phone_approval_required",True)
 monkeypatch.setattr(phone.settings,"public_origin","https://pilot.example.test")
 result={"auth_result":{"result":"allow"},"auth_context":{"factor":"duo_push","result":"success","reason":"user_approved"},"auth_time":time.time()}
 api=SimpleNamespace(health_check=lambda:None,generate_state=lambda:"state123",create_auth_url=lambda *a:"https://api-example.duosecurity.com/auth",exchange_authorization_code_for_2fa_result=lambda *a:result)
 monkeypatch.setattr(phone,"client",lambda:api)
 response=Response();user=SimpleNamespace(id="owner",email="owner@example.test")
 data=phone.begin(user,response)
 from http.cookies import SimpleCookie
 cookie=SimpleCookie();cookie.load(response.headers["set-cookie"])
 return data,cookie[phone.COOKIE].value,result

def test_phone_requires_push_bound_browser_and_one_use(phone_env):
 data,binding,result=phone_env
 assert data["mfa_required"] and "access_token" not in data
 with pytest.raises(HTTPException):phone.finish(binding,"https://pilot.example.test")
 with pytest.raises(HTTPException):phone.approve("state123","code","wrong browser")
 phone.approve("state123","code",binding)
 with pytest.raises(HTTPException):phone.approve("state123","code",binding)
 with pytest.raises(HTTPException):phone.finish(binding,"https://attacker.test")
 assert phone.finish(binding,"https://pilot.example.test")["uid"]=="owner"
 with pytest.raises(HTTPException):phone.finish(binding,"https://pilot.example.test")

@pytest.mark.parametrize("factor",["remembered_device","bypass","passcode","sms_passcode",None])
def test_other_factors_fail_closed(phone_env,factor):
 _,binding,result=phone_env;result["auth_context"]["factor"]=factor
 with pytest.raises(HTTPException):phone.approve("state123","code",binding)
 with pytest.raises(HTTPException):phone.finish(binding,"https://pilot.example.test")

def test_expired_phone_transaction(phone_env):
 _,binding,_=phone_env
 with phone.connection() as c:c.execute("UPDATE transactions SET expires=0")
 with pytest.raises(HTTPException):phone.approve("state123","code",binding)

def test_measured_evidence_owner_missing_and_no_fabrication(tmp_path,monkeypatch):
 monkeypatch.chdir(tmp_path);database.initialise()
 with acting(ALICE):
  d=datasets.register_upload("Logs",None,"a.csv",io.BytesIO(b"DEPTH.M,GR.API,RHOB.G/C3\n100,40,2.4\n101,-999.25,2.5\n102,60,2.6\n"),None)
  ev=snapshot(d.dataset_id);assert ev["curves"]["gamma_ray_api"]["valid"]==2
  assert ev["curves"]["gamma_ray_api"]["median"]==50
  assert "cannot answer" in answer(ev,"What are the oil reserves?")["answer"]
  assert d.checksum_sha256 in answer(ev,"What is the gamma ray median?")["evidence"][1]
 with acting(BOB):
  with pytest.raises(HTTPException) as err:snapshot(d.dataset_id)
  assert err.value.status_code==404


def test_twin_restart_preserves_state_history_and_owner(tmp_path,monkeypatch):
 from app.digital_twin.registry import TwinRegistry
 from app.digital_twin.history import TwinHistory
 from app.digital_twin.schemas import ReservoirState,UpdateSource
 monkeypatch.setenv("PETROEDGE_TWIN_STORE",str(tmp_path/"twins.sqlite3"))
 registry=TwinRegistry();history=TwinHistory()
 with acting(ALICE):
  state=registry.create(ReservoirState(reservoir_id="restart",name="Restart test"))
  history.append(state,list(UpdateSource)[0])
  assert TwinRegistry().get("restart").owner_id==ALICE["user_id"]
  assert len(TwinHistory().list("restart"))==1
 with acting(BOB):
  assert TwinRegistry().list()==[]
  assert TwinHistory().list("restart")==[]
  with pytest.raises(HTTPException):TwinRegistry().get("restart")


def test_password_session_rejected_when_phone_required(monkeypatch):
 from app.core.security import resolve_current_user
 monkeypatch.setattr(phone.settings,"phone_approval_required",True)
 account=SimpleNamespace(id="a",email="owner@example.test",is_active=True,role="admin",full_name="Owner")
 db=SimpleNamespace(get=lambda *a:account)
 with pytest.raises(HTTPException) as err:resolve_current_user({"uid":"a","sub":account.email},db)
 assert err.value.status_code==401


def test_missing_duo_configuration_blocks_login(monkeypatch):
 monkeypatch.setattr(phone.settings,"public_origin","")
 with pytest.raises(HTTPException) as err:phone.client()
 assert err.value.status_code==503


def test_password_callback_completion_route_has_no_early_token(tmp_path,monkeypatch):
 from fastapi import FastAPI
 from fastapi.testclient import TestClient
 from app.api.routes import auth
 from app.api.dependencies import get_user_repository
 from app.core.security import hash_password,decode_access_token
 monkeypatch.chdir(tmp_path)
 monkeypatch.setattr(phone.settings,"phone_approval_required",True)
 monkeypatch.setattr(phone.settings,"public_origin","https://pilot.example.test")
 result={"auth_result":{"result":"allow"},"auth_context":{"factor":"duo_push","result":"success","reason":"user_approved"},"auth_time":time.time()}
 api=SimpleNamespace(health_check=lambda:None,generate_state=lambda:"route-state",create_auth_url=lambda *a:"https://api-example.duosecurity.com/auth",exchange_authorization_code_for_2fa_result=lambda *a:result)
 monkeypatch.setattr(phone,"client",lambda:api)
 user=SimpleNamespace(id="a",email="owner@example.test",is_active=True,role="admin",full_name="Owner",hashed_password=hash_password("test-only-long-password"))
 repo=SimpleNamespace(get_by_email=lambda e:user if e==user.email else None,commit=lambda:None)
 app=FastAPI();app.include_router(auth.router,prefix="/api/v1/auth");app.dependency_overrides[get_user_repository]=lambda:repo
 with TestClient(app,base_url="https://pilot.example.test") as client:
  login=client.post("/api/v1/auth/login",json={"username":user.email,"password":"test-only-long-password"})
  assert login.status_code==200,login.text
  assert login.json()["mfa_required"] and "access_token" not in login.json()
  assert "HttpOnly" in login.headers["set-cookie"] and "Secure" in login.headers["set-cookie"]
  assert client.post("/api/v1/auth/duo/complete",headers={"Origin":"https://pilot.example.test"}).status_code==401
  callback=client.get("/api/v1/auth/duo/callback?state=route-state&duo_code=test-code",follow_redirects=False)
  assert callback.status_code==303
  completed=client.post("/api/v1/auth/duo/complete",headers={"Origin":"https://pilot.example.test"})
  assert completed.status_code==200,completed.text
  assert decode_access_token(completed.json()["access_token"])["phone_approved"] is True
  assert client.post("/api/v1/auth/duo/complete",headers={"Origin":"https://pilot.example.test"}).status_code in [401,403]
