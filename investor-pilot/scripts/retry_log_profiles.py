"""One retry after LAS format routing and numeric-engine improvements."""
import json,subprocess,sys,concurrent.futures
from pathlib import Path
from profile_log_core import OUT
rows=[]
for p in (OUT/"files").glob("*.json"):
 r=json.loads(p.read_text())
 if r["detected_format"]=="LAS_ASCII" and r["status"] in {"error","timeout","worker_failed"}:rows.append((p,r))
def retry(item):
 p,r=item;dest=OUT/"before_parser_retry";dest.mkdir(exist_ok=True)
 (dest/p.name).write_bytes(p.read_bytes())
 try:
  with (OUT/"parser_logs"/(r["file_id"]+"_retry.log")).open("w",encoding="utf-8") as f:
   done=subprocess.run([sys.executable,"-B",str(Path(__file__).with_name("profile_log_core.py")),"--worker",r["file_id"]],stdout=f,stderr=f,timeout=120)
  after=json.loads(p.read_text())
  return {"file_id":r["file_id"],"before":r["status"],"after":after["status"]}
 except subprocess.TimeoutExpired:return {"file_id":r["file_id"],"before":r["status"],"after":"timeout_retained"}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:results=list(ex.map(retry,rows))
(OUT/"PARSER_RETRY.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
print(json.dumps({"retried":len(results),"results":__import__("collections").Counter(r["after"] for r in results)}),flush=True)
