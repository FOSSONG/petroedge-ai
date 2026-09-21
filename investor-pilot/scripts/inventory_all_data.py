"""Read-only full-tree inventory. Catalog membership is a candidate use, not approval."""
import argparse, collections, csv, hashlib, json, re, zipfile, tarfile
from pathlib import Path
from datetime import datetime, timezone
from data_catalog import las_header

ROOT=Path(r"F:\DATA_PETROEDGE_AI")
BASE=Path(r"E:\PETROEDGE_AI\codex\data")
TASKS=["edge_computing","lithology","porosity","permeability","fluid_saturation","reservoir_classification","hc_pay_classification","ccus","ai_agents","digital_well_twin","analysis_assistant","well_log_viewer","user_training"]
LOGTASKS=TASKS[1:7]
RULES={
"core_lab":r"core|poroperm|k.?phi|scal|rcal|capillary|relative.perm",
"pvt_fluids":r"pvt|fluid.composition|pres+ure.volume.temperature",
"production":r"production|producion|cum.oil|cum.gas|qoil|qgas|water.cut|prod[_ ]",
"pressure_well_test":r"pressure|rft|mdt|well.test|dst",
"drilling_telemetry":r"drilling|pason|3w.dataset|mud.log|witsml",
"biostratigraphy":r"biostrat|stratabugs|paleo|foram|nanno|paly",
"trajectory_well_header":r"trajectory|deviation|well.header|welltrace|dip.*azimuth",
"tops_stratigraphy":r"well.top|formation.top|horizon|stratigraph",
"seismic":r"seismic|segy|seg.y|checkshot|check.shot|velocity",
"simulation_geomodel":r"simulation|geomodel|petrel|eclipse|grdecl",
"geomechanics":r"geomechan|triaxial|compressive.strength|young.s.modulus",
}
def restricted(p):
    return bool(re.search(r"credential|password|secret|token",p.name,re.I)) or p.suffix.lower() in {".lnk",".url",".exe",".dll",".share",".ini"} or p.name.lower() in {"thumbs.db","desktop.ini"} or p.name.startswith("~$")
def identify(p,b):
    ext=p.suffix.lower()
    t=b.decode("latin-1",errors="replace")
    if re.search(r"(?im)^\s*~v(?:ersion)?\b",t) and re.search(r"(?im)^\s*~[wc]\b|~well|~curve",t):
        return "LAS_ASCII","signature"
    if b.startswith(b"%PDF-"):return "PDF","signature"
    if b.startswith(b"\x89PNG\r\n"):return "PNG","signature"
    if b.startswith(b"\xff\xd8\xff"):return "JPEG","signature"
    if b[:4] in (b"II*\x00",b"MM\x00*"):return "TIFF","signature"
    if b.startswith(b"PK\x03\x04"):return ({".xlsx":"XLSX",".docx":"DOCX",".pptx":"PPTX"}.get(ext,"ZIP")),"signature_and_extension"
    if b.startswith(b"\xd0\xcf\x11\xe0"):return {".xls":"XLS",".doc":"DOC",".ppt":"PPT"}.get(ext,"OLE_CONTAINER"),"signature_and_extension"
    if "DLIS" in t[:100] and "RECORD" in t[:100]:return "DLIS","signature"
    if ext==".ptd":return ("PETREL_WELL_LOG" if "FloatWellLog" in t else "PETREL_TRAJECTORY" if "WellTrace" in t else "PETREL_COMPONENT"),"signature_hint" if "Well" in t else "extension"
    if ext==".dex" and "Paleo" in t:return "DEX_PALEO","signature"
    if ext==".pds" and "Pds" in t[:50]:return "PDS_PLOT","signature"
    if "SeismicVolume" in t[:1000]:return "PROPRIETARY_SEISMIC_VOLUME","signature"
    known={".las":"LAS_ASCII",".dlis":"DLIS",".lis":"LIS",".lti":"LEGACY_LOG_TAPE",".segy":"SEG-Y",".sgy":"SEG-Y",".zgy":"ZGY",".pet":"PETREL_PROJECT",".csv":"CSV",".txt":"TXT",".asc":"ASCII",".dat":"DAT_UNRESOLVED",".pdf":"PDF",".png":"PNG",".jpg":"JPEG",".jpeg":"JPEG",".tif":"TIFF",".tiff":"TIFF",".cgm":"CGM_PLOT",".zip":"ZIP",".tar":"TAR",".grdecl":"GRDECL",".inc":"SIMULATOR_INCLUDE",".shp":"GIS_SHP",".dbf":"GIS_DBF",".shx":"GIS_SHX",".prj":"GIS_PROJECTION",".xml":"XML",".json":"JSON",".parquet":"PARQUET"}
    return known.get(ext,(ext[1:].upper() if ext else "NO_EXTENSION")),"extension"
