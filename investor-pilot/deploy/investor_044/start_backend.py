import os
from pathlib import Path
from sqlalchemy import select
from app.core.config import settings
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.db.models import User
from app.core.security import hash_password
from app.services.phone_approval import client
if not settings.pilot_owner_email:
 raise RuntimeError("A sole owner must be configured.")
for value in [settings.pilot_owner_email,settings.jwt_secret,settings.petroedge_admin_password]:
 if not value or "REPLACE_" in value:raise RuntimeError("Owner deployment configuration is incomplete.")
if settings.phone_approval_required: client().health_check()
init_db()
with SessionLocal() as db:
 owner=db.scalar(select(User).where(User.email==settings.pilot_owner_email.strip().lower()))
 if owner is None:
  if db.scalar(select(User).limit(1)) is not None:raise RuntimeError("Existing database lacks configured owner; refusing account replacement.")
  db.add(User(email=settings.pilot_owner_email.strip().lower(),full_name="PetroEdge Owner",hashed_password=hash_password(settings.petroedge_admin_password),role="admin",is_active=True));db.commit()
 elif str(owner.role) not in ["admin","administrator"] or not owner.is_active:raise RuntimeError("Configured owner is not active administrator.")
os.execvp("uvicorn",["uvicorn","app.main:app","--host","0.0.0.0","--port","8000","--workers","1","--no-access-log"])
