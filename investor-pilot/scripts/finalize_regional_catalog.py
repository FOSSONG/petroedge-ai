"""Join explicit source well-header evidence and publish review worklists."""
from pathlib import Path
import collections,csv,hashlib,json,sys
import openpyxl,xlrd
from data_catalog import normal,write_csv,write_json,TASKS,candidates
ROOT=Path("E:/PETROEDGE_AI/codex")
SOURCE=Path("F:/DATA_PETROEDGE_AI")
BASE=ROOT/"data/catalogs/niger_delta_audit_002"
OUT=ROOT/"data/catalogs/regional_review_001"
OUT.mkdir(parents=True,exist_ok=False)
records=[json.loads(line) for line in (BASE/"catalog.jsonl").read_text(encoding="utf-8").splitlines()]
tables=[
 "AI WITH TOTAL E&P DATA/Header_Information/Header-Information.xlsx",
 "AI WITH TOTAL E&P DATA/NEW DATA FEB 2025 FROM TOTAL E&P/Well Names.xls",
 "Niger delta Fields/Field X/Well Header Location/XFIELD WELL HEADER LOCATION  INFORMATION.xlsx",
 "Niger delta Fields/Gabo field/GABO_LOG_WELL_HEADERS.xls"]
evidence=[]
for relative in tables:
    path=SOURCE/relative
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if path.suffix==".xlsx":
        book=openpyxl.load_workbook(path,read_only=True,data_only=True,keep_links=False)
        sheets=[(sheet.title,list(sheet.iter_rows(values_only=True))) for sheet in book.worksheets]
        book.close()
    else:
        book=xlrd.open_workbook(str(path),on_demand=True)
        sheets=[(sheet.name,[sheet.row_values(i) for i in range(sheet.nrows)]) for sheet in book.sheets()]
        book.release_resources()
    for sheet,rows in sheets:
        header_row=None
        for index,row in enumerate(rows[:20]):
            columns={normal(v):i for i,v in enumerate(row) if v is not None}
            well_key=next((key for key in ["WELLNAME","WELL"] if key in columns),None)
            basin_key=next((key for key in ["BASINSUBBASIN","BASINNAME","BASINIDENTIFIER"] if key in columns),None)
            if well_key and basin_key:
                header_row=index
                break
        if header_row is None:continue
        for row_number,row in enumerate(rows[header_row+1:],header_row+2):
            if len(row)<=max(columns[well_key],columns[basin_key]):continue
            well=str(row[columns[well_key]] or "").strip()
            basin=str(row[columns[basin_key]] or "").strip()
            if well and normal(basin)=="NIGERDELTA":
                evidence.append({"collection":relative.split("/")[0],"well":well,"well_key":normal(well),"basin":basin,
                    "field":str(row[columns["FIELDNAME"]]) if "FIELDNAME" in columns else "",
                    "source_workbook":relative,"sheet":sheet,"row":row_number,"source_sha256":digest,
                    "status":"explicit_source_table_basin_statement_not_independent_validation"})
lookup=collections.defaultdict(list)
for e in evidence:lookup[(e["collection"],e["well_key"])].append(e)
metadata=[json.loads(l) for l in (ROOT/"data/catalogs/content_metadata_001/metadata.jsonl").read_text(encoding="utf-8").splitlines()]
metadata_lookup={r["relative_path"]:r for r in metadata}
for record in records:
    matches=lookup.get((record["collection"],normal(record["well"])),[])
    record["linked_region_evidence"]=matches
    if matches and record["geography_status"] not in {"outside_nigeria_header","conflicting_metadata"}:
        record["geography_status"]="source_header_table_match"
        record["geography_evidence"]="Exact normalized well name within same collection; source workbook/sheet/row retained"
    elif matches:
        record["geography_status"]="conflicting_metadata"
    meta=metadata_lookup.get(record["relative_path"],{})
    record["content_purpose_hints"]=meta.get("purpose_hints",[])
    if meta.get("sheets"):
        for hint in record["content_purpose_hints"]:
            record["candidate_tasks"]=sorted(set(record["candidate_tasks"])|set(candidates(hint)))
    record["region_review_bucket"]=("niger_delta_source_supported" if record["geography_status"] in {"source_header_table_match","source_header_niger_delta"}
        else "external_excluded_from_nonedge" if record["geography_status"]=="outside_nigeria_header"
        else "unresolved_or_conflicting")
    record["nonedge_gate"]="blocked_until_identity_label_units_review" if record["region_review_bucket"]=="niger_delta_source_supported" else "blocked_pending_niger_delta_evidence"
