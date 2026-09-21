from types import SimpleNamespace
import pandas as pd
import pytest
from app.api.routes import reservoir_v1 as reservoir
from app.preprocessing.curve_aliases import canonical_name_for, curve_match
from app.preprocessing.pipeline import _interpolate_short_gaps


def dataset(units=None):
    return SimpleNamespace(units=units or {}, processing={}, model_dump=lambda: {"dataset_id": "test", "name": "QC fixture"})


def logs(rows=3):
    return pd.DataFrame({"depth_m": range(100, 100+rows), "gamma_ray_api": [40.0]*rows,
        "resistivity_ohmm": [20]*rows, "density_gcc": [2.5]*rows,
        "neutron_porosity_vv": [.2]*rows, "sonic_usft": [80]*rows, "caliper_in": [8.5]*rows})


def install(monkeypatch, frame):
    monkeypatch.setattr(reservoir, "get_dataset", lambda _: dataset())
    monkeypatch.setattr(reservoir, "_frame", lambda _: (frame.copy(), {c:c for c in frame}))


def test_alias_variants_and_ambiguity():
    assert canonical_name_for("borehole-depth") == "depth_m"
    assert canonical_name_for("RHOB.COMP") == "density_gcc"
    assert canonical_name_for("GR:1") == "gamma_ray_api"
    assert canonical_name_for("RM") is None
    assert curve_match("RM")["status"] == "ambiguous"
    assert set(curve_match("RM")["candidates"]) == {"medium_resistivity_ohmm", "mud_resistivity_ohmm"}
    assert canonical_name_for("GR_mystery_vendor") is None


def test_missing_curve_is_not_filled(monkeypatch):
    install(monkeypatch, logs().drop(columns="density_gcc"))
    with pytest.raises(ValueError, match="Missing curve: density_gcc"):
        reservoir._interpret("test")


def test_invalid_rows_excluded_and_scores_not_claimed_calibrated(monkeypatch):
    frame = logs(); frame.loc[1, "gamma_ray_api"] = -999.25
    install(monkeypatch, frame)
    result = reservoir._interpret("test")
    assert [r["source_row"] for r in result["samples"]] == [0,2]
    assert result["summary"]["excluded_rows"] == 1
    assert result["summary"]["output_kind"] == "heuristic_scores_not_probabilities"
    assert "Uncalibrated" in result["summary"]["calibration"]


def test_no_synthetic_depth_or_missing_rows(monkeypatch):
    frame=logs();frame["density_gcc"]=float("nan")
    install(monkeypatch, frame)
    with pytest.raises(ValueError, match="No complete valid rows"):
        reservoir._interpret("test")
    install(monkeypatch, logs().assign(depth_m=[100,100,101]))
    with pytest.raises(ValueError, match="unique and increasing"):
        reservoir._interpret("test")


def test_fluid_scores_respond_to_measurements(monkeypatch):
    frame=logs(); frame.loc[1,["resistivity_ohmm","density_gcc","neutron_porosity_vv","sonic_usft"]]=[100,2.2,.05,130]
    install(monkeypatch,frame)
    values=reservoir._interpret("test")["samples"]
    assert values[0]["fluid_probabilities"] != values[1]["fluid_probabilities"]


def test_reading_covers_deeper_valid_rows_and_converts_declared_units(tmp_path,monkeypatch):
    frame=logs(2101).rename(columns={"depth_m":"DEPT"}); frame.loc[:2099,"gamma_ray_api"]=-999.25
    path=tmp_path/"logs.csv";frame.to_csv(path,index=False)
    monkeypatch.setattr(reservoir,"get_dataset_path",lambda _:path)
    monkeypatch.setattr(reservoir,"get_dataset",lambda _:dataset({"DEPT":"FT"}))
    result=reservoir._interpret("test")
    assert result["summary"]["source_rows"]==2101
    assert len(result["samples"])==1
    assert result["samples"][0]["depth"]==pytest.approx(2200*.3048,abs=.001)


def test_raw_alias_without_unit_blocks(tmp_path,monkeypatch):
    path=tmp_path/"logs.csv";logs().rename(columns={"density_gcc":"RHOB"}).to_csv(path,index=False)
    monkeypatch.setattr(reservoir,"get_dataset_path",lambda _:path)
    monkeypatch.setattr(reservoir,"get_dataset",lambda _:dataset())
    with pytest.raises(ValueError,match="RHOB: declare supported"):
        reservoir._interpret("test")


