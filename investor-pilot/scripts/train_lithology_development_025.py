from pathlib import Path
import json,hashlib
import pandas as pd
import numpy as np
import lasio,joblib,sklearn
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.dummy import DummyClassifier
from sklearn.metrics import f1_score,balanced_accuracy_score,confusion_matrix
B=Path(r"E:\PETROEDGE_AI\codex");P=B/"models/field_x_conditional_024";O=B/"models/lithology_development_025"
O.mkdir(parents=True,exist_ok=False)
old=json.loads((P/"REPORT.json").read_text());source=pd.read_csv(P/"CONDITIONAL_DATASET.csv")
# Prior test wells are excluded before feature extraction, fitting or evaluation.
f=source[source.partition.isin(["train","validation"]) & source.label.isin(["sand","shale"])].copy().reset_index(drop=True)
assert not set(f.well)&{w for w,v in old["well_assignments"].items() if v=="test"}
RAW=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X")
metadata=pd.read_excel(RAW/"Well Header Location/WELLBORE HEADER INFO_DFE.xlsx").set_index("Wellbore Name").to_dict("index")
specs={"sonic_us_ft":({"BCSL","DT","DTC"},{"US/F","US/FT"},30,250,10),"density_g_cm3":({"FDC","RHOB"},{"G/C3","G/CC","G/CM3"},1,4,.1),"sp_mv":({"SP"},{"MV"},-500,500,10)}
logs=[];audit=[]
for well in sorted(f.well.unique()):
 for p in sorted((RAW/"X_FIELD_Well logs"/well).glob("*.las")):
  try:
   header=lasio.read(p,ignore_data=True)
   names={str(x.value).strip().upper() for x in header.well if x.mnemonic.split(":")[0]=="WELL"}
   if names!={well}:continue
   if str(header.well.LMF.value).strip()!="DF" or str(header.well.EDF.unit).lower() not in ["feet","ft","f"]:continue
   if abs(float(header.well.EDF.value)-float(metadata[well]["Depth Reference Elevation"]))>.1:continue
   depth_unit=header.curves[0].unit.upper()
   if depth_unit not in ["F","FT","FEET","M"]:continue
   usable={feature:[c.mnemonic for c in header.curves if c.mnemonic in nameset and c.unit.upper() in units] for feature,(nameset,units,lo,hi,tol) in specs.items()}
   usable={k:v[0] for k,v in usable.items() if len(v)==1}
   if not usable:continue
   l=lasio.read(p);d=np.asarray(l.index,dtype=float)*(3.280839895013123 if depth_unit=="M" else 1)
   digest=hashlib.sha256(p.read_bytes()).hexdigest()
   for feature,channel in usable.items():
    vals=np.asarray(l[channel],dtype=float);lo,hi=specs[feature][2:4];good=np.isfinite(d)&np.isfinite(vals)&(vals>=lo)&(vals<=hi)
    if good.any():logs.append(dict(well=well,feature=feature,depth=d[good],value=vals[good],path=str(p),sha256=digest,channel=channel))
  except Exception as e:audit.append(dict(source=str(p),status="read_error",reason=str(e)))
 print("Profiled development well",well,flush=True)
for feature in specs:
 f[feature]=np.nan
 for i,r in f.iterrows():
  choices=[]
  for l in logs:
   if l["well"]!=r.well or l["feature"]!=feature:continue
   j=int(np.argmin(abs(l["depth"]-r.sidewall_depth_raw)));delta=abs(l["depth"][j]-r.sidewall_depth_raw)
   if delta<=.82:choices.append((delta,l["path"],float(l["value"][j]),l))
  status="unavailable"
  if choices:
   if max(c[2] for c in choices)-min(c[2] for c in choices)>specs[feature][4]:status="acquisitions_disagree"
   else:
    c=min(choices,key=lambda x:(x[0],x[1]));f.at[i,feature]=c[2];status="matched"
    audit.append(dict(well=r.well,sample_number=r.sample_number,feature=feature,status=status,source=c[1],source_sha256=c[3]["sha256"],channel=c[3]["channel"],distance_ft=c[0]));continue
  audit.append(dict(well=r.well,sample_number=r.sample_number,feature=feature,status=status))
features=["gr_api"]+list(specs)
f.to_csv(O/"DEVELOPMENT_DATA.csv",index=False);pd.DataFrame(audit).to_csv(O/"FEATURE_MATCH_AUDIT.csv",index=False)
# Fixed candidates, no hyperparameter search; fold-local preprocessing only.
def factory(name):
 if name=="majority":return DummyClassifier(strategy="most_frequent")
 if name=="logistic_multi":return make_pipeline(SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True),StandardScaler(),LogisticRegression(class_weight="balanced",max_iter=2000,random_state=42))
 return make_pipeline(SimpleImputer(strategy="median",add_indicator=True,keep_empty_features=True),RandomForestClassifier(n_estimators=128,max_depth=5,min_samples_leaf=5,class_weight="balanced",random_state=42,n_jobs=1))
def metrics(y,p):return dict(macro_f1=float(f1_score(y,p,labels=["sand","shale"],average="macro",zero_division=0)),balanced_accuracy=float(balanced_accuracy_score(y,p)),confusion_matrix=confusion_matrix(y,p,labels=["sand","shale"]).tolist())
results={};allpred=[]
for name in ["majority","forest_gr","forest_multi","logistic_multi"]:
 fs=["gr_api"] if name in ["majority","forest_gr"] else features
 folds=[];predictions=[]
 for held in sorted(f.well.unique()):
  train=f[f.well.ne(held)];val=f[f.well.eq(held)]
  assert train.label.nunique()==2
  m=factory(name);m.fit(train[fs],train.label);pred=m.predict(val[fs])
  part=val[["well","sample_number","label"]].copy();part["prediction"]=pred;part["model"]=name;predictions.append(part)
  folds.append(dict(held_well=held,rows=len(val),class_counts=val.label.value_counts().to_dict(),**metrics(val.label,pred)))
 joined=pd.concat(predictions);allpred.append(joined)
 results[name]=dict(pooled_out_of_well=metrics(joined.label,joined.prediction),folds=folds)
 print(name,results[name]["pooled_out_of_well"],flush=True)
 m=factory(name);m.fit(f[fs],f.label)
 artifact=dict(model=m,features=fs,classes=["sand","shale"],status="conditional_development_only",assumption=old["assumption"],training_wells=sorted(f.well.unique()))
 joblib.dump(artifact,O/(name+".joblib"));loaded=joblib.load(O/(name+".joblib"));assert np.array_equal(m.predict(f[fs]),loaded["model"].predict(f[fs]))
pd.concat(allpred).to_csv(O/"OUT_OF_WELL_DEVELOPMENT_PREDICTIONS.csv",index=False)
report=dict(status="CONDITIONAL_DEVELOPMENT_ONLY",assumption=old["assumption"],target="sand versus shale only; clay excluded, no clay prediction claim",development_rows=len(f),well_class_counts={w:g.label.value_counts().to_dict() for w,g in f.groupby("well")},feature_coverage={c:int(f[c].notna().sum()) for c in features},prior_test_wells_not_used=[w for w,v in old["well_assignments"].items() if v=="test"],evaluation="Leave one development well out. Not a fresh independent final test. Single-class fold metrics must not be read as general discrimination.",results=results,models_saved=4,artifact_reload_verified=True,production_eligible=False,sklearn=sklearn.__version__)
report["artifact_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob("*.joblib")}
(O/"REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
(O/"README.md").write_text("# Lithology development comparison\n\n"+json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps({k:v for k,v in report.items() if k not in ["results","artifact_sha256"]}))
