from pathlib import Path
import json,hashlib,collections,platform
import numpy as np
import pandas as pd
import sklearn,joblib
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor,GradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.compose import TransformedTargetRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"models/regression_development_027";O.mkdir(parents=True,exist_ok=False)
C=B/"data/prepared/platform_manifest_001.json";catalog=json.loads(C.read_text())
previous=json.loads((B/"models/exploratory_020/report.json").read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def create(name,log):
 models={"median_baseline":DummyRegressor(strategy="median"),"random_forest":RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=42,n_jobs=1),"extra_trees":ExtraTreesRegressor(n_estimators=128,min_samples_leaf=3,random_state=42,n_jobs=1),"gradient_boosting":GradientBoostingRegressor(n_estimators=100,max_depth=2,min_samples_leaf=3,learning_rate=.05,loss="huber",random_state=42),"ridge":make_pipeline(StandardScaler(),Ridge(alpha=10.0))}
 m=models[name]
 return TransformedTargetRegressor(regressor=m,func=np.log1p,inverse_func=np.expm1) if log else m
names=["median_baseline","random_forest","extra_trees","gradient_boosting","ridge"]
report={"status":"EXPERIMENTAL_DEVELOPMENT_ONLY","design":"Fixed candidate algorithms. Existing train/validation memberships retained; test and purged rows excluded. Validation reused for development, not independent confirmation. No cross-well generalization claim.","target_transform":"log1p for permeability in mD; identity for porosity fraction. This is a declared new development configuration, not directly the previous log10 configuration.","sklearn":sklearn.__version__,"seed":42,"experiments":[]}
for old in previous["experiments"]:
 if old["status"]!="trained_experimental":continue
 key=old["dataset_id"];entry=catalog["datasets"][key];source=C.parent/entry["path"]
 assert sha(source)==entry["sha256"]==old["source_sha256"]
 ap=Path(old["artifact_directory"])/"assignments.csv";assert sha(ap)==old["artifact_sha256"]["assignments.csv"]
 assignments=pd.read_csv(ap);assert not assignments.specimen_id.duplicated().any()
 data=pd.read_csv(source).set_index("specimen_id",drop=False)
 trainids=assignments.loc[assignments.partition.eq("train"),"specimen_id"]
 validids=assignments.loc[assignments.partition.eq("validation"),"specimen_id"]
 testids=set(assignments.loc[assignments.partition.eq("test"),"specimen_id"])
 assert not (set(trainids)|set(validids))&testids
 tr=data.loc[trainids];va=data.loc[validids];features=entry["feature_columns"];target=entry["target_column"]
 assert np.isfinite(tr[features+[target]]).all().all() and np.isfinite(va[features+[target]]).all().all()
 folder=O/key.replace(":","_");folder.mkdir()
 assignments[assignments.partition.isin(["train","validation"])].to_csv(folder/"DEVELOPMENT_ASSIGNMENTS.csv",index=False)
 log="permeability" in entry["target_definition"]
 scores={};preds=va[["specimen_id",target]].copy()
 for name in names:
  m=create(name,log);m.fit(tr[features],tr[target]);pred=m.predict(va[features]);assert np.isfinite(pred).all()
  scores[name]={"mae":float(mean_absolute_error(va[target],pred)),"rmse":float(np.sqrt(mean_squared_error(va[target],pred))),"r2":float(r2_score(va[target],pred)) if va[target].var()>0 else None,"out_of_physical_range":int(((pred<0)|(pred>1)).sum()) if not log else int((pred<0).sum())}
  preds[name]=pred
  artifact={"model":m,"feature_columns":features,"target":entry["target_definition"],"condition":entry["condition"],"unit":entry["constant_columns"]["target_unit"],"status":"experimental_not_promoted","test_used":False,"target_transform":"log1p embedded in model" if log else "identity"}
  joblib.dump(artifact,folder/(name+".joblib"));loaded=joblib.load(folder/(name+".joblib"));assert np.allclose(pred,loaded["model"].predict(va[features]))
 preds.to_csv(folder/"VALIDATION_PREDICTIONS.csv",index=False)
 eligible=[n for n in names if scores[n]["out_of_physical_range"]==0]
 best=min(eligible,key=lambda n:scores[n]["mae"])
 result={"dataset_id":key,"name":entry["name"],"train_rows":len(tr),"validation_rows":len(va),"test_rows_not_used":len(testids),"scores":scores,"selected_by_validation_mae":best,"validation_mae_reduction_vs_baseline_percent":100*(1-scores[best]["mae"]/scores["median_baseline"]["mae"]) if scores["median_baseline"]["mae"] else 0,"source_sha256":sha(source),"assignments_sha256":sha(ap),"artifact_reload_verified":True,"artifact_directory":str(folder),"production_eligible":False}
 result["artifact_sha256"]={p.name:sha(p) for p in folder.glob("*.joblib")}
 (folder/"MODEL_COMPARISON.json").write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
 report["experiments"].append(result)
 print(json.dumps({"name":result["name"],"selected":best,"validation_mae":scores[best]["mae"],"baseline_mae":scores["median_baseline"]["mae"]}),flush=True)
 (O/"REPORT.json").write_text(json.dumps(report,indent=2,allow_nan=False),encoding="utf-8")
lines=["# Porosity and permeability development comparison","",report["design"],"",report["target_transform"],"","| Dataset | Lowest validation MAE candidate | MAE | Baseline MAE |","|---|---|---:|---:|"]
for e in report["experiments"]:
 n=e["selected_by_validation_mae"];lines.append(f"| {e['name']} | {n} | {e['scores'][n]['mae']:.5g} | {e['scores']['median_baseline']['mae']:.5g} |")
lines += ["","Permeability errors are in mD; porosity errors are fractions. Do not aggregate errors across units or laboratory conditions. Some validation sets contain only a few samples; algorithm selection can overfit these sets. All candidates were fitted only on original training rows; validation was not added to their fitting data. Candidates with out-of-range validation predictions were excluded from selection, but this does not guarantee valid outputs elsewhere. Test scores have intentionally not been recomputed. No artifact was imported into production."]
(O/"README.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps({"experiments":len(report["experiments"]),"saved_models":len(report["experiments"])*len(names),"selected_counts":dict(collections.Counter(e["selected_by_validation_mae"] for e in report["experiments"]))}))
