"""Reproducible bounded pilot benchmarks. Never promotes an industrial model."""
from pathlib import Path
from io import BytesIO
import json, hashlib, zipfile, re, time, collections
import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import balanced_accuracy_score, f1_score, confusion_matrix, mean_absolute_error
B=Path(r"E:\PETROEDGE_AI\codex")
OUT=B/"models/investor_pilot_044"
OUT.mkdir(exist_ok=False)
def digest(data):return hashlib.sha256(data).hexdigest()
def save(name,data):
 (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False),encoding="utf-8")
def partition(well):
 n=int(digest(well.encode())[:8],16)%10
 return "train" if n<6 else "validation" if n<8 else "test"
protocol={"seed":44,"edge":{"design":"Real WELL files only; at most 16 hash-selected files per archive event folder, selection before reading labels. Entire parent well assigned by SHA256 modulo 10: train 0-5, validation 6-7, test 8-9. Source duplicates excluded.","features":["P-TPT","T-TPT","P-MON-CKP","T-JUS-CKP"],"window":"Current values, trailing 60-second mean and std (min 30 observations); no future inputs. Sample every 60 source rows; at most 2000 evenly selected valid rows per file.","labels":"0=normal, classes 1-9=event; null/transition >=100 excluded. Binary detection only, not event subtype or early warning.","model":"RandomForest 64 trees depth8 leaf10 balanced seed44 n_jobs1; majority baseline; no hyperparameter tuning","production_eligible":False},"twin":{"design":"GAB18 CSV, fixed 60/20/20 chronological target partitions. Past 3 oil rates predict next observed oil rate. Ridge alpha10, log1p target/features, train-only scaling. Compare last observed rate. No fitted reservoir physics or multi-step forecast.","production_eligible":False}}
save("PROTOCOL.json",protocol)
# Existing independent-well qualification: preserve every prior partition and source.
catpath=B/"data/prepared/platform_manifest_001.json";cat=json.loads(catpath.read_text())
qualification=[]
for key,e in cat["datasets"].items():
 src=catpath.parent/e["path"]
 assert digest(src.read_bytes())==e["sha256"]
 parts=Path(e["path"]).parts;well=parts[1]
 parent="FREEMAN-4" if well.startswith("FREEMAN-4") else "NO_15_9-19" if well.startswith("NO_15_9-19") else well
 qualification.append({"dataset_id":key,"well":well,"parent_well":parent,"target":e["target_definition"],"condition":e["condition"],"rows":e["rows"],"sha256":e["sha256"],"quality_approved":e["quality_approved"],"blocker":e.get("blocked_reason")})
save("REGRESSION_QUALIFICATION.json",{"datasets":qualification,"production_eligible":False,"decision":"No newly qualified independent parent well in prepared catalog. Freeman sidetracks and Volve branches are not independent parent wells. Do not repurpose previously evaluated test rows or mix laboratory conditions. Existing models remain research only."})
archive=Path(r"F:\DATA_PETROEDGE_AI\VOLVE AND OTHER DATA\3w_dataset_2.0.0.zip")
features=protocol["edge"]["features"];records=[];manifest=[];seen=set()
with zipfile.ZipFile(archive) as z:
 names=[i.filename for i in z.infolist() if re.fullmatch(r"[0-9]/WELL-[^/]+\.parquet",i.filename)]
 chosen=[]
 for category in sorted(set(n.split("/")[0] for n in names)):
  chosen+=sorted([n for n in names if n.startswith(category+"/")],key=lambda n:digest(n.encode()))[:16]
 save("EDGE_SOURCE_SELECTION.json",chosen)
 for i,name in enumerate(chosen):
  blob=z.read(name);sha=digest(blob);well=name.split("/")[1].split("_")[0];part=partition(well)
  info={"member":name,"sha256":sha,"well":well,"partition":part,"rows_used":0}
  if sha in seen: info["excluded"]="duplicate payload";manifest.append(info);continue
  seen.add(sha)
  f=pd.read_parquet(BytesIO(blob));f.index=pd.to_datetime(f.index)
  if not f.index.is_monotonic_increasing or f.index.has_duplicates:info["excluded"]="unordered or duplicate timestamps";manifest.append(info);continue
  x=f.reindex(columns=features).apply(pd.to_numeric,errors="coerce")
  roll=x.rolling("60s",min_periods=30)
  a=pd.concat([x.add_suffix("_current"),roll.mean().add_suffix("_mean60s"),roll.std().add_suffix("_std60s")],axis=1)
  a["label"]=pd.to_numeric(f["class"],errors="coerce");a=a.iloc[::60]
  a=a[np.isfinite(a).all(axis=1)&a.label.between(0,9)]
  if len(a)>2000:a=a.iloc[np.linspace(0,len(a)-1,2000,dtype=int)]
  a["label"]=(a.label>0).astype(int);a["well"]=well;a["partition"]=part;a["member"]=name
  info["rows_used"]=len(a);manifest.append(info)
  if len(a):records.append(a)
  if i%15==0:print("Edge files",i+1,"/",len(chosen),flush=True)
