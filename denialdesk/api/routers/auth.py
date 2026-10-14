from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from denialdesk.auth.jwt import create_dev_token
from denialdesk.auth.models import Role
from denialdesk.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class DevTokenRequest(BaseModel):
    user_id: str = "dev-user"
    email: str = "dev@denialdesk.local"
    tenant_id: int | None = 1
    role: str = "clinic_admin"


class DevTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    tenant_id: int | None


@router.post("/dev-token", response_model=DevTokenResponse)
async def get_dev_token(body: DevTokenRequest) -> DevTokenResponse:
    """Issue a signed dev JWT. Only available when dev_mode=True."""
    if not settings.dev_mode:
        raise HTTPException(status_code=404, detail="Not found")
    try:
        role = Role(body.role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Choose from: {[r.value for r in Role]}",
        )
    token = create_dev_token(body.user_id, body.email, body.tenant_id, role)
    return DevTokenResponse(access_token=token, role=body.role, tenant_id=body.tenant_id)
