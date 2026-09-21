from pathlib import Path
import hashlib,json,platform
import numpy as np
import pandas as pd
import sklearn,joblib
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
B=Path(r"E:\PETROEDGE_AI\codex")
O=B/"models/core_saturation_031"
O.mkdir(parents=True,exist_ok=False)
E=B/"data/prepared/saturation_evidence_031"
source=B/"data/prepared/saturation_030/CORE_SATURATION_REVIEW.csv"
pdf=Path(r"F:\DATA_PETROEDGE_AI\Well_logs\09.CORE\15_9-19 A\15-9-19a-core.pdf")
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
d=pd.read_csv(source).sort_values(["core_depth_m","specimen_id"]).reset_index(drop=True)
assert len(d)==71 and d.specimen_id.is_unique
for pathcol,hashcol in [("source_path","source_sha256"),("log_source","log_sha256")]:
 for path,g in d.groupby(pathcol):assert g[hashcol].nunique()==1 and sha(path)==g[hashcol].iloc[0]
features=["gr_api","bulk_density_g_cm3","neutron_porosity_v_v","resistivity_ohm_m"]
targets=["core_water_fraction","core_oil_fraction"]
assert np.isfinite(d[features+targets].to_numpy()).all()
assert d.numerical_alignment_status.eq("candidate").all()
assert d[targets].ge(0).all().all() and d[targets].le(1).all().all()
assert d.bad_data_flag.eq(0).all() and d.depth_delta_m.le(.25).all()
# Conservative exclusions based on visually inspected tracer table, PDF page 67.
nmp=[3862.82,3868.91,3869.91,3870.92,3871.88]
d["exclusion_reason"]=""
d.loc[d.core_depth_m.round(2).isin(nmp),"exclusion_reason"]="Tracer measurement marked nmp; assigned invasion value not independently measured"
d.loc[d.core_depth_m.round(2).eq(3873.94),"exclusion_reason"]="Printed tracer activity 3.47/93.5 conflicts with listed 6.5 percent invasion; unresolved source inconsistency"
assert d.exclusion_reason.ne("").sum()==6
d["split"]=d.core_number.map({1:"train",2:"train",3:"validation",4:"test"})
assert d.split.notna().all()
d.loc[d.exclusion_reason.ne(""),"split"]="excluded"
parts={s:d[d.split.eq(s)].copy() for s in ["train","validation","test"]}
assert all(len(v)>=10 for v in parts.values())
# Require physical separation in both core and aligned log depth.
for left,right in [("train","validation"),("validation","test")]:
 for col in ["core_depth_m","log_depth_m"]:assert parts[right][col].min()-parts[left][col].max()>1.0
for a,b in [("train","validation"),("train","test"),("validation","test")]:
 assert set(parts[a].specimen_id).isdisjoint(parts[b].specimen_id)
 assert set(parts[a].core_number).isdisjoint(parts[b].core_number)
 assert set(parts[a].log_depth_m).isdisjoint(parts[b].log_depth_m)
# Four source spot checks (PDF page 15); not a full re-transcription of 71 rows.
for depth,so,sw in [(3837.88,.529,.364),(3838.92,.725,.110),(3839.92,.239,.524),(3840.94,.616,.217)]:
 r=d.loc[d.core_depth_m.round(2).eq(depth)].iloc[0]
 assert abs(r.core_oil_fraction-so)<1e-9 and abs(r.core_water_fraction-sw)<1e-9
