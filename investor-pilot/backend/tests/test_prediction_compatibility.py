import pandas as pd
import pytest
from app.ml_lifecycle import service

def test_missing_and_empty_curves():
 _,r=service._prediction_inputs({"feature_columns":["GR","NPHI","RT"]},pd.DataFrame({"GR":[20,40],"RT":[-999.25,None]}))
 assert not r["ready"] and r["missing_columns"]==["NPHI"] and r["empty_columns"]==["RT"]
 assert r["complete_rows"]==0

def test_partial_invalid_values_and_numeric_strings():
 _,r=service._prediction_inputs({"feature_columns":["GR"]},pd.DataFrame({"GR":["20","bad"]}))
 assert not r["ready"] and r["complete_rows"]==1 and r["invalid_counts"]=={"GR":1}
 numeric,r=service._prediction_inputs({"feature_columns":["GR"]},pd.DataFrame({"GR":["20",0]}))
 assert r["ready"] and numeric.GR.tolist()==[20,0]

def test_prediction_blocks_before_loading_artifact(monkeypatch):
 monkeypatch.setattr(service,"get_model",lambda _: {"feature_columns":["NPHI"]})
 monkeypatch.setattr(service,"_load_dataset",lambda _: pd.DataFrame({"GR":[20]}))
 monkeypatch.setattr(service.joblib,"load",lambda _: pytest.fail("Must not load unsupported model"))
 with pytest.raises(ValueError,match="Missing required columns: NPHI"):service.predict_dataset("m","d")
