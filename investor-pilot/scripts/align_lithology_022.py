from pathlib import Path
import csv,json,hashlib,collections
import numpy as np
import pandas as pd
import lasio
B=Path(r"E:\PETROEDGE_AI\codex")
OUT=B/"data/prepared/lithology_alignment_022"
OUT.mkdir(parents=True,exist_ok=False)
source=B/"data/prepared/label_candidates_021/KNOWN_LITHOLOGY_INTERVALS.csv"
labels=pd.read_csv(source)
ledger=[];audits=[]
features={"LFP_GR":"API","LFP_NPHI":"v/v_decimal","LFP_RHOB_LOG":"g/cm3","LFP_RT":"ohm.m"}
for tag in ["A","BT2"]:
 well="NO 15/9-19 "+tag
 path=Path(r"F:\DATA_PETROEDGE_AI\Well_logs\06.LFP")/("15_9-19 "+tag)/("159-19"+tag+"_LFP.las")
 l=lasio.read(path);assert str(l.well.UWI.value)==well
 assert l.curves["DEPTH"].unit=="M" and "measured" in l.curves["DEPTH"].descr.lower()
 assert all(l.curves[k].unit==v for k,v in features.items())
 d=np.asarray(l["DEPTH"]);assert np.all(np.diff(d)>0)
 digest=hashlib.sha256(path.read_bytes()).hexdigest()
 subset=labels[labels.well.eq(well)]
 for sp,h in subset.groupby("source_path").source_sha256.first().items():assert hashlib.sha256(Path(sp).read_bytes()).hexdigest()==h
 for _,r in subset.iterrows():
  top=float(r.top_m);base=float(r.base_m);mid=(top+base)/2
  indexes=np.flatnonzero((d>=top)&(d<base))
  result={"well":well,"parent_group":"VOLVE_15_9_19_parent_and_sidetracks","label_code":r.label,"top_m":top,"base_m":base,"label_source":r.source_path,"label_sha256":r.source_sha256,"label_excel_row":int(r.excel_row),"log_source":str(path),"log_sha256":digest,"numerical_interval_samples":len(indexes),"training_ready":False,"depth_reference_status":"label_MD_reference_unconfirmed"}
  if not len(indexes):result.update(status="no_numerical_log_overlap")
  else:
   i=int(indexes[np.argmin(abs(d[indexes]-mid))]);result.update(log_row=i,log_depth_m=float(d[i]))
   for k in features:result[k]=float(l[k][i]) if np.isfinite(l[k][i]) else None
   flag=float(l["LFP_BADDATA"][i]);result["bad_data_flag"]=flag if np.isfinite(flag) else None
   valid=all(result[k] is not None for k in features)
   valid=valid and 0<=result["LFP_GR"]<=500 and 0<=result["LFP_NPHI"]<=1 and 1<=result["LFP_RHOB_LOG"]<=4 and result["LFP_RT"]>0 and flag==0
   result.update(status="numerical_candidate_pending_label_reference_and_provenance" if valid else "log_QC_hold")
  ledger.append(result)
 audits.append({"well":well,"log_sha256":digest,"log_depth_reference":l.curves["DEPTH"].descr,"log_unit":l.curves["DEPTH"].unit,"label_intervals":len(subset),"log_depth_range":[float(d.min()),float(d.max())]})
frame=pd.DataFrame(ledger)
frame.to_csv(OUT/"ALIGNMENT_REVIEW.csv",index=False)
c=frame[frame.status.eq("numerical_candidate_pending_label_reference_and_provenance")].copy()
c["shared_log_row"]=c.duplicated(["well","log_row"],keep=False)
c.to_csv(OUT/"NUMERICAL_CANDIDATES_NOT_TRAINING_APPROVED.csv",index=False)
summary={"wells":audits,"status_counts":frame.status.value_counts().to_dict(),"candidate_label_counts":c.label_code.value_counts().to_dict(),"shared_log_row_candidates":int(c.shared_log_row.sum()),"models_trained":0,"blockers":["Workbook gives metre units without confirmed MD/TVD reference or datum","SFINX interpretation provenance and codebook need verification; labels could be log-derived","Both branches belong to one parent well, not independent train/test wells"],"input_sha256":hashlib.sha256(source.read_bytes()).hexdigest()}
(OUT/"SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
(OUT/"README.md").write_text("# Lithology/log alignment review\n\n"+json.dumps(summary,indent=2)+"\n\nCandidate matching uses interval inclusion [top, base), selects the sample nearest the midpoint, and requires finite GR/neutron/raw density/resistivity with an explicit zero bad-data flag. Numerical overlap is not evidence of matching depth datum. These files are review artifacts and cannot be used as approved training data. No original data, existing models or production registry changed.\n",encoding="utf-8")
assert len(frame)==len(labels)
assert not frame.training_ready.any()
print(json.dumps(summary))
