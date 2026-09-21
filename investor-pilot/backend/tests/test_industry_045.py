import io
from types import SimpleNamespace
from contextlib import contextmanager
import numpy as np
import pytest
from app.services.industry_files import read_text_table, read_dlis
from app.preprocessing.curve_aliases import canonical_name_for, header_parts
from app.platform_v1 import database,datasets
from app.api.routes.reservoir_v1 import _frame
from test_asset_ownership import acting, ALICE

@pytest.mark.parametrize("delimiter", [",", ";", "\t", " "])
def test_ascii_delimiters(tmp_path, delimiter):
    path=tmp_path/"well.asc"
    path.write_text(delimiter.join(["DEPTH.M","GR.API"])+"\n"+delimiter.join(["100","45"])+"\n")
    f=read_text_table(path)
    assert list(f)==["DEPTH.M","GR.API"] and f.iloc[0,1]==45

@pytest.mark.parametrize("text",["100 50\n101 60\n", "GR,GR\n1,2\n", ""])
def test_reject_ambiguous_ascii(tmp_path,text):
    path=tmp_path/"bad.txt";path.write_text(text)
    with pytest.raises(ValueError): read_text_table(path)

@pytest.mark.parametrize("header,target,unit",[
    ("RHOB [g/cm\u00b3]","density_gcc","G/CM3"),
    ("DT (\u00b5s/ft)","sonic_usft","US/FT"),
    ("RT [\u03a9\u00b7m]","resistivity_ohmm","OHM.M"),
    ("GR_EDTC_R.API","gamma_ray_api","API")])
def test_unicode_units(header,target,unit):
    assert canonical_name_for(header)==target and header_parts(header)[1]==unit

def test_ascii_registered_preview_and_screening(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path);database.initialise()
    with acting(ALICE):
        d=datasets.register_upload("ASCII",None,"well.asc",io.BytesIO(b"DEPTH.FT GR.API RHOB.KG/M3\n1000 50 2400\n1001 60 2500\n"),None)
        assert datasets.preview_dataset(d.dataset_id,1,1)["rows"][0]["GR.API"]==60
        f,_=_frame(d.dataset_id)
        assert f.iloc[0]["depth_m"]==pytest.approx(304.8)
        assert f.iloc[0]["density_gcc"]==pytest.approx(2.4)

def test_dlis_preserves_scalar_units_and_rejects_multiple_frames(monkeypatch):
    from dlisio import dlis
    arr=np.zeros(2,dtype=[(("fingerprint","GR"),float)])
    arr["GR"]=[45,60]
    frame=SimpleNamespace(name="F1",channels=[SimpleNamespace(name="GR",fingerprint="fingerprint",units="API")],curves=lambda:arr)
    frames=[frame]
    @contextmanager
    def load(_): yield [SimpleNamespace(frames=frames)]
    monkeypatch.setattr(dlis,"load",load)
    result=read_dlis("sample.dlis")
    assert list(result.GR)==[45,60] and result.attrs["source_units"]=={"GR":"API"}
    frames.append(frame)
    with pytest.raises(ValueError,match="never silently combined"): read_dlis("sample.dlis")

def test_panel_reads_source_once(monkeypatch):
    import asyncio
    from app.api.routes import agents
    from app.services import measured_evidence
    monkeypatch.setattr(agents,"_validate_sources",lambda _:None)
    from pathlib import Path
    monkeypatch.setattr(datasets,"get_dataset_path",lambda _:Path("x.csv"))
    calls=[]
    def snapshot(*args):
        calls.append(args)
        return {"dataset_id":"x","rows":2,"curves":{},"issues":[],"sha256":"abc"}
    monkeypatch.setattr(measured_evidence,"snapshot",snapshot)
    result=asyncio.run(agents.run_panel(agents.AgentRunRequest(dataset_id="x")))
    assert len(calls)==1 and len(result["agents"])==5

def test_pdf_retrieval_cites_and_is_owner_scoped(tmp_path,monkeypatch):
    from reportlab.pdfgen import canvas
    from fastapi import HTTPException
    from test_asset_ownership import BOB
    from app.services.document_evidence import retrieve
    monkeypatch.chdir(tmp_path);database.initialise()
    stream=io.BytesIO();pdf=canvas.Canvas(stream)
    pdf.drawString(40,750,"Reservoir porosity measurements require core calibration.")
    pdf.showPage();pdf.drawString(40,750,"Injection pressure must stay below the fracture pressure.");pdf.save()
    with acting(ALICE):
        d=datasets.register_upload("Technical evidence",None,"evidence.pdf",io.BytesIO(stream.getvalue()),None,dataset_type="technical_document")
        result=retrieve(d.dataset_id,"What is the injection pressure constraint?")
        assert result["passages"][0]["page"]==2
        assert d.checksum_sha256 in result["evidence"][1]
        assert not retrieve(d.dataset_id,"elephant banana orbital")["passages"]
    with acting(BOB):
        with pytest.raises(HTTPException):retrieve(d.dataset_id,"injection")
