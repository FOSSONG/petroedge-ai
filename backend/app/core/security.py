from __future__ import annotations

import hmac
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from argon2 import PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

from app.core.config import settings

password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _validate_password_input(password: str) -> str:
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")

    password_length = len(password.encode("utf-8"))

    if password_length < 12:
        raise ValueError("Password must contain at least 12 UTF-8 bytes.")

    if password_length > 1024:
        raise ValueError("Password is too long.")

    return password


def hash_password(password: str) -> str:
    validated = _validate_password_input(password)

    try:
        return password_hasher.hash(validated)
    except HashingError as exc:
        raise ValueError("Password hashing failed.") from exc


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    if not plain_password or not hashed_password:
        return False

    if not hashed_password.startswith("$argon2"):
        return False

    try:
        return password_hasher.verify(
            hashed_password,
            plain_password,
        )
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        TypeError,
        ValueError,
    ):
        return False


def password_hash_needs_rehash(hashed_password: str) -> bool:
    if not hashed_password or not hashed_password.startswith("$argon2"):
        return True

    try:
        return password_hasher.check_needs_rehash(hashed_password)
    except (InvalidHashError, TypeError, ValueError):
        return True


def create_access_token(
    subject: str,
    roles: list[str],
    *,
    user_id: str | None = None,
    full_name: str | None = None,
    expires_delta: timedelta | None = None,
    additional_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "roles": sorted(set(roles)),
        "iat": now,
        "nbf": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
        "iss": settings.app_name,
        "token_type": "access",
    }
    if user_id:
        payload["uid"] = user_id
    if full_name:
        payload["name"] = full_name
    if additional_claims:
        reserved = {"sub", "roles", "iat", "nbf", "exp", "jti"}
        payload.update({k: v for k, v in additional_claims.items() if k not in reserved})

    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.app_name,
            options={"require_sub": True, "require_exp": True},
        )
    except ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except JWTError as exc:
        raise credentials_error from exc

    if payload.get("token_type") != "access" or not payload.get("sub"):
        raise credentials_error
    roles = payload.get("roles", [])
    if not isinstance(roles, list):
        raise credentials_error
    return payload


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    payload = decode_access_token(token)
    return {
        "username": payload["sub"],
        "roles": payload.get("roles", []),
        "user_id": payload.get("uid"),
        "full_name": payload.get("name"),
        "token_id": payload.get("jti"),
    }


def verify_mfa(code: str | None, expected_code: str | None = None) -> bool:
    if not code or not expected_code:
        return False
    return hmac.compare_digest(str(code), str(expected_code))
