from pathlib import Path
import json,hashlib,collections,re
import pandas as pd
import numpy as np
import lasio,openpyxl,joblib,sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,confusion_matrix
B=Path(r"E:\PETROEDGE_AI\codex");RAW=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X")
O=B/"models/field_x_conditional_024";O.mkdir(parents=True,exist_ok=False)
assumption="UNVERIFIED: sidewall depth interpreted as measured feet from drill floor, inferred from same-well header/survey metadata, not stated in sidewall sheet. Conditional experiment only."
sources={};logs=[];errors=[]
def digest(p):
 h=hashlib.sha256(p.read_bytes()).hexdigest();sources[str(p)]=h;return h
meta_path=RAW/"Well Header Location/WELLBORE HEADER INFO_DFE.xlsx";digest(meta_path)
meta=pd.read_excel(meta_path);metadata=meta.set_index("Wellbore Name").to_dict("index")
for p in sorted((RAW/"X_FIELD_Well logs").glob("*/*.las")):
 try:
  l=lasio.read(p)
  names={str(x.value).strip().upper() for x in l.well if x.mnemonic.split(":")[0]=="WELL"}
  if len(names)!=1:continue
  well=next(iter(names))
  if well not in metadata or metadata[well]["Total Depth Final Unit"]!="feet" or metadata[well]["Depth Reference Point"]!="DF":continue
  if "LMF" not in l.well or str(l.well.LMF.value).strip()!="DF":continue
  if "EDF" not in l.well or str(l.well.EDF.unit).lower() not in ["feet","ft","f"]:continue
  if abs(float(l.well.EDF.value)-float(metadata[well]["Depth Reference Elevation"]))>.1:continue
  unit=l.curves[0].unit.upper()
  if unit not in ["F","FT","FEET","M"]:continue
  gr=[c.mnemonic for c in l.curves if c.mnemonic in ["GR","GRS"] and c.unit.upper()=="API"]
  if len(gr)!=1:continue
  d=np.asarray(l.index,dtype=float)*(3.280839895013123 if unit=="M" else 1)
  v=np.asarray(l[gr[0]],dtype=float)
  good=np.isfinite(d)&np.isfinite(v)&(v>=0)&(v<=500)
  d=d[good];v=v[good]
  if not len(d):continue
  order=np.argsort(d);d=d[order];v=v[order]
  logs.append(dict(well=well,path=str(p),sha256=digest(p),channel=gr[0],depth=d,gr=v))
 except Exception as e:errors.append({"path":str(p),"error":str(e)})
records=[];seen=set()
for p in sorted((RAW/"SEDIMENTOLOGY").glob("*.xlsx")):
 h=digest(p);wb=openpyxl.load_workbook(p,read_only=True,data_only=True)
 for s in wb:
  it=iter(s.values);headers=[str(x or "").strip().lower() for x in next(it)]
  for rn,vals in enumerate(it,2):
   r=dict(zip(headers,vals));well=str(r.get("well_name","")).strip().upper();label=str(r.get("lithology","")).strip().lower()
   if label not in ["sand","shale","clay"]:continue
   try:depth=float(r["depth"])
   except (TypeError,ValueError,KeyError):continue
   identity=(well,str(r.get("sample_number")),depth)
   if identity in seen:continue
   seen.add(identity)
   row=dict(well=well,sample_number=r.get("sample_number"),sidewall_depth_raw=depth,label=label,source_path=str(p),source_sha256=h,sheet=s.title,excel_row=rn,assumption=assumption,status="no_exact_well_log_match")
   candidates=[]
   for l in logs:
    if l["well"]!=well:continue
    i=int(np.argmin(abs(l["depth"]-depth)));delta=abs(l["depth"][i]-depth)
    if delta<=.82:candidates.append((delta,l["path"],i,l))
   if candidates:
    _,_,i,l=min(candidates,key=lambda x:(x[0],x[1]));row.update(status="conditional_candidate",gr_api=float(l["gr"][i]),log_depth_ft=float(l["depth"][i]),distance_ft=float(abs(l["depth"][i]-depth)),log_source=l["path"],log_sha256=l["sha256"],log_channel=l["channel"],candidate_logs=len(candidates))
    # Hold back disagreements between equally plausible acquisitions, rather than silently choose.
    values=[c[3]["gr"][c[2]] for c in candidates]
    if max(values)-min(values)>10:row["status"]="multiple_logs_disagree_over_10_API"
   records.append(row)
 wb.close()
