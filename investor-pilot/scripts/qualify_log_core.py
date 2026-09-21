"""Prepare source-qualified log/core candidate tables; do not create random depth splits."""
import argparse,collections,csv,hashlib,json,math,re
from pathlib import Path
import numpy as np
import lasio
BASE=Path(r"E:\PETROEDGE_AI\codex\data")
AUDIT=BASE/"readiness/log_core_001"
OUT=BASE/"prepared/log_core_002"
FEATURE_MAP={
"GR_COMP":("gr_api","GAPI"),"GR":("gr_api","API"),
"RHOB_COMP":("bulk_density_g_cm3","G/C3"),"DEN":("bulk_density_g_cm3","G/CC"),
"NPHI_COMP":("neutron_porosity_v_v","V/V"),"NEUT":("neutron_porosity_v_v","FRAC"),
"RDEEP_COMP":("deep_resistivity_ohm_m","OHMM"),"RES_DEP":("deep_resistivity_ohm_m","OHMM"),
"DT_COMP":("compressional_slowness_us_ft","US/F"),"HCAL_COMP":("caliper_in","INCHES"),
"DRHO_COMP":("density_correction_g_cm3","G/C3")}
REQUIRED=["gr_api","bulk_density_g_cm3","neutron_porosity_v_v","deep_resistivity_ohm_m"]
def number(x):
 try:
  if isinstance(x,bool):return None
  v=float(x);return v if math.isfinite(v) and v not in [-999.25,-999,-9999] else None
 except (ValueError,TypeError):return None
def measurement(x):
 if str(x).strip()=="":return {"kind":"missing","value":None,"bound":None,"raw":x}
 m=re.fullmatch(r"\s*(<=|>=|<|>|≤|≥)\s*([0-9]+(?:\.[0-9]*)?(?:[eE][+-]?\d+)?)\s*",str(x))
 if m:return {"kind":"censored","value":None,"bound":float(m[2]),"operator":m[1],"raw":x}
 v=number(x)
 return {"kind":"exact" if v is not None else "non_numeric","value":v,"bound":None,"raw":x}
def canon_freeman(name):
 m=re.fullmatch(r"\s*:?\s*FREEMAN[- ]*0*(\d+)(?:[- ]*ST[- ]*0*(\d+))?\s*",str(name),re.I)
 return f"FREEMAN-{int(m[1])}"+(f"-ST{int(m[2])}" if m[2] else "") if m else None
def sid(x):return re.sub(r"\.0$","",str(x)).replace("*","").strip()
def at(row,c):return row[c-1] if len(row)>=c else ""
def source_hash(path):
 with Path(path).open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def outcsv(path,rows,columns=None):
 rows=list(rows);cols=columns or list(dict.fromkeys(k for r in rows for k in r))
 if not cols:cols=["record_id","status"]
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=True) if isinstance(v,(dict,list)) else v for k,v in r.items() if k in cols})
def jwrite(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=True),encoding="utf-8")
def loadbook(fragment,exclude="JULY"):
 for p in (AUDIT/"core_workbooks").glob("*.json"):
  b=json.loads(p.read_text())
  if fragment in b["source_path"] and exclude not in b["source_path"]:
   assert source_hash(b["source_path"])==b["sha256"],"Core source changed: "+b["source_path"]
   return b
 raise ValueError(fragment)
def sheet(book,name):return next(s["rows"] for s in book["sheets"] if s["name"]==name)
def loadlog(profile):
 assert source_hash(profile["source_path"])==profile["sha256"],"Log source changed"
 las=lasio.read(profile["source_path"],engine="numpy")
 unit=las.curves[0].unit.strip().upper()
 if unit not in {"M","F","FT"}:raise ValueError("Unexpected depth unit")
 depth=np.asarray(las.data[:,0],float)*(1 if unit=="M" else .3048)
 if not np.all(np.isfinite(depth)) or not np.all(np.diff(depth)>0):raise ValueError("Log requires index review")
 features={};schema=[]
 for i,c in enumerate(las.curves):
  if c.mnemonic in FEATURE_MAP:
   name,expected=FEATURE_MAP[c.mnemonic]
   if c.unit.strip().upper()!=expected:raise ValueError("Unexpected curve units: "+c.mnemonic)
   features[name]=np.asarray(las.data[:,i],float)
   schema.append({"feature":name,"source_curve":c.mnemonic,"source_unit":c.unit,"description":c.descr})
 return {"depth":depth,"features":features,"schema":schema,"profile":profile}
