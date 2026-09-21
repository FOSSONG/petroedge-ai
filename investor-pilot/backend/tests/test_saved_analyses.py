import hashlib
import sqlite3
from types import SimpleNamespace
import joblib
import pytest
from fastapi import HTTPException
from app.services import analysis_records
from app.ml_platform.adapters import JoblibAdapter
from test_asset_ownership import acting, ALICE, BOB, ADMIN

def test_saved_result_private_immutable_and_integrity_checked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    original={"input":{"x":1},"provenance":{"persisted":False}}
    with acting(ALICE):
        saved=analysis_records.save(original)
        key=saved["analysis_id"]
        original["input"]["x"]=999
        assert analysis_records.get(key)["input"]["x"]==1
        assert len(analysis_records.list_records())==1
    with acting(BOB):
        assert analysis_records.list_records()==[]
        with pytest.raises(HTTPException) as e:analysis_records.get(key)
        assert e.value.status_code==404
    with acting(ADMIN):assert analysis_records.get(key)["provenance"]["persisted"] is True
    conn=sqlite3.connect(tmp_path/"analysis_store/analyses.sqlite3")
    with conn:conn.execute("UPDATE analyses SET payload=? WHERE analysis_id=?", ('{}',key))
    conn.close()
    with acting(ALICE):
        with pytest.raises(HTTPException) as e:analysis_records.get(key)
        assert e.value.status_code==409

def test_artifact_hash_identifies_loaded_bytes_not_replaced_file(tmp_path):
    path=tmp_path/"model.joblib";joblib.dump({"v":1},path)
    first=hashlib.sha256(path.read_bytes()).hexdigest()
    adapter=JoblibAdapter(SimpleNamespace(),path);adapter.load()
    joblib.dump({"v":2},path)
    assert adapter.artifact_sha256==first and adapter.model=={"v":1}
    adapter.unload();adapter.load()
    assert adapter.artifact_sha256==hashlib.sha256(path.read_bytes()).hexdigest()
    assert adapter.model=={"v":2}
