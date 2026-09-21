from pathlib import Path
import json,csv,hashlib,math,re
import pandas as pd
import numpy as np
B=Path(r"E:\PETROEDGE_AI\codex");O=B/"data/prepared/saturation_030";O.mkdir(parents=True,exist_ok=False)
A=B/"data/readiness/log_core_001";books=[json.loads(p.read_text()) for p in (A/"core_workbooks").glob("*.json")]
book=next(b for b in books if b["source_path"].endswith("15919A.XLS"));assert hashlib.sha256(Path(book["source_path"]).read_bytes()).hexdigest()==book["sha256"]
ledger=pd.read_csv(B/"data/prepared/volve_004/REVIEW_LEDGER.csv")
ledger=ledger[ledger.well.eq("NO 15/9-19 A") & ledger.target.eq("porosity_helium_horizontal")].set_index("source_row")
rows=book["sheets"][0]["rows"];assert rows[3][12:14]==["So","Sw"] and rows[4][12:14]==["(%)","(%)"]
records=[];scenarios=[]
def numeric(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
def archie(phi,rt,rw,a=1,m=2,n=2):
 if not (0<phi<=1 and rt>0 and rw>0 and a>0 and m>0 and n>0):raise ValueError("Invalid Archie inputs")
 return (a*rw/(rt*phi**m))**(1/n)
assert abs(archie(.2,10,.1)-.5)<1e-12
assert abs(archie(.2,10,.4)-2*archie(.2,10,.1))<1e-12
for args in [(0,10,.1),(.2,0,.1),(.2,10,0)]:
 try:archie(*args);raise AssertionError("Invalid inputs accepted")
 except ValueError:pass
verified={}
for rn,r in enumerate(rows,1):
 if len(r)<14 or not all(numeric(r[i]) for i in [0,1,2,12,13]):continue
 so,sw=float(r[12])/100,float(r[13])/100
 entry=dict(specimen_id=f"VOLVE_19_A_core{int(r[0])}_sample{int(r[1])}_row{rn}",well="NO 15/9-19 A",parent_group="VOLVE_15_9_19_parent_and_sidetracks",core_number=int(r[0]),sample_number=int(r[1]),core_depth_m=float(r[2]),core_oil_fraction=so,core_water_fraction=sw,unaccounted_fraction=1-so-sw,unaccounted_fraction_meaning="Not a measured reservoir gas saturation",source_path=book["source_path"],source_sha256=book["sha256"],source_sheet=book["sheets"][0]["name"],source_row=rn,label_scope="Reported conventional core saturation; preservation extraction and representativeness unconfirmed",training_approved=False)
 reasons=[]
 if not 0<=so<=1 or not 0<=sw<=1 or so+sw>1.01:reasons.append("core_fraction_QC")
 if rn not in ledger.index:reasons.append("alignment_record_missing")
 else:
  match=ledger.loc[rn];lp=Path(match.log_path)
  if str(lp) not in verified:
   actual=hashlib.sha256(lp.read_bytes()).hexdigest()
   expected=json.loads((B/"data/prepared/volve_004/SOURCE_HASHES.json").read_text())[str(lp)]
   assert actual==expected;verified[str(lp)]=actual
  for k in ["log_depth_m","depth_delta_m","gr_api","neutron_porosity_v_v","bulk_density_g_cm3","resistivity_ohm_m","bad_data_flag"]:entry[k]=float(match[k]) if pd.notna(match[k]) else None
  entry["log_source"]=str(lp);entry["log_sha256"]=verified[str(lp)]
  if entry["depth_delta_m"] is None or entry["depth_delta_m"]>.25:reasons.append("depth_alignment_QC")
  if entry["bad_data_flag"]!=0:reasons.append("bad_data_flag_not_explicitly_clear")
  vals=[entry[k] for k in ["gr_api","neutron_porosity_v_v","bulk_density_g_cm3","resistivity_ohm_m"]]
  if any(v is None or not math.isfinite(v) for v in vals):reasons.append("missing_log_input")
  elif not (0<=vals[0]<=500 and 0<=vals[1]<=1 and 1<=vals[2]<=4 and vals[3]>0):reasons.append("input_range_QC")
 entry["numerical_alignment_status"]="candidate" if not reasons else "held"
 entry["hold_reasons"]=";".join(reasons);records.append(entry)
 if not reasons:
  phi=(2.65-entry["bulk_density_g_cm3"])/(2.65-1.0)
  if 0<phi<=.6:
   for rw in [.05,.1,.2]:
    raw=archie(phi,entry["resistivity_ohm_m"],rw)
    scenarios.append(dict(specimen_id=entry["specimen_id"],log_depth_m=entry["log_depth_m"],density_porosity_estimate=phi,matrix_density_assumed_g_cm3=2.65,fluid_density_assumed_g_cm3=1.0,rw_assumed_ohm_m=rw,a_assumed=1,m_assumed=2,n_assumed=2,sw_raw=raw,sw_bounded=min(1,raw),above_one=raw>1,status="uncalibrated_clean_formation_scenario_not_training_label"))
pd.DataFrame(records).to_csv(O/"CORE_SATURATION_REVIEW.csv",index=False)
pd.DataFrame(scenarios).to_csv(O/"ARCHIE_SCENARIOS.csv",index=False)
cat=pd.read_csv(B/"data/catalogs/all_data_003/MASTER_CATALOG.csv")
hits=cat[cat.relative_path.str.contains(r"PVT|SCAL|relp|relperm|core.flood|saturation",case=False,regex=True,na=False)].copy()
hits[["source_path","detected_format","relative_path"]].to_csv(O/"SUPPORTING_DATA_CANDIDATES.csv",index=False)
summary=dict(core_saturation_pairs=len(records),numerical_candidates=sum(r["numerical_alignment_status"]=="candidate" for r in records),held_rows=sum(r["numerical_alignment_status"]=="held" for r in records),core_fraction_sum_range=[min(r["core_oil_fraction"]+r["core_water_fraction"] for r in records),max(r["core_oil_fraction"]+r["core_water_fraction"] for r in records)],archie_scenario_rows=len(scenarios),scenario_specimens=len(set(r["specimen_id"] for r in scenarios)),above_one_scenarios=sum(r["above_one"] for r in scenarios),supporting_file_candidates=len(hits),training_approved=0,models_trained=0,blockers=["Recovered core saturation method and preservation/invasion history not established","No measured in-situ gas saturation label established","No qualified Rw at formation temperature or measured Archie a m n assigned","One parent well; no independent-well training validation test design"],formula_tests="passed",note="Separate target-specific review: prior horizontal porosity eligibility does not apply to these saturation specimens. SCAL curves are laboratory response curves, not independent depth labels.")
(O/"REPORT.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
(O/"README.md").write_text("# Saturation data qualification and baseline\n\n"+json.dumps(summary,indent=2)+"\n\nCORE_SATURATION_REVIEW.csv preserves source oil/water values, depth joins and QC. The unaccounted fraction is not labeled gas. ARCHIE_SCENARIOS.csv uses explicitly assumed Rw, matrix/fluid density and Archie constants; raw results above one remain flagged alongside bounded display values. These scenarios are not measured labels, calibration or model-performance results. They must not be used to train a model and then called independent saturation truth. Supporting-file candidates are discovery records, not verified content. No production configuration changed.\n",encoding="utf-8")
print(json.dumps(summary))