def nearest(log,d):
 if d is None:return None,{},None
 a=log["depth"];pos=int(np.searchsorted(a,d));choices=[j for j in [pos-1,pos] if 0<=j<len(a)]
 i=min(choices,key=lambda j:abs(a[j]-d))
 vals={k:number(v[i]) for k,v in log["features"].items()}
 return float(a[i]),vals,float(abs(a[i]-d))
def feature_issues(values):
 reasons=[]
 for c in REQUIRED:
  if values.get(c) is None:reasons.append("missing_"+c)
 for c in ["bulk_density_g_cm3","deep_resistivity_ohm_m"]:
  if values.get(c) is not None and values[c]<=0:reasons.append("nonpositive_"+c)
 return reasons
def freeman_rows(book):
 """Repeated WELL ID headers are authoritative within this source sheet."""
 rows=sheet(book,"Corelab Poroperm");well=None;headerrow=None
 for ri,row in enumerate(rows,1):
  if str(at(row,1)).strip().upper()=="WELL ID":
   well=canon_freeman(at(row,2));headerrow=ri
   continue
  depth=number(at(row,2))
  if well and depth is not None and sid(at(row,1)) and re.fullmatch(r"\d+",sid(at(row,1))):
   yield {"row":ri,"well":well,"well_header_row":headerrow,"sample":sid(at(row,1)),"sample_raw":at(row,1),"depth_ft":depth,"description":str(at(row,7)),"targets":[("permeability_air",3,"mD"),("permeability_brine",4,"mD"),("porosity",5,"%")],"values":row}