def classify(relative,fmt,content=""):
    context=re.sub(r"[_/\\-]+"," ",relative.lower())+" "+content.lower()
    labels={name for name,pat in RULES.items() if re.search(pat,context)}
    if fmt in {"LAS_ASCII","DLIS","LIS","LEGACY_LOG_TAPE","PETREL_WELL_LOG"}:labels.add("well_logs")
    if fmt in {"SEG-Y","ZGY","PROPRIETARY_SEISMIC_VOLUME"}:labels.add("seismic")
    if fmt=="PETREL_TRAJECTORY":labels.add("trajectory_well_header")
    if fmt.startswith("PETREL") or fmt in {"GRDECL","SIMULATOR_INCLUDE"}:labels.add("simulation_geomodel")
    if fmt=="DEX_PALEO":labels.add("biostratigraphy")
    if fmt in {"PDF","DOC","DOCX","PPT","PPTX","RTF","HTML"}:labels.add("documents")
    if fmt in {"PNG","JPEG","TIFF","CGM_PLOT","PDS_PLOT"}:labels.add("images_and_plots")
    if fmt in {"ZIP","TAR"}:labels.add("archives")
    if fmt in {"CSV","XLS","XLSX","ASCII","TXT"}:labels.add("tables_and_text")
    if fmt.startswith("GIS_"):labels.add("spatial_gis")
    if re.search(r"\bwell logs?\b|\bwireline\b",context):labels.add("well_logs")
    return sorted(labels or {"unclassified"})
def routes(labels):
    s=set(labels); out={"ai_agents","analysis_assistant"}
    if s & {"well_logs","core_lab"}:out.update(LOGTASKS);out.update({"well_log_viewer","user_training","ccus","digital_well_twin"})
    if s & {"production","drilling_telemetry","pressure_well_test"}:out.update({"edge_computing","digital_well_twin","user_training"})
    if s & {"pvt_fluids","seismic","geomechanics","simulation_geomodel","spatial_gis","trajectory_well_header","tops_stratigraphy"}:out.update({"ccus","digital_well_twin"})
    if "pvt_fluids" in s:out.update({"fluid_saturation","hc_pay_classification"})
    if "biostratigraphy" in s:out.add("lithology")
    if "trajectory_well_header" in s:out.add("well_log_viewer")
    if s=={"archives"}:return []
    return sorted(out)
def writecsv(path,rows,columns=None):
    rows=list(rows);path.parent.mkdir(parents=True,exist_ok=True)
    cols=columns or (list(rows[0]) if rows else ["file_id","source_path"])
    with path.open("w",encoding="utf-8-sig",errors="backslashreplace",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols,extrasaction="ignore");w.writeheader()
        for row in rows:
            w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items() if k in cols})
