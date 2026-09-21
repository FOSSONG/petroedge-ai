import pandas as pd
import pytest
from app.services.well_curve_mapping import CurveMapping, mapped_records, validate_mapping
from test_well_dataset_access import well_client

def mapping(reference="MD"):
    return CurveMapping(depth_reference=reference, curves={
        "depth_m":{"source":"D","unit":"ft"},
        "gamma_ray_api":{"source":"G","unit":"API"},
        "resistivity_ohmm":{"source":"R","unit":"ohm.m"},
        "density_gcc":{"source":"B","unit":"kg/m3"},
        "neutron_porosity_vv":{"source":"N","unit":"%", "null_values":[-999.25]},
        "sonic_usft":{"source":"S","unit":"us/m"},
        "caliper_in":{"source":"C","unit":"mm"},
    })

def frame():
    return pd.DataFrame([dict(D=1000,G=40,R=20,B=2500,N=20,S=200,C=254)])

def test_conversion_and_preserved_source():
    source=frame();before=source.copy(deep=True)
    row=mapped_records(source,mapping(),"W1")[0]
    assert row["depth_m"]==pytest.approx(304.8)
    assert row["density_gcc"]==2.5
    assert row["neutron_porosity_vv"]==0.2
    assert row["sonic_usft"]==pytest.approx(60.96)
    assert row["caliper_in"]==pytest.approx(10)
    assert row["analysis_ready"] is True
    pd.testing.assert_frame_equal(source,before)

@pytest.mark.parametrize("bad", [-999.25, "invalid", float("inf"), None, 150])
def test_bad_measurements_not_analysis_ready(bad):
    source=frame();source["N"]=bad
    row=mapped_records(source,mapping(),"W1")[0]
    assert row["analysis_ready"] is False

@pytest.mark.parametrize("reference",["TVD","TVDSS"])
def test_depth_references_not_interchangeable(reference):
    assert mapped_records(frame(),mapping(reference),"W1")[0]["analysis_ready"] is False

def test_invalid_mapping_rejected():
    m=mapping();m.curves["density_gcc"].unit="API"
    with pytest.raises(ValueError):validate_mapping(m,frame().columns)
    m=mapping();m.curves["density_gcc"].source="G"
    with pytest.raises(ValueError):validate_mapping(m,frame().columns)
    with pytest.raises(ValueError):validate_mapping(mapping(),["D"])

def test_mapping_round_trip_and_raw_retained(well_client):
    c,user,data=well_client
    payload={"dataset_id":data.dataset_id,"mapping":{"depth_reference":"MD","curves":{"depth_m":{"source":"DEPTH","unit":"ft"},"gamma_ray_api":{"source":"GR","unit":"API"}}}}
    assert c.put("/wells/W1/log-dataset",json=payload).status_code==200
    config=c.get("/wells/W1/log-dataset").json()
    assert config["binding"]["mapping"]["curves"]["depth_m"]["unit"]=="ft"
    row=c.get("/wells/W1/logs?mapped=true").json()[0]
    assert row["depth_m"]==pytest.approx(30.48)
    assert row["analysis_ready"] is False
    assert c.get("/wells/W1/logs").json()[0]["DEPTH"]==100
    payload["mapping"]["curves"]["depth_m"]["unit"]="API"
    assert c.put("/wells/W1/log-dataset",json=payload).status_code==422