columns=["file_id","relative_path","bytes","modality","content_purpose_hints","geography_status","geography_evidence",
         "field","well","uwi","linked_region_evidence","candidate_tasks","target_candidates","sha256","region_review_bucket","nonedge_gate","split","training_ready"]
write_csv(OUT/"CATALOG.csv",records,columns)
write_json(OUT/"REGION_EVIDENCE.json",evidence)
with (OUT/"catalog.jsonl").open("w",encoding="utf-8") as stream:
    for record in records:stream.write(json.dumps(record,ensure_ascii=False)+"\n")
for bucket in sorted({r["region_review_bucket"] for r in records}):
    write_csv(OUT/"by_region"/bucket/"manifest.csv",[r for r in records if r["region_review_bucket"]==bucket],columns)
task_counts={}
for task in TASKS:
    matching=[r for r in records if task in r["candidate_tasks"]]
    allowed=[r for r in matching if task=="edge_computing" or r["region_review_bucket"]=="niger_delta_source_supported"]
    blocked=[r for r in matching if r not in allowed]
    taskroot=ROOT/"data/tasks"/task/"catalogs"
    write_csv(taskroot/"region_candidates.csv",allowed,columns)
    write_csv(taskroot/"blocked_region_review.csv",blocked,columns)
    write_json(taskroot/"STATUS.json",{"source_catalog":str(OUT),"candidate_count":len(allowed),"blocked_count":len(blocked),
       "status":"metadata_review_only","training_ready":False,
       "scope":"External geography allowed only for edge; task relevance and labels still need validation"})
    task_counts[task]={"region_candidates":len(allowed),"blocked":len(blocked)}
summary={"files":len(records),"region_buckets":dict(collections.Counter(r["region_review_bucket"] for r in records)),
 "evidence_table_rows":len(evidence),"source_table_matched_files":sum(r["geography_status"]=="source_header_table_match" for r in records),
 "task_worklists":task_counts,"training_ready_files":0,"calibration_status":"not calibrated",
 "limits":["No unstructured or DLIS contents yet validated","Basin source statements are not independent validation",
 "Field aliases, label provenance, units and commercial deployment rights remain unresolved","No locked data splits or trained models produced"]}
write_json(OUT/"SUMMARY.json",summary)
write_json(ROOT/"data/catalogs/CURRENT.json",{"regional_catalog":str(OUT),"base_catalog":str(BASE),"metadata_catalog":str(ROOT/"data/catalogs/content_metadata_001"),
 "superseded_catalog":str(ROOT/"data/catalogs/niger_delta_audit_001"),
 "superseded_reason":"Initial country classifier treated unrecognized codes as external; fixed with explicit external-country allowlist and regression tests"})
policy={"nonedge_region_requirement":"verified_niger_delta","edge_external_exception":True,
 "unknown_region_action":"hold_for_review","never_convert_external_data_to_nigerian_by_relabeling":True,
 "split_unit":"canonical_field","well_aliases":"resolve_before_split","duplicate_check":"full content hash plus overlapping intervals and shared lineage",
 "preprocessing_fit":"training_only","test_use":"sealed independent evaluation only",
 "assistant_and_agent_evaluation":"exclude held-out answers and derived analysis from retrieval and tuning",
 "calibration_status":"not calibrated","runtime_api_enforcement":"not yet integrated; current controls are preparation CLI and manifests"}
write_json(ROOT/"data/REGIONAL_DATA_POLICY.json",policy)
columns_review=["file_id","source_path","sha256","field_id","well_id","task","region_status","region_evidence","identity_status","label_status","units_status","causal_review"]
write_csv(ROOT/"data/REVIEWED_MANIFEST_TEMPLATE.csv",[],columns_review)
print(json.dumps(summary),flush=True)

