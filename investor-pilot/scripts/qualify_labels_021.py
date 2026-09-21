from pathlib import Path
import csv,json,hashlib,re,collections
import openpyxl
B=Path(r"E:\PETROEDGE_AI\codex\data")
O=B/"prepared/label_candidates_021"
O.mkdir(parents=True,exist_ok=False)
def write(name,rows):
 columns=list(dict.fromkeys(k for r in rows for k in r))
 with (O/name).open("w",newline="",encoding="utf-8") as f:
  w=csv.DictWriter(f,fieldnames=columns);w.writeheader();w.writerows(rows)
def norm(s):return re.sub(r"[^A-Z0-9]","",re.sub(r"^NO\s+","",str(s).upper()))
cat=list(csv.DictReader((B/"catalogs/all_data_003/MASTER_CATALOG.csv").open(encoding="utf-8-sig")))
logs=list(csv.DictReader((B/"readiness/log_core_001/LOG_FILES.csv").open(encoding="utf-8-sig")))
intervals=[];sources=[]
for row in cat:
 if not row["source_path"].lower().endswith("facies.xlsx"):continue
 path=Path(row["source_path"]);digest=hashlib.sha256(path.read_bytes()).hexdigest()
 book=openpyxl.load_workbook(path,read_only=True,data_only=True)
 count=0
 for sheet in book:
  iterator=sheet.iter_rows(values_only=True);headers=[str(c or "").strip() for c in next(iterator)]
  for number,values in enumerate(iterator,2):
   cells=dict(zip(headers,values))
   if not cells.get("Litho Class"):continue
   top=cells.get("* Top Depth (meters)");base=cells.get("* Base Depth (meters)")
   try:top=float(top);base=float(base)
   except (ValueError,TypeError):continue
   well=str(cells.get("* Well UWI") or cells.get("Common Well Name"))
   kind=str(cells.get("* Litho Crv Type") or "")
   record={"well":well,"parent_group":re.sub(r"(BT[0-9]+|SR|[ABC])$","",norm(well)),"top_m":top,"base_m":base,"label":str(cells["Litho Class"]),"label_type":kind,"interpretation_source":cells.get("* Source"),"rock_percent":cells.get("Rock Percent (%)"),"source_path":str(path),"source_sha256":digest,"sheet":sheet.title,"excel_row":number,"status":"candidate_pending_depth_reference_and_label_provenance" if base>top else "invalid_interval","training_ready":False}
   intervals.append(record);count+=1
 book.close();sources.append({"path":str(path),"sha256":digest,"interval_rows":count})
# Repeated intervals remain visible, with explicit duplicate flags.
seen=set()
for r in intervals:
 key=tuple(r[k] for k in ("well","top_m","base_m","label","label_type","interpretation_source"))
 r["duplicate_semantic_interval"]=key in seen;seen.add(key)
write("FACIES_INTERVAL_CANDIDATES.csv",intervals)
labels=[];seen=set();verified={}
for line in (B/"readiness/log_core_001/core_samples.jsonl").open():
 s=json.loads(line)
 if not s.get("lithology_class_source"):continue
 path=s["source_path"]
 if path not in verified:verified[path]=hashlib.sha256(Path(path).read_bytes()).hexdigest()==s["source_sha256"]
 key=(s["well_source"],s["core_depth"],s["lithology_class_source"],s.get("description_source"))
 label=str(s["lithology_class_source"]).strip()
 labels.append({"record_id":s["sample_record_id"],"well":s["well_source"],"core_depth":s["core_depth"],"depth_unit":s["depth_unit"],"raw_label":label,"simple_label_candidate":label.lower() if label.lower() in {"sand","shale","clay"} else "","description":s.get("description_source"),"duplicate_semantic_record":key in seen,"source_hash_verified":verified[path],"source_path":path,"sheet":s["sheet"],"excel_row":s["excel_row"],"status":"pending_well_identity_depth_unit_and_log_alignment","training_ready":False})
 seen.add(key)
write("SIDEWALL_LITHOLOGY_CANDIDATES.csv",labels)
wellreview=[]
for well in sorted(set(r["well"] for r in intervals)):
 matching=[l for l in logs if norm(l.get("well",""))==norm(well)]
 subset=[r for r in intervals if r["well"]==well and not r["duplicate_semantic_interval"]]
 wellreview.append({"well":well,"parent_group":subset[0]["parent_group"],"intervals":len(subset),"label_types":json.dumps(sorted(set(r["label_type"] for r in subset))),"classes":json.dumps(sorted(set(r["label"] for r in subset))),"exact_normalized_log_header_candidates":len(matching),"log_paths":json.dumps([l.get("source_path") for l in matching]),"status":"review_required_no_split_assigned"})
write("INDEPENDENT_WELL_REVIEW.csv",wellreview)
summary={"facies_sources":sources,"facies_intervals":len(intervals),"unique_intervals":sum(not r["duplicate_semantic_interval"] for r in intervals),"facies_wells":len(wellreview),"candidate_parent_groups":len(set(r["parent_group"] for r in wellreview)),"label_types":dict(collections.Counter(r["label_type"] for r in intervals)),"sidewall_rows":len(labels),"unique_sidewall_rows":sum(not r["duplicate_semantic_record"] for r in labels),"simple_label_counts":dict(collections.Counter(r["simple_label_candidate"] for r in labels if not r["duplicate_semantic_record"] and r["simple_label_candidate"])),"all_sidewall_source_hashes_verified":all(verified.values()),"status":"Candidate extraction only. Parent-group names are provisional; no independent model validation or lithology training performed."}
(O/"SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
(O/"README.md").write_text("# Lithology and facies candidates\n\n"+summary["status"]+"\n\nFACIES_INTERVAL_CANDIDATES.csv retains source label types, meter units, workbook rows and hashes. Genetic facies must not be relabeled as rock lithology. MD/TVD reference and interpretation provenance remain unresolved. SIDEWALL_LITHOLOGY_CANDIDATES.csv preserves mixed descriptions without collapsing them into pure classes. Duplicates are flagged, not treated as independent examples. Well identity, depth units and core/log alignment must be resolved before training. INDEPENDENT_WELL_REVIEW.csv contains provisional parent groups and exact normalized header candidates only; these are not verified joins.\n",encoding="utf-8")
print(json.dumps({k:v for k,v in summary.items() if k!="facies_sources"}))
