from fastapi import APIRouter, HTTPException, status

from app.core.security import authenticate_user, create_access_token, verify_mfa
from app.schemas import LoginRequest, TokenResponse

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest) -> TokenResponse:
    user = authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user["mfa_enabled"] and not verify_mfa(payload.mfa_code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code")
    token = create_access_token(user["sub"], user["roles"])
    return TokenResponse(access_token=token, roles=user["roles"])

