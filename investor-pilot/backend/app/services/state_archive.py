"""Verified offline state archives. Backups are not a live Cloud Run database.

Caller must stop all application writers before archiving or restoring.
No secrets/config/source code are included by default. Restore is only to a new directory.
"""
import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path, PurePosixPath

STATE_DIRS=("data","dataset_store","analysis_store","model_store","uploads")
def digest(path):
 with Path(path).open("rb") as handle:return hashlib.file_digest(handle,"sha256").hexdigest()

def create(root, output, *, offline=False):
 if not offline:raise ValueError("Stop application writers and explicitly confirm offline=True.")
 root=Path(root).resolve();output=Path(output).resolve()
 if output.is_relative_to(root):raise ValueError("Archive destination must be outside the state root.")
 files=[]
 for folder in STATE_DIRS:
  directory=root/folder
  if directory.exists():files += [p for p in directory.rglob("*") if p.is_file()]
 files += list(root.glob("*.db"))+list(root.glob("*.sqlite3"))
 manifest={}
 for path in sorted(set(files)):
  if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError("Linked state files are not supported.")
  if path.name.endswith(("-wal","-shm","-journal")):
   if path.stat().st_size:raise ValueError("Database journal present; cleanly stop and checkpoint databases first.")
   continue
  if path.name.startswith(".env") or path.suffix.lower() in (".pem",".key"):raise ValueError("Unexpected credential file inside state.")
  with path.open("rb") as handle:magic=handle.read(16)
  if magic==b"SQLite format 3\x00":
   with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as connection:
    if connection.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise ValueError("Database integrity check failed.")
  manifest[path.relative_to(root).as_posix()]={"sha256":digest(path),"bytes":path.stat().st_size}
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,"x",compression=zipfile.ZIP_DEFLATED) as archive:
  for name in manifest:archive.write(root/name,name)
  archive.writestr("state-manifest.json",json.dumps({"version":1,"files":manifest},indent=2))
 verify(output)
 return {"files":len(manifest),"sha256":digest(output),"bytes":output.stat().st_size}

def verify(archive_path):
 with zipfile.ZipFile(archive_path) as archive:
  names=archive.namelist()
  if len(names)!=len(set(names)):raise ValueError("Duplicate archive members.")
  manifest=json.loads(archive.read("state-manifest.json"))
  if manifest.get("version")!=1:raise ValueError("Unsupported state archive version.")
  files=manifest["files"]
  if set(names)!=set(files)|{"state-manifest.json"}:raise ValueError("Unlisted archive member.")
  for name,meta in files.items():
   path=PurePosixPath(name)
   if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:raise ValueError("Unsafe archive path.")
   info=archive.getinfo(name)
   if info.file_size!=meta["bytes"]:raise ValueError("State size mismatch.")
   with archive.open(name) as handle:
    if hashlib.file_digest(handle,"sha256").hexdigest()!=meta["sha256"]:raise ValueError("State checksum mismatch.")
  return manifest

def restore(archive_path,destination):
 manifest=verify(archive_path);destination=Path(destination)
 if destination.exists():raise ValueError("Restore only into a new directory; existing state is never overwritten.")
 destination.mkdir(parents=True)
 with zipfile.ZipFile(archive_path) as archive:
  for name in manifest["files"]:
   path=destination/name;path.parent.mkdir(parents=True,exist_ok=True)
   with archive.open(name) as source,path.open("xb") as target:
    import shutil
    shutil.copyfileobj(source,target)
 return len(manifest["files"])

def upload_gcs(archive_path,bucket_name,object_name,*,client=None):
 """Immutable private backup object; a configured GCS client/bucket is required."""
 verify(archive_path)
 if not bucket_name or not object_name:raise ValueError("Bucket and object name are required.")
 if client is None:
  from google.cloud import storage
  client=storage.Client()
 blob=client.bucket(bucket_name).blob(object_name)
 blob.metadata={"sha256":digest(archive_path),"purpose":"offline-state-backup"}
 blob.upload_from_filename(str(archive_path),if_generation_match=0,checksum="auto")
 blob.reload()
 if blob.metadata.get("sha256")!=digest(archive_path):raise ValueError("Backup metadata verification failed.")
 return {"bucket":bucket_name,"object":object_name,"generation":str(blob.generation),"sha256":blob.metadata["sha256"]}

if __name__=="__main__":
 import argparse
 parser=argparse.ArgumentParser(description=__doc__)
 sub=parser.add_subparsers(dest="command",required=True)
 pack=sub.add_parser("create");pack.add_argument("root");pack.add_argument("archive");pack.add_argument("--offline",action="store_true")
 check=sub.add_parser("verify");check.add_argument("archive")
 unpack=sub.add_parser("restore");unpack.add_argument("archive");unpack.add_argument("destination")
 upload=sub.add_parser("upload-gcs");upload.add_argument("archive");upload.add_argument("bucket");upload.add_argument("object")
 args=parser.parse_args()
 if args.command=="create":result=create(args.root,args.archive,offline=args.offline)
 elif args.command=="verify":result={"files":len(verify(args.archive)["files"])}
 elif args.command=="restore":result={"restored_files":restore(args.archive,args.destination)}
 else:result=upload_gcs(args.archive,args.bucket,args.object)
 print(json.dumps(result))
