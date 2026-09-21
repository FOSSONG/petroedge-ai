"""Profile LAS and DLIS without modifying sources. Per-file subprocess isolation."""
import re
import argparse,collections,concurrent.futures,csv,hashlib,json,logging,os,subprocess,sys,time
from pathlib import Path
import numpy as np
BASE=Path(r"E:\PETROEDGE_AI\codex\data")
OUT=BASE/"readiness/log_core_001"
CAT=BASE/"catalogs/all_data_003/catalog.jsonl"
FAMILIES={"gamma_ray":{"GR","CGR","SGR","GAM","GAMMA"},"density":{"RHOB","RHOZ","DEN","DENS","ZDEN"},"neutron":{"NPHI","TNPH","CNC","CNL","NEU","NPOR"},"sonic":{"DT","DTC","DTCO","AC","DTS"},"resistivity":{"RT","RDEP","ILD","LLD","AT90","AT60","RESD","RESDP","RD","ILD_LOG","RDEEP"},"caliper":{"CALI","CAL","HCAL","CALS"}}
def family(name):
    n=str(name).upper().split(":")[0]
    if n.endswith("_COMP"):n=n[:-5]
    return next((k for k,v in FAMILIES.items() if n in v),"")
def depth_factor(unit):
    u=str(unit).strip().upper().replace(" ","")
    return {"M":1.0,"METRE":1.0,"METRES":1.0,"METER":1.0,"METERS":1.0,"FT":.3048,"F":.3048,"FEET":.3048,"FOOT":.3048,"IN":.0254,"INCH":.0254,"0.1IN":.00254,".1IN":.00254,"CM":.01,"MM":.001}.get(u)
def stats(a):
    a=np.asarray(a)
    if a.ndim!=1 or a.dtype.kind not in "iuf":return {"numeric_scalar":False,"shape":list(a.shape)}
    finite=np.isfinite(a);v=a[finite]
    suspected=np.isin(a,[-999.25,-999,-9999,-999.75,-99999])
    clean=a[finite&~suspected]
    return {"numeric_scalar":True,"rows":len(a),"nonfinite":int((~finite).sum()),"suspected_sentinel":int(suspected.sum()),"finite_min":float(v.min()) if len(v) else None,"finite_max":float(v.max()) if len(v) else None,"usable_candidate_count":len(clean),"p01_candidate":float(np.quantile(clean,.01)) if len(clean) else None,"p99_candidate":float(np.quantile(clean,.99)) if len(clean) else None}
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=True,allow_nan=False,default=str),encoding="utf-8")
def depth_info(a,unit,idxpath,channels,kind):
    a=np.asarray(a,dtype=float);good=np.isfinite(a)&~np.isin(a,[-999.25,-999,-9999,-99999])
    d=a[good];factor=depth_factor(unit)
    result={"index_kind":kind,"index_unit":str(unit),"index_min":float(d.min()) if len(d) else None,"index_max":float(d.max()) if len(d) else None,"index_rows":len(d),"duplicate_index_count":int(len(d)-len(np.unique(d))),"monotonic_increasing":bool(np.all(np.diff(d)>0)) if len(d)>1 else False,"monotonic_decreasing":bool(np.all(np.diff(d)<0)) if len(d)>1 else False,"depth_factor_to_m":factor}
    if factor is not None and kind=="depth" and len(d):
        d=d*factor
        data={"depth_m":d}
        for name,values in channels.items():
            if len(values)==len(a):data[name]=np.asarray(values)[good]
        np.savez_compressed(idxpath,**data)
        result.update(depth_min_m=float(d.min()),depth_max_m=float(d.max()),index_artifact=str(idxpath),median_step_m=float(np.median(np.abs(np.diff(d)))) if len(d)>1 else None)
    return result
