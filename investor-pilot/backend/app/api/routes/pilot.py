from app.core.rbac import require_roles
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.core.security import get_current_user, hash_password
from app.core.pilot_access import access_state, require_pilot_owner
from app.db.session import get_db
from app.db.models import User
from app.core.config import settings
from app.api.routes.auth import EMAIL_PATTERN

router = APIRouter()


def owner(user=Depends(get_current_user)):
    require_pilot_owner(user)
    return user


class PauseRequest(BaseModel):
    paused: bool


class CustomerRequest(BaseModel):
    email: str = Field(max_length=320)
    full_name: str = Field(min_length=2,max_length=200)
    password: str = Field(min_length=12,max_length=256)
    role: Literal["viewer", "engineer", "geoscientist"] = "viewer"


class ActiveRequest(BaseModel):
    is_active: bool


def public_user(user):
    return {"id":user.id,"email":user.email,"full_name":user.full_name,"role":user.role,"is_active":user.is_active}


@router.get("/access")
def status(user=Depends(owner)):
    return access_state()


@router.put("/access")
def pause(payload:PauseRequest,user=Depends(owner)):
    return access_state(payload.paused,user["user_id"])


@router.get("/customers")
def customers(user=Depends(owner),db:Session=Depends(get_db)):
    return [public_user(u) for u in db.scalars(select(User).order_by(User.email)).all()]


@router.post("/customers",status_code=201)
def create_customer(payload:CustomerRequest,user=Depends(owner),db:Session=Depends(get_db)):
    email=payload.email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(422,"Enter a valid email address.")
    account=User(email=email,full_name=payload.full_name.strip(),hashed_password=hash_password(payload.password),role=payload.role,is_active=True)
    db.add(account)
    try: db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409,"An account with this email already exists.") from exc
    db.refresh(account)
    return public_user(account)


@router.put("/customers/{customer_id}/active")
def set_active(customer_id:str,payload:ActiveRequest,user=Depends(owner),db:Session=Depends(get_db)):
    account=db.get(User,customer_id)
    if account is None: raise HTTPException(404,"Account not found.")
    if account.email.lower()==settings.pilot_owner_email.strip().lower():
        raise HTTPException(409,"The owner cannot disable their own recovery access.")
    account.is_active=payload.is_active
    db.commit()
    return public_user(account)


@router.get("/benchmarks/{kind}")
def benchmark(kind:str,user=Depends(require_roles("viewer"))):
    import json
    from pathlib import Path
    from app.core.config import BACKEND_ROOT
    names={"edge":"EDGE_REPORT.json","twin":"TWIN_REPORT.json","qualification":"REGRESSION_QUALIFICATION.json"}
    if kind not in names:raise HTTPException(404,"Unknown benchmark")
    path=BACKEND_ROOT/"pilot_assets"/names[kind]
    if not path.exists():raise HTTPException(503,"Benchmark assets are not installed.")
    value=json.loads(path.read_text(encoding="utf-8"))
    value.pop("manifest",None)
    return value
