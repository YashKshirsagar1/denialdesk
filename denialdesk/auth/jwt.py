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

        return UserClaims(
            user_id=payload.get("sub", ""),
            email=payload.get("email", ""),
            tenant_id=payload.get("tenant_id"),
            role=Role(payload.get("role", "clinic_staff")),
        )
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=401, detail=f"Malformed token claims: {e}")


def create_dev_token(
    user_id: str,
    email: str,
    tenant_id: int | None,
    role: Role,
) -> str:
    """Create a signed HS256 dev token. Only called from the dev-token endpoint."""
    payload = {
        "sub": user_id,
        "email": email,
        "tenant_id": tenant_id,
        "role": role.value,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, settings.dev_jwt_secret, algorithm="HS256")