def run(snapshot):
    output=BASE/"catalogs"/snapshot
    output.mkdir(parents=True,exist_ok=False)
    old={r["source_path"]:r for r in map(json.loads,(BASE/"catalogs/niger_delta_audit_002/catalog.jsonl").open(encoding="utf-8"))}
    meta={r["source_path"]:r for r in map(json.loads,(BASE/"catalogs/content_metadata_001/metadata.jsonl").open(encoding="utf-8"))}
    rows=[];members=[];errors=[];dirs=[]
    def onerror(e):errors.append({"path":str(e.filename),"error":str(e)})
    import os
    for folder,subdirs,files in os.walk(ROOT,onerror=onerror,followlinks=False):
        dirs.append({"path":folder,"direct_files":len(files),"direct_subdirectories":len(subdirs)})
        for name in sorted(files):
            p=Path(folder)/name; rel=p.relative_to(ROOT).as_posix()
            try:
                st=p.stat(); skip=restricted(p);b=b"" if skip else p.open("rb").read(16384)
                fmt,basis=identify(p,b) if not skip else ("RESTRICTED_NONDATA","not_opened")
                prior=old.get(str(p),{})
                cached=prior if prior.get("bytes")==st.st_size and prior.get("modified_ns")==st.st_mtime_ns else {}
                m=meta.get(str(p),{}) if cached else {}
                content=""
                if fmt in {"LAS_ASCII","CSV","ASCII","TXT","DEX_PALEO","DAT_UNRESOLVED"}:content=b.decode("latin-1",errors="replace")
                sheetnames=[s["name"] for s in m.get("sheets",[])]
                if m.get("sheets"):content+=" "+json.dumps([{"name":s["name"],"rows":s["first_12_rows"][:3]} for s in m["sheets"]])
                labels=["restricted_nondata"] if skip else classify(rel,fmt,content)
                headers={};curves=cached.get("curves",[])
                field=cached.get("field","");well=cached.get("well","");uwi=cached.get("uwi","")
                if fmt=="LAS_ASCII" and not curves:
                    try:
                        headers,curves,_=las_header(p)
                        field=headers.get("FLD",{}).get("value","");well=headers.get("WELL",{}).get("value","");uwi=headers.get("UWI",{}).get("value","")
                    except Exception as e:errors.append({"path":str(p),"error":"LAS metadata: "+str(e)})
                row={"file_id":hashlib.sha256(rel.encode()).hexdigest()[:20],"source_path":str(p),"relative_path":rel,"collection":rel.split("/")[0],"bytes":st.st_size,"modified_ns":st.st_mtime_ns,"extension":p.suffix.lower() or "(none)","detected_format":fmt,"format_basis":basis,"varieties":labels,"variety_basis":"candidate_from_path_and_bounded_header_or_cached_workbook_metadata","feature_candidates":[] if skip else routes(labels),"field":field,"well":well,"uwi":uwi,"curves":curves,"workbook_sheets":sheetnames,"sha256":cached.get("sha256",""),"geography_gate":"disabled_by_user","split":"unassigned","training_ready":False,"inspection":"not_opened_restricted" if skip else "first_16384_bytes; cached_metadata_if_stat_matches","readiness":"review_identity_units_labels_and_decode" if not skip else "excluded_nondata"}
                rows.append(row)
                if fmt in {"ZIP","TAR"}:
                    try:
                        if fmt=="ZIP":
                            with zipfile.ZipFile(p) as z:
                                entries=[(i.filename,i.file_size,i.is_dir()) for i in z.infolist()]
                        else:
                            with tarfile.open(p,"r:*") as z:entries=[(i.name,i.size,i.isdir()) for i in z]
                        for n,size,isdir in entries:
                            if isdir:continue
                            mf,_=identify(Path(n),b"")
                            ml=classify(str(p)+"/"+n,mf)
                            members.append({"container":str(p),"member":n,"bytes":size,"format_hint":mf,"varieties":ml,"feature_candidates":routes(ml),"inspection":"member_name_only_not_extracted","unsafe_path":n.startswith(("/","\\")) or ".." in Path(n.replace("\\","/")).parts})
                    except Exception as e:errors.append({"path":str(p),"error":"archive index: "+str(e)})
            except Exception as e:errors.append({"path":str(p),"error":str(e)})
        if len(rows)%500< len(files):print(f"Inventoried {len(rows)} files",flush=True)
    (output/"catalog.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in rows),encoding="utf-8")
    columns=["file_id","source_path","relative_path","collection","bytes","extension","detected_format","format_basis","varieties","feature_candidates","field","well","uwi","workbook_sheets","split","training_ready","inspection"]
    writecsv(output/"MASTER_CATALOG.csv",rows,columns)
    writecsv(output/"DIRECTORIES.csv",dirs)
    writecsv(output/"ARCHIVE_MEMBERS.csv",members)
    for key,dirn in [("detected_format","by_format"),("collection","by_collection")]:
        groups=collections.defaultdict(list)
        for r in rows:groups[r[key]].append(r)
        for name,group in groups.items():writecsv(output/dirn/("group_"+re.sub(r"[^a-zA-Z0-9_-]","_",name)+".csv"),group,columns)
    for key,dirn in [("varieties","by_variety"),("feature_candidates","by_feature")]:
        for name in sorted({n for r in rows for n in r[key]}):writecsv(output/dirn/(name+".csv"),[r for r in rows if name in r[key]],columns)
    writecsv(output/"FIELD_WELL_INDEX.csv",[r for r in rows if r["field"] or r["well"]],columns)
    for task in TASKS:
        dest=BASE/"tasks"/task
        writecsv(dest/"catalogs"/"all_data_candidates.csv",[r for r in rows if task in r["feature_candidates"]],columns)
        for part in ["train","validation","test"]:(dest/part).mkdir(parents=True,exist_ok=True)
        (dest/"README.md").write_text("# "+task+"\n\nActive catalog: catalogs/all_data_candidates.csv from "+snapshot+".\nNo geographic admission filter. Entries are candidate source references, not training-ready records. Old region_candidates.csv / blocked_region_review.csv are historical and superseded. Raw data remains on F:. Split folders remain unassigned until identity, duplication, labels, units and independence checks are complete.\n",encoding="utf-8")
    summary={"created_utc":datetime.now(timezone.utc).isoformat(),"source_root":str(ROOT),"physical_files":len(rows),"physical_bytes":sum(r["bytes"] for r in rows),"directories":len(dirs),"archive_members":len(members),"geography_gate":"disabled","formats":dict(collections.Counter(r["detected_format"] for r in rows).most_common()),"extensions":dict(collections.Counter(r["extension"] for r in rows).most_common()),"varieties":dict(collections.Counter(n for r in rows for n in r["varieties"]).most_common()),"features":dict(collections.Counter(n for r in rows for n in r["feature_candidates"]).most_common()),"las_metadata_files":sum(bool(r["curves"]) for r in rows),"workbook_metadata_files":sum(bool(r["workbook_sheets"]) for r in rows),"errors":errors,"limitations":["Full directory traversal, bounded content inspection; no full numeric payload validation.","PDF/image domain classification is path-based; no PDF text extraction or OCR in this snapshot.","DLIS/LIS classified but channels not decoded. Proprietary files need export/adapters.","Archive member counts are separate, not additional unique training samples.","Variety/feature counts overlap and include path hints; candidate membership is not label availability.","Cached LAS hashes only; global duplicate detection remains pending."]}
    (output/"SUMMARY.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    for label in ["formats","extensions","varieties","features"]:writecsv(output/(label.upper()+"_COUNTS.csv"),[{"name":k,"files":v} for k,v in summary[label].items()])
    (BASE/"catalogs/CURRENT.json").write_text(json.dumps({"active_snapshot":snapshot,"path":str(output),"policy":"ALL_DATA_POLICY.json","historical_regional_catalogs":"superseded; preserved for audit"},indent=2),encoding="utf-8")
    (BASE/"ALL_DATA_POLICY.json").write_text(json.dumps({"geographic_admission_filter":False,"reason":"Latest user instruction: classify and use diverse data regardless of Niger Delta provenance","raw_sources":"read_only","catalog_membership":"candidate_only","training_requires":["verified canonical identity","measured or explicitly qualified target provenance","units and depth/time alignment","duplicate review","locked independent partitions"],"supersedes":"REGIONAL_DATA_POLICY.json"},indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--snapshot",required=True);run(parser.parse_args().snapshot)
