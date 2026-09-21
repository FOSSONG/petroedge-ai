from pathlib import Path
import json,re,hashlib,math
import pandas as pd
B=Path(r"E:\PETROEDGE_AI\codex"); A=B/"data/readiness/log_core_001"; O=B/"data/prepared/saturation_sources_032"; O.mkdir(parents=True,exist_ok=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
pattern=re.compile(r"(^|_)(SW|SO|SG|SWT|SWE|SWIRR|BVW)($|_)|saturation",re.I)
rows=[]; profiles=0
for line in (A/"log_profiles.jsonl").open():
 p=json.loads(line);profiles+=1
 for frame in p.get("frames",[]):
  for c in frame.get("channels",[]):
   if not pattern.search(c["name"]+" "+c.get("description","")):continue
   path=p["source_path"];desc=c.get("description","")
   if "exponent" in desc.lower():category="parameter_not_saturation_target"
   elif "X-005" in path:category="tool_interpretation_requires_acquisition_review"
   elif "COMPUTED" in path.upper() or "INTERPRETATION" in path.upper() or "CPI" in path.upper():category="computed_petrophysical_interpretation"
   elif "Alwyn" in path or "Kandie" in path:category="teaching_case_interpretation_provenance_unverified"
   else:category="saturation_named_curve_method_unverified"
   rows.append(dict(source_path=path,cached_sha256=p.get("sha256"),well_header=p.get("well",""),field=p.get("field",""),frame=frame.get("frame_id"),channel=c["name"],unit=c.get("unit"),description=desc,usable_candidate_rows=c.get("usable_candidate_count"),category=category,measured_label_approved=False,production_eligible=False))
pd.DataFrame(rows).to_csv(O/"LOG_TARGET_CANDIDATES.csv",index=False)
books=[];alwyn=[]
for p in (A/"core_workbooks").glob("*.json"):
 w=json.loads(p.read_text())
 for s in w["sheets"]:
  hits=[]
  for i,row in enumerate(s["rows"]):
   for j,v in enumerate(row):
    if isinstance(v,str) and re.search(r"\b(sw|so|sg|saturation|saturations|swi|sor|wtr)\b",v,re.I):hits.append(dict(row=i+1,column=j+1,text=v[:200]))
  if hits:books.append(dict(source_path=w["source_path"],sheet=s["name"],keyword_cells=hits,approved=False))
  if "Alwyn" in w["source_path"] and s["name"]=="cores1to9":
   assert sha(w["source_path"])==w["sha256"]
   values=[]
   for n,row in enumerate(s["rows"],1):
    if len(row)>8 and all(isinstance(row[k],(int,float)) and math.isfinite(row[k]) for k in [1,2,7,8]):values.append([row[k] for k in [1,2,7,8]])
   alwyn.append(dict(source_path=w["source_path"],source_sha256=w["sha256"],numeric_sample_depth_oil_water_rows=len(values),numeric_content_sha256=hashlib.sha256(json.dumps(values).encode()).hexdigest(),scope="ALWYN 3/9A-4 teaching workbook; units, method, provenance and core-log depth alignment need qualification",training_approved=False))
(O/"WORKBOOK_REVIEW.json").write_text(json.dumps(books,indent=2),encoding="utf-8")
# Inspect actual Field X headers and payloads, without joining historical logs.
import lasio
rst=[]
for name in ["las7738.las","las8098.las","las8374.las"]:
 path=Path(r"F:\DATA_PETROEDGE_AI\Niger delta Fields\Field X\X_FIELD_Well logs\X-005")/name
 header=[]
 for line in path.read_text(errors="replace").splitlines():
  if line.strip().upper().startswith("~A"):break
  if re.match(r"^(DATE|LNAM|LMF|WELL|R[1-5] )",line):header.append(re.sub(r"\s+"," ",line).strip())
 las=lasio.read(str(path)); curves=[]
 for c in las.curves:
  if c.mnemonic.split(":")[0] in ["SW","SO"]:
   import numpy as np
   v=np.asarray(las[c.mnemonic],dtype=float);valid=v[np.isfinite(v)]
   curves.append(dict(channel=c.mnemonic,unit=c.unit,finite_rows=len(valid),outside_fraction_range=int(((valid<0)|(valid>1)).sum()),minimum=float(valid.min()) if len(valid) else None,maximum=float(valid.max()) if len(valid) else None))
 rst.append(dict(source_path=str(path),sha256=sha(path),header_evidence=header,curves=curves,training_approved=False,hold_reasons=["Conflicting header dates 1966 and 1998; acquisition/time alignment with input logs not established","RST interpreted saturation requires processing/QC review; not a core measurement","Repeated exports/channels require depth-level duplicate resolution","Only one Field X well in this targeted group; not a multi-well validation set"]))
(O/"FIELD_X_RST_REVIEW.json").write_text(json.dumps(rst,indent=2),encoding="utf-8")
report=dict(scope="Existing decoded log profiles and cached core workbooks; not exhaustive inspection of every PDF, image, archive or unparsed file",profiles_scanned=profiles,matched_channels=len(rows),matched_files=len(set(r["source_path"] for r in rows)),category_counts=pd.Series([r["category"] for r in rows]).value_counts().to_dict(),alwyn=alwyn,field_x_rst_files=len(rst),new_measured_label_sets_approved=0,models_trained=0,prior_031_test_reused=False,cache_hashes={str(A/n):sha(A/n) for n in ["log_profiles.jsonl"]},next_actions=["Qualify Alwyn source methods, units and matching log coverage, retaining teaching-case provenance and deduplicating student/solution copies","Review Field X RST acquisition/QC/time correspondence before any supervised joins","Use interpreted SW only in a separately named interpretation-reproduction task, never as independent measured saturation truth","Keep saturation models from phase031 out of production; no new qualified independent-well set established"])
(O/"REPORT.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
summary=["# Saturation source qualification register", "",f"Scanned {profiles} cached log profiles: {len(rows)} matching channels in {report['matched_files']} files. Counts include a saturation exponent and repeated/derived curves; they are not counts of independent labels.","", "No additional measured saturation dataset approved and no model retrained.","", "## Findings", "", "- Field X X-005: three RST exports contain oil/water curves. Actual headers include both 1966 and 1998 dates; timing and historical-log joins remain unresolved. One export repeats SW with different unit notation. All remain held.", "- Alwyn: student and solution workbooks contain numeric oil/water core columns. They remain educational-source candidates until units, measurement method and depth alignment are confirmed; copies must not become separate wells.", "- Computed Volve and other named SW curves are interpretation candidates, not independent laboratory truth. Sidetracks require shared parent-well splits.", "", "## Next steps", ""]+["- "+x for x in report["next_actions"]]+["",report["scope"],"", "Files: LOG_TARGET_CANDIDATES.csv, WORKBOOK_REVIEW.json, FIELD_X_RST_REVIEW.json, REPORT.json. Raw files were read only; the running application was unchanged."]
(O/"README.md").write_text("\n".join(summary),encoding="utf-8")
assert all(not r["measured_label_approved"] for r in rows)
assert len(rst)==3 and all(not x["training_approved"] for x in rst)
print(json.dumps(report,indent=2))
