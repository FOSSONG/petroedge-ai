"""Password + verified fresh Duo Push. Missing configuration and bypasses fail closed."""
import hashlib,secrets,sqlite3,time,re
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import HTTPException
from app.core.config import settings
COOKIE="petroedge_phone_transaction"
COOKIE_PATH="/api/v1/auth/duo"

def required(email,role):
 return settings.phone_approval_required and (email.lower()==(settings.pilot_owner_email or "").lower() or role in {"admin","administrator"})

def client():
 from duo_universal.client import Client
 origin=urlsplit(settings.public_origin)
 if origin.scheme!="https" or not origin.netloc or origin.path not in ["","/"] or origin.query or origin.fragment or not settings.duo_client_id or not settings.duo_client_secret or not re.fullmatch(r"api-[a-zA-Z0-9]+\.duosecurity\.com",settings.duo_api_host):
  raise HTTPException(503,"Phone approval is required but Duo and the public HTTPS origin are not configured.")
 return Client(settings.duo_client_id,settings.duo_client_secret,settings.duo_api_host,settings.public_origin.rstrip("/")+COOKIE_PATH+"/callback")

def connection():
 p=Path.cwd()/"data/phone_approval.sqlite3";p.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(p,timeout=10);c.row_factory=sqlite3.Row
 c.execute("CREATE TABLE IF NOT EXISTS transactions (state TEXT PRIMARY KEY, binding TEXT NOT NULL, username TEXT NOT NULL, uid TEXT NOT NULL, nonce TEXT NOT NULL, expires REAL NOT NULL, stage TEXT NOT NULL)")
 c.execute("DELETE FROM transactions WHERE expires < ?",(time.time(),));c.commit()
 return c

def hashed(value):return hashlib.sha256(value.encode()).hexdigest()

def begin(user,response):
 api=client()
 try:api.health_check()
 except Exception as exc:raise HTTPException(503,"Phone approval service unavailable; access remains blocked.") from exc
 state=api.generate_state();binding=secrets.token_urlsafe(32);nonce=secrets.token_urlsafe(32)
 with connection() as c:
  # Bound pending transactions and avoid repeatedly sending prompts for the same account.
  count=c.execute("SELECT count(*) FROM transactions WHERE uid=?",(str(user.id),)).fetchone()[0]
  if count>=5:raise HTTPException(429,"Too many pending phone approvals. Wait five minutes before retrying.")
  c.execute("INSERT INTO transactions VALUES (?,?,?,?,?,?,?)",(state,hashed(binding),user.email,str(user.id),nonce,time.time()+300,"pending"))
 response.set_cookie(COOKIE,binding,httponly=True,secure=True,samesite="lax",max_age=300,path=COOKIE_PATH)
 response.headers["Cache-Control"]="no-store"
 return {"mfa_required":True,"authorization_url":api.create_auth_url(user.email,state,nonce)}

def verify_push(result):
 context=result.get("auth_context") or {}
 if result.get("auth_result",{}).get("result")!="allow" or context.get("factor")!="duo_push" or context.get("result")!="success" or context.get("reason")!="user_approved":
  raise HTTPException(403,"A fresh phone Push approval is required. Remembered sessions, bypasses and other factors are not accepted.")
 if abs(time.time()-float(result.get("auth_time",0)))>300:
  raise HTTPException(403,"Phone approval expired; sign in again.")

def approve(state,code,binding):
 if not binding:raise HTTPException(401,"Login browser binding is missing.")
 with connection() as c:
  c.execute("BEGIN IMMEDIATE")
  row=c.execute("SELECT * FROM transactions WHERE state=? AND binding=? AND stage='pending' AND expires>?",(state,hashed(binding),time.time())).fetchone()
  if not row:raise HTTPException(401,"Invalid or expired approval transaction.")
  c.execute("UPDATE transactions SET stage='consumed' WHERE state=?",(state,))
 try:result=client().exchange_authorization_code_for_2fa_result(code,row["username"],row["nonce"])
 except HTTPException:raise
 except Exception as exc:raise HTTPException(401,"Phone approval verification failed.") from exc
 verify_push(result)
 with connection() as c:c.execute("UPDATE transactions SET stage='approved',expires=? WHERE state=?",(time.time()+60,state))

def finish(binding,origin):
 if not binding or origin!=settings.public_origin.rstrip("/"):raise HTTPException(403,"Same-origin approved browser required.")
 with connection() as c:
  c.execute("BEGIN IMMEDIATE")
  row=c.execute("SELECT * FROM transactions WHERE binding=? AND stage='approved' AND expires>?",(hashed(binding),time.time())).fetchone()
  if not row:raise HTTPException(401,"No unconsumed phone approval. Sign in again.")
  c.execute("DELETE FROM transactions WHERE state=?",(row["state"],))
 return dict(row)
