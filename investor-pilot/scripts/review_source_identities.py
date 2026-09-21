"""Resolve only identities directly supported by source header fields."""
import collections,json,re
from pathlib import Path
from qualify_log_core import AUDIT,OUT,outcsv,jwrite,canon_freeman
MISSING={"","UNKNOWN","NONE","NULL","N/A"}
def header_identity(headers,key):
    values=[(k,str(v.get("value","")).strip()) for k,v in headers.items() if k.split(":")[0]==key and str(v.get("value","")).strip().upper() not in MISSING]
    distinct={v.upper() for k,v in values}
    return (values[0][1],"consistent_source_header",values) if len(distinct)==1 else ("","conflicting_source_headers" if values else "missing",values)
def token(x):return re.sub("[^A-Z0-9]","",str(x).upper())
def run():
    logs=[json.loads(s) for s in (AUDIT/"log_profiles.jsonl").read_text().splitlines()]
    evidence=[];corrections=[];uwis={}
    for p in (AUDIT/"core_workbooks").glob("*.json"):
        book=json.loads(p.read_text())
        if "core shift" not in book["source_path"].lower():continue
        for sh in book["sheets"]:
            for ri,row in enumerate(sh["rows"],1):
                if ri>1 and len(row)>1 and str(row[0]).startswith("NO "):
                    uwis[token(row[0])]={"uwi":str(row[0]),"well":str(row[1]),"source":book["source_path"],"sheet":sh["name"],"row":ri}
    for log in logs:
        h=log.get("well_header",{})
        well,status,fields=header_identity(h,"WELL")
        if well and not log.get("well"):
            corrections.append({"file_id":log["file_id"],"source_path":log["source_path"],"previous_well":"","resolved_well":well,"basis":"all duplicate WELL header values agree","header_fields":fields})
        if log.get("well") and well and log["well"].upper()!=well.upper():status="profile_header_disagreement"
        identity={"file_id":log["file_id"],"source_path":log["source_path"],"well_source":well or log.get("well",""),"header_identity_status":status,"source_UWI":log.get("uwi",""),"join_status":"not_reviewed","evidence":[]}
        uwi=log.get("uwi","")
        hit=uwis.get(token(uwi)) or uwis.get(token(well))
        if hit:
            identity.update(canonical_well=hit["well"],join_status="source_UWI_link_supported",evidence=[hit])
            chans=[c["name"] for f in log["frames"] for c in f["channels"]]
            identity["curve_use"]="interpretation_or_rock_physics_provenance_review_required" if any(c.startswith("LFP_") or c in {"KLOGH","PHIF"} for c in chans) else "numerical_curve_QC_required"
        elif canon_freeman(well) and str(log.get("field","")).upper()=="FREEMAN":
            identity.update(canonical_well=canon_freeman(well),join_status="field_supported_zero_padding_equivalence",evidence=[{"field_header":log.get("field"),"well_header":well}])
        if "GABO-13_lcs" in log["source_path"]:
            identity.update(join_status="blocked_filename_header_conflict",evidence=[{"filename_well":"GABO-13","source_header_well":well}])
        evidence.append(identity)
    outcsv(OUT/"HEADER_IDENTITY_CORRECTIONS.csv",corrections)
    outcsv(OUT/"WELL_IDENTITY_REVIEW.csv",evidence)
    jwrite(OUT/"IDENTITY_REVIEW_SUMMARY.json",{"duplicate_header_identities_recovered":len(corrections),"source_UWI_links":sum(r["join_status"]=="source_UWI_link_supported" for r in evidence),"filename_header_conflicts":sum(r["join_status"]=="blocked_filename_header_conflict" for r in evidence),"notes":["Country/UWI prefixes are retained; links compare full normalized source UWI.","Recovered names do not resolve missing core depth units or prove curve suitability.","Source records and old audit are retained; corrected extraction supersedes affected identities."]})
    print(json.dumps(json.loads((OUT/"IDENTITY_REVIEW_SUMMARY.json").read_text())))
if __name__=="__main__":run()
