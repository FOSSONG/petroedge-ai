"""Join core records to log depth indexes without silently accepting aliases or units."""
import collections,csv,hashlib,json,math,re
from pathlib import Path
import numpy as np
from profile_log_core import OUT,depth_factor,family
def norm(s):return re.sub(r"[^A-Z0-9]","",str(s).upper())
def read(name):return [json.loads(s) for s in (OUT/name).read_text(encoding="utf-8").splitlines()]
def csvout(name,rows):
    rows=list(rows);cols=list(dict.fromkeys(k for r in rows for k in r)) if rows else ["status"]
    with (OUT/name).open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=cols);w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=True) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def shift_depth(sample,shifts):
    factor=depth_factor(sample["depth_unit"])
    if factor is None:return None,"depth_unit_unresolved",[]
    d=sample["core_depth"]*factor
    candidates=[s for s in shifts if norm(s["well"])==norm(sample["well_source"]) and s["core_top_m"]<=d<=s["core_base_m"]]
    core=sample["core_id_source"]
    if core:
        def cid(v):
            try:return str(int(float(v)))
            except (ValueError,TypeError):return norm(v).removeprefix("CORE")
        exact=[s for s in candidates if cid(s["core_id"])==cid(core)]
        if exact:candidates=exact
    if len(candidates)!=1:return None,("shift_unavailable" if not candidates else "shift_ambiguous"),candidates
    s=candidates[0];width=s["core_base_m"]-s["core_top_m"]
    if width<=0:return None,"invalid_shift_interval",candidates
    # Use the source endpoints; this is interval mapping, not learned target fitting.
    result=s["log_top_m"]+(d-s["core_top_m"])*(s["log_base_m"]-s["log_top_m"])/width
    return result,"documented_shift_applied",candidates
def fingerprint(sample):
    obj={k:sample[k] for k in ["well_source","sample_id_source","core_id_source","core_depth","depth_unit","description_source","lithology_class_source"]}
    obj["targets"]=[{k:t[k] for k in ["task","value","unit","condition"]} for t in sample["targets"]]
    return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()
