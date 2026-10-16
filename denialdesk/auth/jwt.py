from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt

from denialdesk.auth.models import Role, UserClaims
from denialdesk.config import settings


def verify_token(token: str) -> UserClaims:
    """Verify a JWT and return UserClaims.

    Dev mode (dev_mode=True): HS256, signed with dev_jwt_secret.
    Prod mode: RS256, validated against Auth0 JWKS (stub — raises NotImplementedError).
    """
    try:
        if settings.dev_mode:
            payload = jwt.decode(
                token,
                settings.dev_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        else:
            # Prod: Auth0 RS256 verification. Fetch JWKS from auth0_domain and verify RS256.
            raise NotImplementedError("Prod Auth0 JWT verification not yet wired")

        claims = UserClaims(
            user_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            tenant_id=payload.get("tenant_id"),
            role=Role(payload.get("role", "clinic_staff")),
            name=payload.get("name", ""),
        )
        # A clinic token with no tenant would be treated as cross-tenant by the
        # tenant-scoping code. Never accept one.
        if claims.role in (Role.clinic_admin, Role.clinic_staff) and claims.tenant_id is None:
            raise HTTPException(status_code=401, detail="Malformed token claims: clinic role requires tenant_id")
        return claims
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=401, detail=f"Malformed token claims: {e}")


def create_dev_token(
    user_id: str,
    email: str,
    tenant_id: int | None,
    role: Role,
    name: str = "",
) -> str:
    """Create a signed HS256 access token (dev-mode signer; swapped for the IdP in prod)."""
    payload = {
        "sub": user_id,
        "email": email,
        "tenant_id": tenant_id,
        "role": role.value,
        "name": name,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.access_token_ttl_hours),
    }
    return jwt.encode(payload, settings.dev_jwt_secret, algorithm="HS256")