def process(row):
    p=Path(row["source_path"]);st=p.stat()
    r={k:row[k] for k in ["file_id","source_path","relative_path","collection","detected_format"]}
    r.update(bytes=st.st_size,modified_ns=st.st_mtime_ns,frames=[],errors=[],status="decoded",parser_versions={})
    with p.open("rb") as f:r["sha256"]=hashlib.file_digest(f,"sha256").hexdigest()
    logging.disable(logging.WARNING)
    if row["detected_format"]=="LAS_ASCII":
        import lasio
        r["parser_versions"]["lasio"]=lasio.__version__
        with p.open("rb") as stream:prefix=stream.read(65536).decode("latin-1")
        if re.search(r"(?im)^\s*VERS\s*\.\s*3(?:\.0)?\b",prefix):
            from data_catalog import las_header
            heads,curves,_=las_header(p)
            r.update(status="metadata_only_las3",well=heads.get("WELL",{}).get("value",""),field=heads.get("FLD",{}).get("value",""),uwi=heads.get("UWI",{}).get("value",""),well_header=heads,sections=re.findall(r"(?m)^~[^\r\n]+",prefix),errors=["LAS 3 multi-section/time-series requires a typed adapter; not sent to LAS 2 numeric parser"])
            return r
        las=lasio.read(str(p),engine="numpy")
        def head(k):
            values=[str(c.value).strip() for c in las.well if c.mnemonic.split(":")[0]==k and str(c.value).strip().upper() not in {"","UNKNOWN","NONE","NULL","N/A"}]
            return values[0] if len({v.upper() for v in values})==1 else ""
        r.update(well=head("WELL"),field=head("FLD"),uwi=head("UWI"),api=head("API"))
        r["well_header"]={c.mnemonic:{"value":str(c.value),"unit":str(c.unit),"description":str(c.descr)} for c in las.well}
        a=las.data;curves=[];selected={}
        for i,c in enumerate(las.curves):
            item={"name":c.mnemonic,"unit":c.unit,"description":c.descr,"family":family(c.mnemonic),**stats(a[:,i])}
            curves.append(item)
            if item["family"] and item["family"] not in selected:selected[item["family"]]=a[:,i]
        fr={"frame_id":"LAS","channels":curves,"rows":len(a),"payload_status":"decoded"}
        if len(las.curves):
            c=las.curves[0];kind="depth" if c.mnemonic.upper().split(":")[0] in {"DEPTH","DEPT","DEP","MD","TDEP","TVD","TVDSS"} else "unknown"
            fr.update(depth_info(a[:,0],c.unit,OUT/"indexes"/(row["file_id"]+"_LAS.npz"),selected,kind))
            fr["index_name"]=c.mnemonic
        r["frames"].append(fr)
    else:
        from dlisio import dlis
        import dlisio
        r["parser_versions"]["dlisio"]=dlisio.__version__
        origins=[];counter=0
        with dlis.load(str(p)) as fs:
            for li,lf in enumerate(fs):
                for o in lf.origins:origins.append({"well":str(o.well_name or ""),"uwi":str(o.well_id or ""),"field":str(o.field_name or "")})
                for fr in lf.frames:
                    fid=f"LF{li}_F{counter}";counter+=1
                    item={"frame_id":fid,"name":fr.name,"index_name":str(fr.index),"index_type":str(fr.index_type),"spacing_header":str(fr.spacing),"channels":[],"payload_status":"metadata_only"}
                    for c in fr.channels:
                        item["channels"].append({"name":c.name,"unit":str(c.units),"description":str(c.long_name),"family":family(c.name),"dimension":list(c.dimension)})
                    try:
                        dtype=fr.dtype()
                        # Bound array expansion; multidimensional waveforms remain metadata-only.
                        scalar=all(not dtype.fields[n][0].shape for n in dtype.names)
                        if not scalar:item["payload_status"]="multidimensional_frame_requires_specialist_decoder"
                        elif st.st_size>96*1024**2 or dtype.itemsize>8192:item["payload_status"]="deferred_large_frame"
                        else:
                            arr=fr.curves()
                            item.update(rows=len(arr),payload_status="decoded")
                            selected={}
                            for ci,c in enumerate(fr.channels):
                                val=arr[dtype.names[ci+1]]
                                item["channels"][ci].update(stats(val))
                                fam=family(c.name)
                                if fam and fam not in selected and val.ndim==1:selected[fam]=val
                            if fr.index_type and fr.channels:
                                c=fr.channels[0];kind="depth" if "DEPTH" in str(fr.index_type).upper() else "time_or_other"
                                item.update(depth_info(arr[dtype.names[1]],c.units,OUT/"indexes"/(row["file_id"]+"_"+fid+".npz"),selected,kind))
                    except Exception as e:item["payload_status"]="decode_error";item["error"]=str(e)[:2000]
                    r["frames"].append(item)
        r["origins"]=origins
        for k in ["well","uwi","field"]:r[k]=" | ".join(sorted({o[k] for o in origins if o[k]}))
    after=p.stat()
    if after.st_size!=st.st_size or after.st_mtime_ns!=st.st_mtime_ns:raise ValueError("Source changed during profiling")
    return r
def worker(file_id):
    row=next(r for r in map(json.loads,CAT.read_text(encoding="utf-8").splitlines()) if r["file_id"]==file_id)
    try:r=process(row)
    except Exception as e:r={k:row[k] for k in ["file_id","source_path","relative_path","collection","detected_format"]};r.update(status="error",errors=[str(e)[:3000]],frames=[])
    dump(OUT/"files"/(file_id+".json"),r)
def run():
    OUT.mkdir(parents=True,exist_ok=True)
    for d in ["files","indexes","parser_logs"]:(OUT/d).mkdir(exist_ok=True)
    rows=[r for r in map(json.loads,CAT.read_text(encoding="utf-8").splitlines()) if r["detected_format"] in {"LAS_ASCII","DLIS"}]
    def launch(row):
        dest=OUT/"files"/(row["file_id"]+".json")
        if dest.exists():return "cached"
        with (OUT/"parser_logs"/(row["file_id"]+".log")).open("w",encoding="utf-8") as f:
            try:
                result=subprocess.run([sys.executable,"-B",str(Path(__file__).resolve()),"--worker",row["file_id"]],stdout=f,stderr=f,timeout=120)
                if result.returncode and not dest.exists():dump(dest,dict(row,status="worker_failed",errors=[f"exit {result.returncode}"],frames=[]))
            except subprocess.TimeoutExpired:dump(dest,dict(row,status="timeout",errors=["120 second per-file resource limit"],frames=[]))
        return "done"
    start=time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for i,_ in enumerate(ex.map(launch,rows),1):
            if i%25==0:print(json.dumps({"completed":i,"total":len(rows),"elapsed_seconds":round(time.time()-start)}),flush=True)
    prof=[json.loads((OUT/"files"/(r["file_id"]+".json")).read_text()) for r in rows]
    (OUT/"log_profiles.jsonl").write_text("".join(json.dumps(r,ensure_ascii=True)+"\n" for r in prof),encoding="utf-8")
    summary={"files":len(rows),"statuses":dict(collections.Counter(r["status"] for r in prof)),"frames":dict(collections.Counter(f["payload_status"] for r in prof for f in r["frames"])),"elapsed_seconds":round(time.time()-start)}
    dump(OUT/"LOG_PROFILE_SUMMARY.json",summary);print(json.dumps(summary),flush=True)
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--worker");args=p.parse_args()
    worker(args.worker) if args.worker else run()
