"""Run backend tests in an isolated E: copy; preserve live user storage."""
import os, shutil, subprocess, secrets, sys
from pathlib import Path
base=Path(__file__).resolve().parents[2]
src=base/"application/backend"
dst=base/"runtime"/("pilot-tests-"+secrets.token_hex(4))
shutil.copytree(src,dst,ignore=shutil.ignore_patterns(".env","*.db","*.db-*","*.sqlite*","__pycache__",".pytest_cache","*.egg-info","model_store","dataset_store","prediction_store","analysis_store"))
env=os.environ.copy();env.update(PYTHONPATH=str(dst),PYTHONDONTWRITEBYTECODE="1",JWT_SECRET=secrets.token_hex(32),PETROEDGE_ADMIN_PASSWORD=secrets.token_urlsafe(24),DATABASE_URL="sqlite:///"+str(dst/"test.db").replace("\\","/"),PETROEDGE_DATA_DIR=str(dst/"data"),ENVIRONMENT="test",TEMP=str(base/"runtime/tmp"),TMP=str(base/"runtime/tmp"))
env.pop("PILOT_OWNER_EMAIL",None)
log=base/"docs/assessment/PILOT_QC_TESTS_014.log"
with log.open("w",encoding="utf-8") as out:
    result=subprocess.run([sys.executable,"-B","-m","pytest","tests","-q","--tb=short","-p","no:cacheprovider","--basetemp",str(dst/"pytest-tmp")],cwd=dst,env=env,stdout=out,stderr=subprocess.STDOUT,timeout=240)
print(log.read_text(encoding="utf-8")[-8000:]);print("EXIT",result.returncode);sys.exit(result.returncode)
