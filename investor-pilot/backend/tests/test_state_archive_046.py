import hashlib,json,sqlite3,zipfile
import pytest
from app.services.state_archive import create,restore,verify,upload_gcs

def test_offline_archive_survives_restore_and_never_overwrites(tmp_path):
 root=tmp_path/"state";(root/"data").mkdir(parents=True)
 with sqlite3.connect(root/"data"/"accounts.sqlite3") as conn:
  conn.execute("CREATE TABLE users (id TEXT)");conn.execute("INSERT INTO users VALUES ('owner')")
 (root/"dataset_store").mkdir();(root/"dataset_store"/"logs.csv").write_text("GR\n20\n")
 (root/".env").write_text("secret-not-an-archive-member")
 out=tmp_path/"state.zip"
 with pytest.raises(ValueError):create(root,out)
 assert create(root,out,offline=True)["files"]==2
 restored=tmp_path/"restored";assert restore(out,restored)==2
 with sqlite3.connect(restored/"data"/"accounts.sqlite3") as conn:assert conn.execute("SELECT id FROM users").fetchone()[0]=="owner"
 assert not (restored/".env").exists()
 with pytest.raises(ValueError):restore(out,restored)

def test_traversal_and_corruption_rejected_before_restore(tmp_path):
 for name,contents,checksum in [("../escape",b"x",hashlib.sha256(b"x").hexdigest()),("data/file",b"x","bad")]:
  archive=tmp_path/(checksum[:5]+".zip")
  with zipfile.ZipFile(archive,"w") as z:
   z.writestr(name,contents);z.writestr("state-manifest.json",json.dumps({"version":1,"files":{name:{"bytes":1,"sha256":checksum}}}))
  with pytest.raises(ValueError):restore(archive,tmp_path/"unsafe")
  assert not (tmp_path/"unsafe").exists()

def test_gcs_backup_is_immutable_and_hash_tagged(tmp_path):
 from types import SimpleNamespace
 root=tmp_path/"state";root.mkdir();out=tmp_path/"backup.zip";create(root,out,offline=True)
 calls=[]
 blob=SimpleNamespace(metadata={},generation=7,upload_from_filename=lambda *a,**k:calls.append(k),reload=lambda:None)
 client=SimpleNamespace(bucket=lambda _:SimpleNamespace(blob=lambda _:blob))
 result=upload_gcs(out,"private-bucket","backup.zip",client=client)
 assert calls[0]["if_generation_match"]==0 and result["sha256"]==hashlib.sha256(out.read_bytes()).hexdigest()