limitations=[
"Experimental reproduction of reported recovered-core laboratory values, not established in-situ saturation truth.",
"One parent well; whole-core interval split is not independent-well or Nigerian validation.",
"Dean-Stark water measured directly; oil inferred from weight loss using density 0.850 g/cc.",
"Report describes water invasion correction but worksheet row-level correction arithmetic has not been reconstructed; target remains reported workbook water fraction.",
"Oil values are not invasion-corrected; offshore plug drilling used Isopar L oil.",
"Five unmeasurable tracer rows and one inconsistent tracer row excluded conservatively.",
"No measured gas target; unaccounted pore fraction is not gas. No three-phase normalization.",
"Small validation/test sets, depth-domain shift and shared well limit all metrics.",
"No Rw at reservoir temperature, Archie calibration, DT input or missing-curve support established here.",
"Test data are held from fitting and selection in this run; their descriptive source ranges were previously audited.",
"Source table calls the field Sleipner; project catalog groups files under Volve. Well identity is the join key; field naming needs reconciliation."
]
evidence={"source_pdf":str(pdf),"sha256":sha(pdf),"report_number":"10177-97","report_date":"1998-03-25","inspection":"Visual inspection of scanned PDF, one-based PDF page references",
"findings":[{"pages":[4],"finding":"Core depth datum MD RKB in metres."},{"pages":[5,6,9],"finding":"1.5-inch vertical saturation plugs drilled offshore with Isopar L; immediate cling film, aluminium film and ProtecCore laminate preservation. Whole-core wax preservation is a separate branch."},{"pages":[10],"finding":"Dean-Stark toluene extraction measures water volume; oil from weight loss with density 0.850 g/cc; salt correction to water; cores 5-7 not analyzed for saturation."},{"pages":[11],"finding":"Tracer-based mud-filtrate invasion correction described for water, assuming invading water displaces oil or gas; oil not corrected."},{"pages":[15],"finding":"Four workbook oil/water pairs spot-checked against conventional core table; pore saturation in percent; table field name Sleipner."},{"pages":[67,68],"finding":"Tracer invasion tables available. Five rows marked nmp; one printed activity/invasion inconsistency at depth 3873.94 m."},{"pages":[12,13,65],"finding":"Separate simulated-water formation-factor measurements exist; table provides Ro/Rw, not qualified reservoir-temperature Rw."}],"limitations":limitations}
(E/"EVIDENCE.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
d["label_scope"]="Reported conventional core oil/water fractions, method verified; experimental only"
d["training_approved"]=d.split.ne("excluded")
d["production_eligible"]=False
d.to_csv(O/"SPLIT_MANIFEST.csv",index=False)
protocol={"features":features,"feature_units":["API","g/cm3","v/v","ohm.m"],"targets":targets,"split":"Cores 1+2 train, core 3 validation, core 4 test; six tracer-QC exclusions","counts":{s:len(v) for s,v in parts.items()},"minimum_split_depth_gap_m":1,"selection":"Lowest validation MAE; median wins ties; no refit and no tuning after test","models":{"median":"DummyRegressor(strategy=median)","random_forest":"128 trees, min_samples_leaf=3, random_state=31, n_jobs=1"},"preprocessing":"None; finite complete four-curve input required. Raw recorded units; no target-derived features.","production_eligible":False,"limitations":limitations}
(O/"PROTOCOL.json").write_text(json.dumps(protocol,indent=2),encoding="utf-8")
def metrics(y,p):return {"mae_fraction":float(mean_absolute_error(y,p)),"mae_percentage_points":float(100*mean_absolute_error(y,p)),"rmse_fraction":float(np.sqrt(mean_squared_error(y,p))),"r2":float(r2_score(y,p))}
results=[]; predrows=[]; selected_predictions={}
for target in targets:
 candidates={"median":DummyRegressor(strategy="median"),"random_forest":RandomForestRegressor(n_estimators=128,min_samples_leaf=3,random_state=31,n_jobs=1)}
 vals={}; artifacts={}
 for name,model in candidates.items():
  model.fit(parts["train"][features],parts["train"][target])
  vp=model.predict(parts["validation"][features]); vals[name]=metrics(parts["validation"][target],vp)
  artifact=O/f"{target}_{name}.joblib"
  bundle={"model":model,"required_features":features,"target":target,"target_unit":"fraction of pore volume","scope":"reported recovered-core laboratory value","production_eligible":False,"limitations":limitations}
  joblib.dump(bundle,artifact)
  reloaded=joblib.load(artifact)
  np.testing.assert_allclose(reloaded["model"].predict(parts["validation"][features]),vp,rtol=0,atol=0)
  artifacts[name]={"path":str(artifact),"sha256":sha(artifact)}
  for (_,r),v in zip(parts["validation"].iterrows(),vp):predrows.append(dict(specimen_id=r.specimen_id,target=target,split="validation",model=name,observed=float(r[target]),predicted=float(v)))
 chosen=min(candidates,key=lambda n:vals[n]["mae_fraction"])
 # Final test consumed once after validation selection; selected model and fixed baseline only.
 tests={}
 for name in dict.fromkeys(["median",chosen]):
  tp=candidates[name].predict(parts["test"][features]); tests[name]=metrics(parts["test"][target],tp)
  assert np.isfinite(tp).all() and ((tp>=0)&(tp<=1)).all()
  if name==chosen:selected_predictions[target]=tp
  for (_,r),v in zip(parts["test"].iterrows(),tp):predrows.append(dict(specimen_id=r.specimen_id,target=target,split="test",model=name,observed=float(r[target]),predicted=float(v)))
 results.append(dict(target=target,selected_model=chosen,validation=vals,test=tests,artifacts=artifacts,production_eligible=False))
pd.DataFrame(predrows).to_csv(O/"PREDICTIONS.csv",index=False)
report={"status":"experimental_completed_not_production_qualified","protocol":protocol,"results":results,"source_review_sha256":sha(source),"evidence_sha256":sha(E/"EVIDENCE.json"),"split_sha256":sha(O/"SPLIT_MANIFEST.csv"),"script_sha256":sha(__file__),"python":platform.python_version(),"sklearn":sklearn.__version__,"verification":"source hashes, units/ranges, source spot checks, specimen/core/depth separation, finite predictions, and exact artifact reload predictions passed","selected_test_oil_plus_water_above_one":int((selected_predictions[targets[0]]+selected_predictions[targets[1]]>1).sum()),"gas_model_trained":False}
(O/"REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
lines=["# Experimental reported-core saturation training", "", "Production eligible: NO. These models reproduce laboratory core values; they do not establish in-situ three-phase saturation.","",f"Samples: {len(d)} audited; {sum(len(v) for v in parts.values())} included; 6 held for tracer QC.","",f"Split counts: {protocol['counts']}","", "| Target | Selected model | Validation MAE (percentage points) | Test MAE (percentage points) | Test median MAE |", "|---|---|---:|---:|---:|"]
for r in results:
 n=r["selected_model"];lines.append(f"| {r['target']} | {n} | {r['validation'][n]['mae_percentage_points']:.2f} | {r['test'][n]['mae_percentage_points']:.2f} | {r['test']['median']['mae_percentage_points']:.2f} |")
lines += ["", "## Limits", ""]+["- "+v for v in limitations]+["", "Four saved artifacts passed exact prediction reload checks. No application registry or production model was changed. PREDICTIONS.csv preserves observed and predicted fractions. SPLIT_MANIFEST.csv includes excluded rows and their reasons. Do not reuse test results for tuning; subsequent development needs a new independent evaluation plan."]
(O/"README.md").write_text("\n".join(lines),encoding="utf-8")
(E/"README.md").write_text("# Saturation source evidence\n\n"+json.dumps(evidence,indent=2),encoding="utf-8")
print(json.dumps({"counts":protocol["counts"],"results":[{"target":r["target"],"selected":r["selected_model"],"validation":r["validation"],"test":r["test"]} for r in results],"verification":report["verification"]},indent=2))