def run():
 OUT.mkdir(parents=True,exist_ok=False)
 profiles=[json.loads(s) for s in (AUDIT/"log_profiles.jsonl").read_text().splitlines()]
 gprofile=next(r for r in profiles if r.get("well")=="GABO51")
 gbook=loadbook("GABO-51 PRELIMINARY");gshift=loadbook("GABO-51_Core_to_log_shift")
 fbook=loadbook("Freeman-4 conventional core analysis.xls")
 logs={"GABO-51":loadlog(gprofile)}
 for name in ["FREEMAN-4","FREEMAN-4-ST1"]:
  wanted="MARIE/Well logs/Freeman-004"+("-ST1" if name.endswith("ST1") else "")+".las"
  p=next(r for r in profiles if r["relative_path"]==wanted)
  assert canon_freeman(p["well"])==name and p["field"]=="FREEMAN"
  logs[name]=loadlog(p)
 raw=[];aliases=[];corrections=[];notes=[];sources={}
 for b in [gbook,gshift,fbook]:sources[b["source_path"]]=b["sha256"]
 for log in logs.values():sources[log["profile"]["source_path"]]=log["profile"]["sha256"]
 grow=sheet(gbook,"RR06001-KPHI-GABO-51")
 shiftrows=sheet(gshift,"Sheet1")
 for ri,row in enumerate(grow,1):
  dep=number(at(row,2))
  if ri<10 or dep is None or not sid(at(row,1)):continue
  flags=re.findall(r"\((\d+)\)",str(at(row,8)))
  # Notes 1 and 2 explicitly question measurement validity; notes 4/5 are retained flags.
  compromised=any(f in flags for f in ["1","2"])
  shifts=[(n+1,r) for n,r in enumerate(shiftrows) if number(at(r,2)) is not None and number(at(r,3)) is not None and float(at(r,2))<=dep<=float(at(r,3))]
  depth=None;shiftref=""
  if len(shifts)==1:
   n,r=shifts[0];a,b,c,d=[float(at(r,k)) for k in [2,3,4,5]]
   depth=c+(dep-a)*(d-c)/(b-a);shiftref=f'{gshift["source_path"]}#Sheet1!B{n}:F{n}'
  spec=hashlib.sha256(f"GABO-51|{sid(at(row,1))}|{dep}".encode()).hexdigest()[:24]
  for pressure,pcol,kcol in [(190,3,4),(225,5,6)]:
   for target,col,unit in [("porosity",pcol,"%"),("permeability_air_horizontal",kcol,"mD")]:
    raw.append({"specimen_id":spec,"well_id":"GABO-51","field_id":"","split_group_id":"GABO-51_source_package","sample_id":sid(at(row,1)),"core_source":gbook["source_path"],"core_sha256":gbook["sha256"],"sheet":"RR06001-KPHI-GABO-51","source_row":ri,"target_column":col,"target":target,"measurement":measurement(at(row,col)),"unit":unit,"condition":f"{pressure}_bar","stress_value":pressure,"stress_unit":"bar","core_depth_m":dep,"shifted_log_depth_m":depth,"shift_evidence":shiftref,"shift_status":"source_estimated_interval_shift" if depth is not None else "unresolved","notes":flags,"compromised":compromised,"sample_marker_unresolved":False,"description":str(at(row,9))})
 aliases.append({"canonical_well":"GABO-51","log_well_header":gprofile["well"],"core_well_header":"GABO-51","evidence":"Core B2 and LAS WELL; same source package; punctuation-only difference","status":"source_package_identity_supported; global UWI/field unresolved"})
 notes.extend({"source":gbook["source_path"],"sheet":"RR06001-KPHI-GABO-51","row":ri,"text":str(at(grow[ri-1],1))} for ri in range(175,181))
 db=sheet(fbook,"Database")
 for r in freeman_rows(fbook):
  well=r["well"];dep=r["depth_ft"]
  dbhits=[(i+1,x) for i,x in enumerate(db) if canon_freeman(at(x,1))==well and sid(at(x,3))==r["sample"] and number(at(x,6)) is not None and abs(float(at(x,6))-dep)<1e-6]
  depth=None;shiftref="";dbrow=None;shiftstatus="unresolved"
  if len(dbhits)==1:
   dbrow,x=dbhits[0];ld=number(at(x,7))
   # Cross-check cached Database log depth against the well/core-specific Shifts table.
   coreid=number(at(x,4));shiftcol=2 if well=="FREEMAN-4" else 3
   shift_hits=[(i+1,s) for i,s in enumerate(sheet(fbook,"Shifts")) if number(at(s,1))==coreid and coreid is not None and number(at(s,shiftcol)) is not None]
   if ld is not None and len(shift_hits)==1:
    si,sr=shift_hits[0];shift=float(at(sr,shiftcol))
    if abs(ld-dep-shift)<1e-6:
     depth=ld*.3048;shiftref=f'{fbook["source_path"]}#Database!F{dbrow}:G{dbrow};Shifts!{chr(64+shiftcol)}{si}'
     shiftstatus="source_log_depth_and_shift_agree; feet_inherited_from_matching_Corelab_depth"
  spec=hashlib.sha256(f"{well}|{r['sample']}|{dep}".encode()).hexdigest()[:24]
  fracture=bool(re.search(r"\bfrac(?:tured|ture)?\b|chipped|broken",r["description"],re.I))
  for target,col,unit in r["targets"]:
   raw.append({"specimen_id":spec,"well_id":well,"field_id":"FREEMAN","split_group_id":"FREEMAN-4_parent_and_sidetrack","sample_id":r["sample"],"core_source":fbook["source_path"],"core_sha256":fbook["sha256"],"sheet":"Corelab Poroperm","source_row":r["row"],"source_well_header_row":r["well_header_row"],"target_column":col,"target":target,"measurement":measurement(at(r["values"],col)),"unit":unit,"condition":"1000_psig","stress_value":1000,"stress_unit":"psig","core_depth_m":dep*.3048,"shifted_log_depth_m":depth,"shift_evidence":shiftref,"shift_status":shiftstatus,"notes":["source_description_fracture"] if fracture else [],"compromised":fracture,"sample_marker_unresolved":"*" in str(r["sample_raw"]),"description":r["description"]})
  if well=="FREEMAN-4-ST1":corrections.append({"source":fbook["source_path"],"sheet":"Corelab Poroperm","row":r["row"],"previous_assignment":"Freeman-4","correct_assignment":well,"evidence":"WELL ID header at row 66 states Freeman-4 ST1"})
 for well in ["FREEMAN-4","FREEMAN-4-ST1"]:
  aliases.append({"canonical_well":well,"log_well_header":logs[well]["profile"]["well"],"core_well_header":"Freeman-4" if well=="FREEMAN-4" else "Freeman-4 ST1","evidence":"Explicit laboratory WELL ID headers, LAS WELL/FLD=FREEMAN; numeric zero-padding normalized, sidetrack retained","status":"source-supported naming equivalence"})
 datasets=collections.defaultdict(list);ledger=[];censored=[];rejected=[]
 for r in raw:
  m=r.pop("measurement");log=logs[r["well_id"]]
  actual,features,delta=nearest(log,r["shifted_log_depth_m"])
  reasons=[]
  if r["compromised"]:reasons.append("fractured_chipped_or_broken_source_sample")
  if r["sample_marker_unresolved"]:reasons.append("asterisk_sample_marker_requires_explanation")
  if r["shifted_log_depth_m"] is None:reasons.append("depth_shift_unresolved")
  if delta is not None and delta>.25:reasons.append("log_sample_farther_than_0.25m")
  reasons+=feature_issues(features)
  v=m["value"]
  normalized=v/100 if v is not None and r["unit"]=="%" else v
  if m["kind"]!="exact":reasons.append("target_"+m["kind"])
  elif r["target"]=="porosity" and not 0<=normalized<=1:reasons.append("porosity_out_of_range")
  elif r["target"].startswith("permeability") and normalized<=0:reasons.append("nonpositive_permeability_requires_review")
  record={**r,"target_value_raw":m["raw"],"target_kind":m["kind"],"target_bound":m.get("bound"),"target_operator":m.get("operator",""),"target_value":normalized,"target_unit":"fraction" if r["unit"]=="%" else "mD","log_source":log["profile"]["source_path"],"log_sha256":log["profile"]["sha256"],"log_depth_m":actual,"alignment_distance_m":delta,**features,"exclusion_reasons":reasons,"status":"eligible_for_development" if not reasons else "excluded_from_primary","split":"unassigned"}
  ledger.append(record)
  if m["kind"]=="censored":censored.append(record)
  if reasons:rejected.append(record)
  else:datasets[(r["well_id"],r["condition"],r["target"])].append(record)
 outcsv(OUT/"SAMPLE_TARGET_LEDGER.csv",ledger)
 outcsv(OUT/"CENSORED_TARGETS.csv",censored)
 outcsv(OUT/"EXCLUDED_RECORDS.csv",rejected)
 outcsv(OUT/"IDENTITY_EVIDENCE.csv",aliases)
 outcsv(OUT/"EXTRACTION_CORRECTIONS.csv",corrections)
 outcsv(OUT/"LABORATORY_NOTES.csv",notes)
 schema={well:log["schema"] for well,log in logs.items()}
 jwrite(OUT/"FEATURE_SCHEMA.json",{"required_common_features":REQUIRED,"optional_features":["compressional_slowness_us_ft","caliper_in","density_correction_g_cm3"],"sources":schema,"excluded_model_inputs":["target_value","target_bound","core_depth_m","shifted_log_depth_m","well_id","sample_id","specimen_id","split_group_id","all metadata and interpretation-derived labels"]})
 manifests=[]
 for (well,condition,target),records in sorted(datasets.items()):
  folder=OUT/well/condition/target;folder.mkdir(parents=True)
  metadata_cols=[k for k in records[0] if k not in REQUIRED]
  outcsv(folder/"dataset.csv",records)
  outcsv(folder/"features.csv",records,["specimen_id",*REQUIRED])
  outcsv(folder/"targets.csv",records,["specimen_id","target_value","target_unit"])
  # No transforms are learned here; no labels/features are imputed.
  manifests.append({"well":well,"condition":condition,"target":target,"rows":len(records),"path":str(folder/"dataset.csv"),"features_path":str(folder/"features.csv"),"targets_path":str(folder/"targets.csv"),"status":"development_candidate_no_independent_split"})
 outcsv(OUT/"DATASET_REGISTRY.csv",manifests)
 jwrite(OUT/"SOURCE_HASHES.json",sources)
 counts={"source_target_slots":len(ledger),"nonmissing_target_slots":sum(r["target_kind"]!="missing" for r in ledger),"primary_task_rows":sum(len(v) for v in datasets.values()),"primary_unique_specimens":len({r["specimen_id"] for v in datasets.values() for r in v}),"primary_wells":sorted({k[0] for k in datasets}),"independent_parent_groups":sorted({r["split_group_id"] for v in datasets.values() for r in v}),"dataset_tables":len(manifests),"censored_target_rows":len(censored),"source_rows_with_corrected_sidetrack":len(corrections),"source_note_exclusions":sum(r["compromised"] and r["target_kind"]!="missing" for r in ledger),"status_counts":dict(collections.Counter(r["status"] for r in ledger)),"datasets":manifests,"models_trained":0,"split_status":"not_created: only two parent-well groups; stress/fluid conditions differ; field identity unresolved for GABO"}
 jwrite(OUT/"SUMMARY.json",counts)
 print(json.dumps(counts,indent=2))
if __name__=="__main__":run()
