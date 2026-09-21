from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
import lasio
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score,balanced_accuracy_score,confusion_matrix
B=Path(r"E:\PETROEDGE_AI\codex");PREV=B/"models/lithology_development_025";O=B/"models/lithology_robustness_026"
O.mkdir(parents=True,exist_ok=False)
f=pd.read_csv(PREV/"DEVELOPMENT_DATA.csv");report=json.loads((PREV/"REPORT.json").read_text())
assert hashlib.sha256((PREV/"DEVELOPMENT_DATA.csv").read_bytes()).hexdigest()==report["dataset_sha256"]
assert not set(f.well)&set(report["prior_test_wells_not_used"])
shifts=[-3,-1,-.5,0,.5,1,3];values={shift:np.full(len(f),np.nan) for shift in shifts};source_hashes={}
for source,group in f.groupby("log_source"):
 p=Path(source);digest=hashlib.sha256(p.read_bytes()).hexdigest();assert set(group.log_sha256)=={digest};source_hashes[source]=digest
 l=lasio.read(p);unit=l.curves[0].unit.upper();assert unit in ["F","FT","FEET","M"]
 d=np.asarray(l.index,dtype=float)*(3.280839895013123 if unit=="M" else 1)
 for channel,g in group.groupby("log_channel"):
  assert l.curves[channel].unit.upper()=="API"
  v=np.asarray(l[channel],dtype=float);valid=np.isfinite(d)&np.isfinite(v)&(v>=0)&(v<=500)
  dd=d[valid];vv=v[valid]
  for shift in shifts:
   for idx,r in g.iterrows():
    target=r.sidewall_depth_raw+shift;i=int(np.argmin(abs(dd-target)))
    if abs(dd[i]-target)<=.82:values[shift][idx]=vv[i]
 print('Read',p.name,flush=True)
# Fixed common rows for all scenarios prevents changing sample coverage between comparisons.
common=np.logical_and.reduce([np.isfinite(v) for v in values.values()]);data=f.loc[common].copy()
assert len(data)>=50
results=[];preds=[]
for shift in shifts:
 x=values[shift][common];y=data.label.to_numpy();wells=data.well.to_numpy();out=np.empty(len(y),dtype=object)
 for held in sorted(set(wells)):
  tr=wells!=held;va=~tr;assert set(y[tr])=={"sand","shale"}
  m=RandomForestClassifier(n_estimators=128,max_depth=5,min_samples_leaf=5,class_weight="balanced",random_state=42,n_jobs=1)
  m.fit(x[tr,None],y[tr]);out[va]=m.predict(x[va,None])
 results.append(dict(shift_ft=shift,rows=len(y),macro_f1=float(f1_score(y,out,labels=["sand","shale"],average="macro",zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(y,out)),confusion_matrix=confusion_matrix(y,out,labels=["sand","shale"]).tolist()))
 part=data[["well","sample_number","label"]].copy();part["shift_ft"]=shift;part["prediction"]=out;preds.append(part)
 print(json.dumps(results[-1]),flush=True)
predictions=pd.concat(preds);predictions.to_csv(O/"SENSITIVITY_PREDICTIONS.csv",index=False)
# Cluster bootstrap of baseline OOF results: resample wells, never individual correlated rows.
base=predictions[predictions.shift_ft.eq(0)];rng=np.random.default_rng(42);wells=sorted(base.well.unique());scores=[]
for _ in range(2000):
 sample=pd.concat([base[base.well.eq(w)] for w in rng.choice(wells,size=len(wells),replace=True)])
 if sample.label.nunique()<2:continue
 scores.append(f1_score(sample.label,sample.prediction,labels=["sand","shale"],average="macro",zero_division=0))
summary=dict(status="CONDITIONAL_DEVELOPMENT_ROBUSTNESS_ONLY",assumption=report["assumption"],design="Predefined shifts; each scenario retrains the same fixed forest in leave-one-development-well-out folds. No scenario chosen as a correction or new preferred model. Does not confirm feet, MD or datum.",source_rows=len(f),common_rows=int(common.sum()),excluded_for_incomplete_shift_coverage=int((~common).sum()),development_wells=wells,excluded_prior_test_wells=report["prior_test_wells_not_used"],results=results,well_cluster_bootstrap=dict(replicates=2000,valid_replicates=len(scores),macro_f1_percentile_95=np.quantile(scores,[.025,.975]).tolist(),caution="Only four development wells; exploratory uncertainty range is unstable and not a population performance guarantee. Single-class draws excluded."),source_hashes=source_hashes,production_eligible=False)
(O/"REPORT.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
lines=["# Lithology depth sensitivity", "",summary["design"],"",summary["assumption"],"",f"Common samples across scenarios: {len(data)} of {len(f)}. Prior test wells excluded.","","| Shift in feet | Macro F1 | Balanced accuracy |","|---|---:|---:|"]
for r in results:lines.append(f"| {r['shift_ft']} | {r['macro_f1']:.4f} | {r['balanced_accuracy']:.4f} |")
lines += ["", "Well-cluster bootstrap summary: "+json.dumps(summary["well_cluster_bootstrap"]),"", "No model promoted. Sensitivity within a few feet does not establish the missing source depth convention or accuracy on a new field. No test labels were used."]
(O/"README.md").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps({k:v for k,v in summary.items() if k not in ["source_hashes","results"]}))
