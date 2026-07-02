from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

DEMO_USERS = {
    "admin@petroedge.ai": {
        "sub": "admin@petroedge.ai",
        "name": "PetroEdge Administrator",
        "hashed_password": pwd_context.hash("petroedge123"),
        "roles": ["admin", "geoscientist", "engineer"],
        "mfa_enabled": True,
    },
    "viewer@petroedge.ai": {
        "sub": "viewer@petroedge.ai",
        "name": "Operations Viewer",
        "hashed_password": pwd_context.hash("petroedge123"),
        "roles": ["viewer"],
        "mfa_enabled": True,
    },
}


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def authenticate_user(username: str, password: str) -> dict[str, Any] | None:
    user = DEMO_USERS.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user


def verify_mfa(code: str | None) -> bool:
    return code in {"123456", "000000"}


def create_access_token(subject: str, roles: list[str]) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "roles": roles, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        subject = payload.get("sub")
        roles = payload.get("roles", [])
        if subject is None:
            raise credentials_exception
        return {"sub": subject, "roles": roles}
    except JWTError as exc:
        raise credentials_exception from exc

