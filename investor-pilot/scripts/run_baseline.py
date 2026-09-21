from pathlib import Path
import json, os, shutil, subprocess, sys, secrets, datetime
ROOT = Path("E:/PETROEDGE_AI/codex")
REPORT = ROOT / "docs/assessment"
SOURCE = ROOT / "application/backend"
SANDBOX = ROOT / "runtime/backend-baseline"
if SANDBOX.exists():
    raise SystemExit("Baseline sandbox exists; refusing to overwrite")
shutil.copytree(SOURCE, SANDBOX, ignore=shutil.ignore_patterns(".env", "*.db", "*.db-*", "*.sqlite*", "__pycache__", ".pytest_cache", "*.egg-info"))
env = os.environ.copy()
env.update({
    "PYTHONPATH": str(SANDBOX), "PYTHONDONTWRITEBYTECODE": "1",
    "JWT_SECRET": secrets.token_hex(32), "PETROEDGE_ADMIN_PASSWORD": secrets.token_urlsafe(24),
    "DATABASE_URL": "sqlite:///" + str(SANDBOX / "baseline.db").replace("\\", "/"),
    "PETROEDGE_DATA_DIR": str(SANDBOX / "data"),
    "ENVIRONMENT": "test", "TEMP": str(ROOT / "runtime/tmp"), "TMP": str(ROOT / "runtime/tmp"),
    "MPLCONFIGDIR": str(ROOT / "runtime/matplotlib"),
})
summary = {"sandbox":str(SANDBOX), "created_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "dependency_source":"Original pyproject.toml ranges resolved today; not historical pinned environment",
    "checks":{}}
commands = {
 "dependency_check":[sys.executable, "-m", "pip", "check"],
 "backend_tests":[sys.executable, "-B", "-m", "pytest", "tests", "-q", "--tb=short", "-p", "no:cacheprovider",
                  "--basetemp", str(ROOT / "runtime/pytest-basetemp"), "--junitxml", str(REPORT / "BACKEND_BASELINE_JUNIT.xml")],
 "startup_smoke":[sys.executable, "-B", "-c",
    "import json; from fastapi.testclient import TestClient; from app.main import app; "
    "exec('with TestClient(app) as client:\\n response=client.get(\"/health\")\\n print(json.dumps({\"status_code\":response.status_code,\"health\":response.json(),\"routes\":len(app.routes)}))\\n response.raise_for_status()')"],
}
for name, command in commands.items():
    print("Starting " + name, flush=True)
    log = REPORT / (name.upper() + ".log")
    with log.open("w", encoding="utf-8") as stream:
        try:
            result = subprocess.run(command, cwd=SANDBOX, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=240)
            summary["checks"][name] = {"exit_code":result.returncode, "log":str(log)}
        except subprocess.TimeoutExpired:
            summary["checks"][name] = {"exit_code":None, "status":"timeout_after_240s", "log":str(log)}
    (REPORT / "RUNTIME_BASELINE.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({name:summary["checks"][name]}), flush=True)
freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True)
(REPORT / "PYTHON_ENVIRONMENT_FREEZE.txt").write_text(freeze.stdout, encoding="utf-8")
print(json.dumps(summary), flush=True)

