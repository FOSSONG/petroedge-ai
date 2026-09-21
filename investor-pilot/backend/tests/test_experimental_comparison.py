import json
from app.ml_lifecycle.experimental import experimental_comparison

def test_unconfigured(monkeypatch):
 monkeypatch.delenv("PETROEDGE_EXPERIMENT_REPORT",raising=False)
 assert experimental_comparison()["configured"] is False

def test_report_does_not_expose_artifact_paths(tmp_path,monkeypatch):
 p=tmp_path/"report.json"
 p.write_text(json.dumps({"design":"development only","datasets":[{"name":"W / permeability_air / stress","dataset_id":"d","training_rows":20,"validation_rows":5,"test_rows_excluded":5,"production_eligible":True,"variants":[{"name":"full","missing_curve":None,"required_features":["GR"],"validation_mae":1,"mae_change_vs_full_percent":0,"artifact":"private/path","sha256":"private"}]}]}))
 monkeypatch.setenv("PETROEDGE_EXPERIMENT_REPORT",str(p))
 r=experimental_comparison();assert r["datasets"][0]["production_eligible"] is False
 assert "artifact" not in r["datasets"][0]["variants"][0]
 assert r["datasets"][0]["error_unit"]=="mD"
