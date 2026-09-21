"""Read-only projection of an administrator-configured experiment report."""
import json
import os
from pathlib import Path

def experimental_comparison():
    configured=os.environ.get("PETROEDGE_EXPERIMENT_REPORT")
    if not configured:
        return {"configured":False,"design":"No experimental report configured.","datasets":[]}
    path=Path(configured)
    if path.stat().st_size>5_000_000:
        raise ValueError("Experimental report exceeds supported size")
    report=json.loads(path.read_text(encoding="utf-8"))
    datasets=[]
    for row in report["datasets"]:
        variants=[{k:v[k] for k in ("name","missing_curve","required_features","validation_mae","mae_change_vs_full_percent")} for v in row["variants"]]
        datasets.append({**{k:row[k] for k in ("name","dataset_id","training_rows","validation_rows","test_rows_excluded")},"variants":variants,"production_eligible":False,"error_unit":"mD" if "/ permeability" in row["name"] else "porosity fraction"})
    return {"configured":True,"design":report["design"],"datasets":datasets}
