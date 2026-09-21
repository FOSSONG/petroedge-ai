from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"models/missing_curve_028";O.mkdir(parents=True,exist_ok=False)
C=B/"data/prepared/platform_manifest_001.json";cat=json.loads(C.read_text())
old=json.loads((B/"models/exploratory_020/report.json").read_text());report=[]
for e in old["experiments"]:
 if e["status"]!="trained_experimental":continue
 entry=cat["datasets"][e["dataset_id"]];path=C.parent/entry["path"]
 assert hashlib.sha256(path.read_bytes()).hexdigest()==entry["sha256"]
 ap=Path(e["artifact_directory"])/"assignments.csv";assert hashlib.sha256(ap.read_bytes()).hexdigest()==e["artifact_sha256"]["assignments.csv"]
 a=pd.read_csv(ap);f=pd.read_csv(path).set_index("specimen_id")
 tr=f.loc[a.loc[a.partition.eq("train"),"specimen_id"]];va=f.loc[a.loc[a.partition.eq("validation"),"specimen_id"]]
 folder=O/e["dataset_id"].replace(":","_");folder.mkdir();target=entry["target_column"];features=entry["feature_columns"];variants=[]
 for missing in [None,*features]:
  fs=[c for c in features if c!=missing];name="full_inputs" if missing is None else "without_"+missing
  m=RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=42,n_jobs=1)
  if "permeability" in entry["target_definition"]:m=TransformedTargetRegressor(regressor=m,func=np.log1p,inverse_func=np.expm1)
  m.fit(tr[fs],tr[target]);pred=m.predict(va[fs]);assert np.isfinite(pred).all()
  artifact=dict(model=m,required_features=fs,missing_curve=missing,target=entry["target_definition"],condition=entry["condition"],unit=entry["constant_columns"]["target_unit"],status="experimental_not_approved",imputation="none",test_used=False)
  dest=folder/(name+".joblib");joblib.dump(artifact,dest);assert np.allclose(pred,joblib.load(dest)["model"].predict(va[fs]))
  pd.DataFrame({"specimen_id":va.index,"measured":va[target],"predicted":pred}).to_csv(folder/(name+"_validation.csv"),index=False)
  variants.append(dict(name=name,missing_curve=missing,required_features=fs,validation_mae=float(mean_absolute_error(va[target],pred)),artifact=str(dest),sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
 full=variants[0]["validation_mae"]
 for v in variants:v["mae_change_vs_full_percent"]=100*(v["validation_mae"]/full-1) if full else None
 record=dict(name=e["name"],dataset_id=e["dataset_id"],training_rows=len(tr),validation_rows=len(va),test_rows_excluded=int(a.partition.eq("test").sum()),variants=variants,production_eligible=False)
 report.append(record);print(e["name"],flush=True)
(O/"REPORT.json").write_text(json.dumps({"status":"EXPERIMENTAL_REDUCED_INPUT_COMPARISON","design":"Identical original training and validation rows across variants; one required curve removed at a time. No imputation. No test evaluation or automatic deployment. Small reused validation partitions do not qualify variants for operational selection.","datasets":report},indent=2),encoding="utf-8")
lines=["# Missing curve experiments","","Five Random Forest variants per dataset: full inputs, then omission of each of the four original curves. Each variant is separately trained; no curve is fabricated. DT was not in these feature contracts. Two or more missing curves remain unsupported.","","Validation results are developmental and conditional on the original data qualification. Models remain outside the production registry. A lower validation error after removing a curve does not establish better unseen-well performance.","","| Dataset | Missing curve | Validation MAE | Change versus full |","|---|---|---:|---:|"]
for r in report:
 for v in r["variants"]:lines.append(f"| {r['name']} | {v['missing_curve'] or 'none'} | {v['validation_mae']:.5g} | {v['mae_change_vs_full_percent']:.1f}% |")
(O/"README.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps({"datasets":len(report),"models":sum(len(r["variants"]) for r in report)}))
