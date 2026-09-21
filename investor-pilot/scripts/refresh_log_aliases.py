"""Refresh profiles made before the verified composite-curve aliases were added."""
import json,subprocess,sys,concurrent.futures
from pathlib import Path
from profile_log_core import OUT,family
paths=[]
for p in (OUT/"files").glob("*.json"):
 r=json.loads(p.read_text())
 if r["status"]=="decoded" and any(family(c["name"])!=c.get("family","") for f in r["frames"] for c in f["channels"]):paths.append((p,r["file_id"]))
def refresh(item):
 p,fid=item
 backup=OUT/"pre_alias_profiles";backup.mkdir(exist_ok=True)
 (backup/p.name).write_bytes(p.read_bytes())
 with (OUT/"parser_logs"/(fid+"_alias_refresh.log")).open("w",encoding="utf-8") as f:
  result=subprocess.run([sys.executable,"-B",str(Path(__file__).with_name("profile_log_core.py")),"--worker",fid],stdout=f,stderr=f,timeout=120)
 return {"file_id":fid,"exit_code":result.returncode}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:result=list(ex.map(refresh,paths))
(OUT/"ALIAS_REFRESH.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps({"refreshed":len(result),"failures":sum(r["exit_code"]!=0 for r in result)}),flush=True)