def test_interpolation_does_not_partially_fill_long_gaps():
    frame=pd.DataFrame({"gamma_ray_api":[1,None,3,None,None,None,None,8]})
    result,counts=_interpolate_short_gaps(frame,curves=["gamma_ray_api"],limit=2,method="linear")
    assert result.loc[1,"gamma_ray_api"]==2
    assert result.loc[3:6,"gamma_ray_api"].isna().all()
    assert counts["gamma_ray_api"]==1


def test_prepared_copy_preserves_rows_and_does_not_invent_caliper(tmp_path,monkeypatch):
    import io
    from app.platform_v1 import database,datasets
    from app.platform_v1.schemas import DatasetPreparationRequest
    monkeypatch.chdir(tmp_path);database.initialise()
    source=datasets.register_upload("QC source",None,"logs.csv",io.BytesIO(b"DEPTH,GR\n100,10\n100,-999.25\n101,30\n"),None)
    child=datasets.prepare_dataset(source.dataset_id,DatasetPreparationRequest(interpolate_limit=0,despike=False,null_values=[-999.25]),None)
    frame=datasets._frame(datasets.get_dataset_path(child.dataset_id))
    assert len(frame)==3
    assert frame.depth_m.tolist()==[100,100,101]
    assert "caliper_in" not in frame
    assert pd.isna(frame.loc[1,"gamma_ray_api"])
    original=datasets._frame(datasets.get_dataset_path(source.dataset_id))
    assert original.loc[1,"GR"]==-999.25
    with pytest.raises(ValueError,match="duplicate or unordered"):
        datasets.prepare_dataset(source.dataset_id,DatasetPreparationRequest(interpolate_limit=1,despike=False),None)


def test_missing_optional_sonic_is_reported_not_fabricated(monkeypatch):
    install(monkeypatch,logs().drop(columns=["sonic_usft","caliper_in"]))
    result=reservoir._interpret("test")
    assert result["samples"][0]["dt"] is None
    assert result["samples"][0]["caliper"] is None
    assert result["samples"][0]["porosity"]>0
    assert set(result["summary"]["missing_optional_curves"])=={"sonic_usft","caliper_in"}


def test_explicit_mapping_copy_to_screening_with_owner_isolation(tmp_path,monkeypatch):
    import io
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.platform_v1 import database,datasets
    from app.core.security import get_current_user
    from app.core.ownership import OwnershipContextMiddleware
    from test_asset_ownership import ALICE,BOB,acting
    monkeypatch.chdir(tmp_path);database.initialise()
    with acting(ALICE):
        source=datasets.register_upload("Explicit units",None,"source.csv",io.BytesIO(b"D,G,R,B,N\n100,40,20,2500,20\n101,50,30,2400,25\n"),None)
    app=FastAPI();app.add_middleware(OwnershipContextMiddleware);app.include_router(reservoir.router)
    user={"value":ALICE};app.dependency_overrides[get_current_user]=lambda:user["value"]
    targets=["depth_m","gamma_ray_api","resistivity_ohmm","density_gcc","neutron_porosity_vv"]
    payload={"depth_reference":"MD","curves":{target:{"source":col,"unit":unit} for target,col,unit in zip(targets,"DGRBN",["ft","API","ohm.m","kg/m3","%"] )}}
    with TestClient(app) as client:
        response=client.post(f"/datasets/{source.dataset_id}/mapped-copy",json=payload)
        assert response.status_code==201,response.text
        child=response.json();assert child["owner_id"]==ALICE["user_id"]
        response=client.get(f"/datasets/{child['dataset_id']}/interpretation")
        assert response.status_code==200,response.text
        sample=response.json()["samples"][0]
        assert sample["depth"]==30.48
        assert sample["rhob"]==2.5 and sample["nphi"]==.2
        assert sample["dt"] is None
        user["value"]=BOB
        assert client.get(f"/datasets/{child['dataset_id']}/interpretation").status_code==404


def test_crossplot_data_uses_deep_rows_and_pairwise_qc(monkeypatch):
    frame=logs(2100);frame.loc[:2050,"gamma_ray_api"]=float("nan")
    install(monkeypatch,frame)
    result=reservoir.crossplot_data("test",{})
    assert len(result["rows"])==2100
    assert result["rows"][0]["gamma_ray_api"] is None
    assert result["rows"][2099]["gamma_ray_api"]==40
    assert result["rows"][0]["density_gcc"]==2.5


def test_pdf_export_returns_actual_pdf_and_qc_errors(monkeypatch):
    import asyncio
    install(monkeypatch,logs())
    response=reservoir.log_signature_pdf("test",{})
    async def read():
        chunks=[]
        async for chunk in response.body_iterator:chunks.append(chunk)
        return b"".join(chunks)
    content=asyncio.run(read())
    assert content.startswith(b"%PDF-") and len(content)>1000
    assert "attachment" in response.headers["content-disposition"]
