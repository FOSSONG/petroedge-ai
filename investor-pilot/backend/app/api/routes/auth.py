from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import UserRepo
from app.core.config import settings
from app.core.security import create_access_token, get_current_user, hash_password
from app.db.models import User, UserRole
from app.schemas import LoginRequest, TokenResponse
from app.services.domain_services import AuthenticationService

router = APIRouter()

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthenticationStatus(BaseModel):
    setup_required: bool
    user_count: int
    manual_login: bool = True


class BootstrapAdministratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=5, max_length=320)
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalised = value.strip().lower()
        if not EMAIL_PATTERN.fullmatch(normalised):
            raise ValueError("Enter a valid email address.")
        return normalised

    @field_validator("confirm_password")
    @classmethod
    def passwords_match(
        cls,
        value: str,
        info: Any,
    ) -> str:
        password = info.data.get("password")
        if password is not None and value != password:
            raise ValueError("Passwords do not match.")
        return value


def _token_response(user: User, phone_approved: bool = False) -> TokenResponse:
    token = create_access_token(
        user.email,
        [str(user.role)],
        user_id=str(user.id),
        full_name=user.full_name,
        additional_claims={"phone_approved":phone_approved},
    )

    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        roles=[str(user.role)],
        user={
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "roles": [str(user.role)],
            "is_active": user.is_active,
        },
    )


@router.get("/status", response_model=AuthenticationStatus)
def authentication_status(users: UserRepo) -> AuthenticationStatus:
    count = users.count()

    return AuthenticationStatus(
        setup_required=count == 0,
        user_count=count,
    )


@router.post(
    "/bootstrap-admin",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
def bootstrap_administrator(
    payload: BootstrapAdministratorRequest,
    users: UserRepo,
) -> TokenResponse:
    if settings.pilot_owner_email:
        raise HTTPException(403, "Public setup is disabled for this pilot. Initialise the owner account locally before deployment.")
    if users.count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Initial setup is already complete. "
                "Ask an administrator to create or reset an account."
            ),
        )

    administrator = User(
        email=payload.email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    try:
        users.add(administrator)
    except IntegrityError as exc:
        users.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    return _token_response(administrator)


@router.post("/login", response_model=None)
def login(payload: LoginRequest, users: UserRepo, response: Response):
    user = AuthenticationService(users).authenticate(
        payload.username,
        payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.services.phone_approval import required, begin
    if required(user.email,str(user.role)):
        return begin(user,response)

    user.last_login_at = datetime.now(timezone.utc)
    users.commit()

    return _token_response(user)


@router.get("/me")
def me(
    user: dict[str, Any] = __import__(
        "fastapi",
        fromlist=["Depends"],
    ).Depends(get_current_user),
) -> dict[str, Any]:
    return user

@router.get("/duo/callback")
def duo_callback(request:Request,state:str,duo_code:str):
    from app.services.phone_approval import approve,COOKIE
    approve(state,duo_code,request.cookies.get(COOKIE))
    return RedirectResponse(settings.public_origin.rstrip("/")+"/?phone_approved=1",status_code=303,headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})

@router.post("/duo/complete",response_model=TokenResponse)
def duo_complete(request:Request,response:Response,users:UserRepo):
    from app.services.phone_approval import finish,COOKIE,COOKIE_PATH
    transaction=finish(request.cookies.get(COOKIE),request.headers.get("origin"))
    user=users.get_by_email(transaction["username"])
    if user is None or not user.is_active or str(user.id)!=transaction["uid"]:raise HTTPException(401,"Account unavailable.")
    user.last_login_at=datetime.now(timezone.utc);users.commit()
    response.delete_cookie(COOKIE,path=COOKIE_PATH,secure=True,httponly=True,samesite="lax")
    response.headers["Cache-Control"]="no-store"
    return _token_response(user,phone_approved=True)
