from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.core.security import create_access_token, verify_credentials
from app.schemas.auth import TokenRequest, TokenResponse

router = APIRouter()


@router.post("/token", response_model=TokenResponse)
async def login(payload: TokenRequest) -> TokenResponse:
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    token = create_access_token(payload.username)
    return TokenResponse(access_token=token, expires_in=settings.jwt_expiry_minutes * 60)