assert records,"No complete sensor windows"
d=pd.concat(records);cols=[c for c in d if c not in ["label","well","partition","member"]]
assert all(len(set(d.loc[d.partition==a,"well"])&set(d.loc[d.partition==b,"well"]))==0 for a,b in [("train","validation"),("train","test"),("validation","test")])
train=d[d.partition=="train"];assert train.label.nunique()==2
model=RandomForestClassifier(n_estimators=64,max_depth=8,min_samples_leaf=10,class_weight="balanced",random_state=44,n_jobs=1).fit(train[cols],train.label)
baseline=DummyClassifier(strategy="most_frequent").fit(train[cols],train.label)
edge={"name":"3W real-event detector","mode":"experimental_binary_event_detection","production_eligible":False,"features":cols,"source_archive":archive.name,"selection_files":len(chosen),"manifest":manifest,"metrics":{},"limitations":["Bounded real-file subset, not the full 3W benchmark.","Not a GRU; random forest baseline uses causal sensor windows.","Missing sensors withhold prediction. Native 3W sensor conventions only.","No field latency, false alarms/day or early-warning qualification.","Measured classification scores do not establish probability calibration."]}
for part in ["train","validation","test"]:
 v=d[d.partition==part];assert len(v) and v.label.nunique()==2,(part,len(v))
 pred=model.predict(v[cols]);bp=baseline.predict(v[cols])
 edge["metrics"][part]={"rows":len(v),"wells":int(v.well.nunique()),"macro_f1":float(f1_score(v.label,pred,average="macro")),"balanced_accuracy":float(balanced_accuracy_score(v.label,pred)),"baseline_macro_f1":float(f1_score(v.label,bp,average="macro")),"confusion_matrix":confusion_matrix(v.label,pred,labels=[0,1]).tolist()}
 if part=="test":
  result=v[["well","member","label"]].copy();result["prediction"]=pred;result.to_csv(OUT/"EDGE_TEST_PREDICTIONS.csv")
  sample=v.iloc[:500];t=time.perf_counter();pred=model.predict(sample[cols]);elapsed=time.perf_counter()-t
  edge["replay"]=[{"sample":i,"timestamp":str(ts),"actual":int(a),"prediction":int(b)} for i,(ts,a,b) in enumerate(zip(sample.index,sample.label,pred))]
  edge["local_batch_ms_per_row"]=elapsed*1000/len(sample)
  edge["runtime_note"]="Measured on development computer; not edge-device benchmark"
joblib.dump(model,OUT/"edge_real_events.joblib")
assert np.array_equal(joblib.load(OUT/"edge_real_events.joblib").predict(train[cols].iloc[:50]),model.predict(train[cols].iloc[:50]))
edge["artifact_sha256"]=digest((OUT/"edge_real_events.joblib").read_bytes());edge["artifact_bytes"]=(OUT/"edge_real_events.joblib").stat().st_size
edge["artifact_retained"]=all(edge["metrics"][part]["macro_f1"]>edge["metrics"][part]["baseline_macro_f1"] for part in ["validation","test"])
if not edge["artifact_retained"]:
 (OUT/"edge_real_events.joblib").unlink()
 edge["decision"]="Rejected: held-out performance below baseline. Fitted binary removed."
save("EDGE_REPORT.json",edge)
# Real production history with chronological backtest.
p=Path(r"F:\DATA_PETROEDGE_AI\AI WITH TOTAL E&P DATA\Production_Data\Gab18_4.csv")
f=pd.read_csv(p,skiprows=1);f["date"]=pd.to_datetime(pd.to_numeric(f.Date,errors="coerce"),unit="D",origin="1899-12-30")
f["rate"]=pd.to_numeric(f["Qoil(STB/d)"],errors="coerce");f=f.sort_values("date")
assert not f.date.duplicated().any()
for lag in [1,2,3]:f[f"lag{lag}"]=f.rate.shift(lag)
usable=f.dropna(subset=["date","rate","lag1","lag2","lag3"]);usable=usable[(usable[["rate","lag1","lag2","lag3"]]>=0).all(axis=1)]
n=len(usable);assert n>=30
cut1=int(n*.6);cut2=int(n*.8);xx=["lag1","lag2","lag3"]
reg=make_pipeline(StandardScaler(),Ridge(alpha=10)).fit(np.log1p(usable.iloc[:cut1][xx]),np.log1p(usable.iloc[:cut1].rate))
twin={"name":"GA-18/4_IIA production history and backtest","mode":"historical_data_twin_not_reservoir_simulator","source_sha256":digest(p.read_bytes()),"source_file":p.name,"unit":"STB/d","production_eligible":False,"metrics":{},"history":[],"limitations":["Excel serial dates interpreted with 1899-12-30 origin.","Forecast is next observed report, not a fixed daily horizon.","Rolling one-step evaluation uses observed preceding rates; not a blind multi-step forecast.","No pressure/PVT history match, intervention model or reserves estimate."]}
for part,lo,hi in [("train",0,cut1),("validation",cut1,cut2),("test",cut2,n)]:
 v=usable.iloc[lo:hi];pred=np.maximum(0,np.expm1(reg.predict(np.log1p(v[xx]))))
 twin["metrics"][part]={"rows":len(v),"mae":float(mean_absolute_error(v.rate,pred)),"persistence_mae":float(mean_absolute_error(v.rate,v.lag1)),"first_date":str(v.date.min().date()),"last_date":str(v.date.max().date())}
 for date,actual,pp,last in zip(v.date,v.rate,pred,v.lag1):twin["history"].append({"date":str(date.date()),"actual":float(actual),"prediction":float(pp),"baseline":float(last),"partition":part})
twin["candidate_beats_persistence"]=all(twin["metrics"][a]["mae"]<twin["metrics"][a]["persistence_mae"] for a in ["validation","test"])
if twin["candidate_beats_persistence"]:joblib.dump(reg,OUT/"twin_rate_ridge.joblib")
save("TWIN_REPORT.json",twin)
save("SUMMARY.json",{"edge":edge["metrics"],"twin":twin["metrics"],"twin_beats_baseline":twin["candidate_beats_persistence"],"production_eligible":False,"complete":True})
print(json.dumps(json.loads((OUT/"SUMMARY.json").read_text()),indent=2),flush=True)