def usable(v):return np.isfinite(v) and v not in (-999,-999.25,-9999,-999.75,-99999)
def run():
    profiles=read("log_profiles.jsonl");samples=read("core_samples.jsonl");shifts=read("core_shifts.jsonl")
    hashes=collections.defaultdict(list)
    for p in profiles:
        if p.get("sha256"):hashes[p["sha256"]].append(p)
    duplicate_log=[{"sha256":h,"file_id":p["file_id"],"source_path":p["source_path"],"group_files":len(group)} for h,group in hashes.items() if len(group)>1 for p in group]
    csvout("DUPLICATE_LOG_FILES.csv",duplicate_log)
    canonical=[];seen=set()
    for p in profiles:
        key=p.get("sha256",p["file_id"])
        if key in seen:continue
        seen.add(key);canonical.append(p)
    wellframes=collections.defaultdict(list);channels=[];files=[]
    for p in profiles:
        fams=set()
        for fr in p["frames"]:
            for c in fr["channels"]:
                fam=family(c["name"])
                if fam and c.get("usable_candidate_count",0)>0:fams.add(fam)
                channels.append({"file_id":p["file_id"],"source_path":p["source_path"],"well":p.get("well",""),"frame_id":fr["frame_id"],"payload_status":fr["payload_status"],"channel":c["name"],"family_candidate":fam,"unit":c["unit"],"rows":c.get("rows"),"nonfinite":c.get("nonfinite"),"suspected_sentinel":c.get("suspected_sentinel"),"usable_candidate_count":c.get("usable_candidate_count"),"min":c.get("finite_min"),"max":c.get("finite_max")})
        files.append({"file_id":p["file_id"],"source_path":p["source_path"],"format":p["detected_format"],"status":p["status"],"sha256":p.get("sha256",""),"well":p.get("well",""),"field":p.get("field",""),"uwi":p.get("uwi",""),"frames":len(p["frames"]),"decoded_frames":sum(f["payload_status"]=="decoded" for f in p["frames"]),"families_with_observations":sorted(fams),"errors":p.get("errors",[])})
    for p in canonical:
        names=str(p.get("well","")).split(" | ")
        for name in names:
            if len(names)==1 and name.strip():
                for f in p["frames"]:wellframes[norm(name)].append((p,f))
    csvout("LOG_FILES.csv",files);csvout("CURVE_COVERAGE.csv",channels)
    unique=[];duplicates=[];seen={}
    for s in samples:
        key=fingerprint(s)
        if key in seen:duplicates.append({"sample_record_id":s["sample_record_id"],"source_path":s["source_path"],"sheet":s["sheet"],"excel_row":s["excel_row"],"same_as_sample_record":seen[key]})
        else:unique.append(s);seen[key]=s["sample_record_id"]
    csvout("DUPLICATE_CORE_RECORDS.csv",duplicates)
    # Flag possible shared specimens even when labels/conditions differ; do not collapse them.
    specimen=collections.defaultdict(list)
    for s in unique:specimen[(norm(s["well_source"]),s["core_depth"])].append(s)
    csvout("REPEATED_SPECIMEN_REVIEW.csv",[{"well_key":k[0],"core_depth_source_units":k[1],"records":[{"id":s["sample_record_id"],"path":s["source_path"],"row":s["excel_row"],"unit":s["depth_unit"]} for s in v]} for k,v in specimen.items() if len(v)>1])
    indexcache={};matches=[];normalized=[]
    for s in unique:
        candidates=wellframes.get(norm(s["well_source"]),[])
        target_depth,status,evidence=shift_depth(s,shifts)
        options=[]
        if target_depth is not None:
            for p,f in candidates:
                idx=f.get("index_artifact")
                if not idx or f.get("index_kind")!="depth" or str(f.get("index_name","")).upper().startswith("TVD"):continue
                if idx not in indexcache:
                    with np.load(idx,allow_pickle=False) as z:data={k:z[k] for k in z.files}
                    order=np.argsort(data["depth_m"]);indexcache[idx]={k:v[order] for k,v in data.items()}
                data=indexcache[idx];depth=data["depth_m"]
                if len(depth)==0:continue
                j=int(np.searchsorted(depth,target_depth));poss=[i for i in (j-1,j) if 0<=i<len(depth)]
                nearest=min(poss,key=lambda i:abs(depth[i]-target_depth))
                delta=float(abs(depth[nearest]-target_depth))
                vals={k:float(v[nearest]) for k,v in data.items() if k!="depth_m" and usable(float(v[nearest]))}
                options.append({"source_path":p["source_path"],"file_id":p["file_id"],"sha256":p.get("sha256",""),"frame":f["frame_id"],"distance_m":delta,"log_depth_m":float(depth[nearest]),"features_raw":vals,"feature_count":len(vals),"depth_duplicate_count":f.get("duplicate_index_count",0)})
        within=[r for r in options if r["distance_m"]<=.25]
        best=min(within,key=lambda r:(-r["feature_count"],r["distance_m"],r["file_id"],r["frame"])) if within else (min(options,key=lambda r:r["distance_m"]) if options else None)
        flags=[]
        if not candidates:flags.append("source_well_name_has_no_log_header_match")
        if status!="documented_shift_applied":flags.append(status)
        if not within:flags.append("no_decoded_log_sample_within_provisional_0.25m")
        if best and best["feature_count"]<3:flags.append("fewer_than_three_common_curve_families_at_depth")
        if best and best["depth_duplicate_count"]:flags.append("duplicate_log_depths_require_review")
        tasks=sorted({t["task"] for t in s["targets"]}|({"lithology"} if s["lithology_class_source"] or s["description_source"] else set()))
        row={"sample_record_id":s["sample_record_id"],"well_source":s["well_source"],"core_source_path":s["source_path"],"sheet":s["sheet"],"excel_row":s["excel_row"],"core_depth":s["core_depth"],"core_depth_unit":s["depth_unit"],"shifted_log_depth_m":target_depth,"shift_status":status,"shift_evidence":evidence,"name_matched_log_files":len({p["file_id"] for p,f in candidates}),"within_tolerance_frames":len(within),"best_log_source":best["source_path"] if best else "","best_log_file_id":best["file_id"] if best else "","best_log_frame":best["frame"] if best else "","distance_m":best["distance_m"] if best else None,"feature_families":sorted(best["features_raw"]) if best else [],"features_raw":best["features_raw"] if best else {},"target_tasks":tasks,"structural_status":"source_name_shift_and_sample_supported" if candidates and within else "unresolved","blockers":flags,"training_ready":False,"remaining_qualification":"canonical identity; unit/curve semantic QC; label conditions/taxonomy; grouped split"}
        matches.append(row)
        for t in s["targets"]:
            value=t["value"];u=t["unit"];normalizedvalue=value/100 if u=="%" else value if u in {"V/V","mD"} else None
            valid=normalizedvalue is not None and (0<=normalizedvalue<=1 if t["task"] in {"porosity","oil_saturation","water_saturation"} else normalizedvalue>=0)
            normalized.append({"sample_record_id":s["sample_record_id"],"well_source":s["well_source"],"source_path":s["source_path"],"sheet":s["sheet"],"cell":t["cell"],"task":t["task"],"value_raw":value,"unit_raw":u,"value_normalized":normalizedvalue,"unit_normalized":"mD" if u=="mD" else "fraction" if u in {"%","V/V"} else "unresolved","unit_and_range_check":"passes_basic_check" if valid else "needs_review","condition":t["condition"],"provenance_status":t["status"]})
    csvout("LOG_CORE_MATCH_REVIEW.csv",matches);csvout("CORE_TARGET_VALUES.csv",normalized)
    csvout("CORE_SHEET_REVIEW.csv",read("core_sheet_coverage.jsonl"))
    wells=[]
    for name in sorted({s["well_source"] for s in unique}):
        m=[r for r in matches if r["well_source"]==name];u=[r for r in unique if r["well_source"]==name]
        wells.append({"well_source":name,"unique_source_rows":len(u),"source_name_matches":sum(r["name_matched_log_files"]>0 for r in m),"documented_shift_rows":sum(r["shift_status"]=="documented_shift_applied" for r in m),"within_0_25m_rows":sum(r["within_tolerance_frames"]>0 for r in m),"within_0_25m_and_3_families":sum(r["within_tolerance_frames"]>0 and len(r["feature_families"])>=3 for r in m),"porosity_rows":sum(any(t["task"]=="porosity" for t in r["targets"]) for r in u),"permeability_rows":sum(any(t["task"]=="permeability" for t in r["targets"]) for r in u),"explicit_lithology_rows":sum(bool(r["lithology_class_source"]) for r in u),"description_rows":sum(bool(r["description_source"]) for r in u),"oil_saturation_rows":sum(any(t["task"]=="oil_saturation" for t in r["targets"]) for r in u),"water_saturation_rows":sum(any(t["task"]=="water_saturation" for t in r["targets"]) for r in u),"blockers":dict(collections.Counter(b for r in m for b in r["blockers"]))})
    csvout("WELL_MODEL_READINESS.csv",wells)
    result={"log_files_profiled":len(profiles),"log_file_statuses":dict(collections.Counter(p["status"] for p in profiles)),"log_formats":dict(collections.Counter(p["detected_format"] for p in profiles)),"frame_statuses":dict(collections.Counter(f["payload_status"] for p in profiles for f in p["frames"])),"exact_log_duplicate_groups":sum(len(v)>1 for v in hashes.values()),"exact_log_duplicate_extra_files":sum(len(v)-1 for v in hashes.values()),"core_source_rows":len(samples),"duplicate_core_rows":len(duplicates),"unique_core_source_rows":len(unique),"core_source_well_names":len(wells),"shifted_sample_matches":sum(r["within_tolerance_frames"]>0 for r in matches),"shifted_matches_with_3_families":sum(r["within_tolerance_frames"]>0 and len(r["feature_families"])>=3 for r in matches),"training_approved_rows":0,"provisional_tolerance_m":.25,"targets_by_task":dict(collections.Counter(r["task"] for r in normalized))}
    (OUT/"READINESS_SUMMARY.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2),flush=True)
if __name__=="__main__":run()