f=pd.DataFrame(records)
# No repeated same-well log sample may receive conflicting labels or enter partitions twice.
c=f[f.status.eq("conditional_candidate")].copy()
conflict=c.groupby(["well","log_depth_ft"]).label.transform("nunique").gt(1)
f.loc[c.index[conflict],"status"]="conflicting_labels_at_same_log_depth"
c=c[~conflict].drop_duplicates(["well","log_depth_ft"])
f.to_csv(O/"MATCH_AUDIT.csv",index=False)
summary={"status":"CONDITIONAL_EXPERIMENT_NOT_VALIDATED","assumption":assumption,"scope":"Single gamma-ray predictor baseline. Not a complete petrophysical classifier.","selected_log_files":len(logs),"audit_counts":f.status.value_counts().to_dict(),"candidate_rows":len(c),"wells":c.groupby("well").size().to_dict(),"labels":c.label.value_counts().to_dict(),"read_errors":errors,"models_trained":0,"sklearn":sklearn.__version__}
wells=sorted(c.well.unique())
if len(wells)>=5:
 n=len(wells);a=max(1,int(n*.6));b=max(a+1,int(n*.8));assign={w:("train" if i<a else "validation" if i<b else "test") for i,w in enumerate(wells)}
 c["partition"]=c.well.map(assign);c.to_csv(O/"CONDITIONAL_DATASET.csv",index=False)
 parts={k:c[c.partition.eq(k)] for k in ["train","validation","test"]}
 if all(len(v)>=10 for v in parts.values()) and parts["train"].label.nunique()>=2:
  assert c.groupby("well").partition.nunique().max()==1
  models={"majority_baseline":DummyClassifier(strategy="most_frequent"),"random_forest":RandomForestClassifier(n_estimators=128,max_depth=5,min_samples_leaf=5,class_weight="balanced",random_state=42,n_jobs=1)}
  classes=sorted(c.label.unique());scores={}
  def metrics(y,p):return dict(accuracy=float(accuracy_score(y,p)),balanced_accuracy=float(balanced_accuracy_score(y,p)),macro_f1=float(f1_score(y,p,labels=classes,average="macro",zero_division=0)),confusion_matrix=confusion_matrix(y,p,labels=classes).tolist())
  for name,m in models.items():
   m.fit(parts["train"][["gr_api"]],parts["train"].label)
   scores[name]=metrics(parts["validation"].label,m.predict(parts["validation"][["gr_api"]]))
   joblib.dump(dict(model=m,features=["gr_api"],assumption=assumption,status="conditional_experimental",classes=classes),O/(name+".joblib"))
  winner=max(scores,key=lambda k:scores[k]["macro_f1"])
  pred=models[winner].predict(parts["test"][["gr_api"]]);test=metrics(parts["test"].label,pred)
  out=parts["test"].copy();out["prediction"]=pred;out.to_csv(O/"TEST_PREDICTIONS.csv",index=False)
  loaded=joblib.load(O/(winner+".joblib"));assert np.array_equal(pred,loaded["model"].predict(parts["test"][["gr_api"]]))
  summary.update(models_trained=2,well_assignments=assign,partition_rows={k:len(v) for k,v in parts.items()},class_order=classes,validation=scores,selected_model=winner,test=test,artifact_reload_verified=True)
else:c.to_csv(O/"CONDITIONAL_DATASET.csv",index=False)
summary["source_hashes"]=sources
(O/"REPORT.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
(O/"README.md").write_text("# Field X conditional experiment\n\n"+assumption+"\n\n"+json.dumps({k:v for k,v in summary.items() if k not in ["source_hashes","read_errors"]},indent=2)+"\n\nWell grouping uses exact source identifiers, without inferred name aliases. No production approval or promotion. Evaluation is conditional on the unresolved sidewall depth convention and does not establish validated geological accuracy.\n",encoding="utf-8")
print(json.dumps({k:v for k,v in summary.items() if k not in ["source_hashes","read_errors"]}))
