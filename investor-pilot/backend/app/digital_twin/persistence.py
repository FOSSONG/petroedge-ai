"""Single-worker durable twin snapshots. SQLite commits each store update atomically."""
import os,json,sqlite3
from pathlib import Path
from contextlib import closing

def load(key):
 path=os.getenv("PETROEDGE_TWIN_STORE")
 if not path:return {}
 Path(path).parent.mkdir(parents=True,exist_ok=True)
 with closing(sqlite3.connect(path)) as c:
  c.execute("CREATE TABLE IF NOT EXISTS twin_documents (key TEXT PRIMARY KEY,document TEXT NOT NULL)");c.commit()
  row=c.execute("SELECT document FROM twin_documents WHERE key=?",(key,)).fetchone()
 return json.loads(row[0]) if row else {}

def save(key,document):
 path=os.getenv("PETROEDGE_TWIN_STORE")
 if not path:return
 with closing(sqlite3.connect(path,timeout=10)) as c:
  with c:c.execute("INSERT OR REPLACE INTO twin_documents VALUES (?,?)",(key,json.dumps(document,allow_nan=False)))
