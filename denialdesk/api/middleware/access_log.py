"""
FastAPI middleware that logs every request to a PHI-bearing route into access_logs.

PHI-bearing routes (logged):
  /api/cases, /api/queue, /api/upload, /api/batches,
  /api/document-requests, /api/ops/deadlines, /api/clinic

Non-PHI routes (not logged):
  /api/auth, /api/kpis, /api/health, /docs, /openapi.json

actor_email is always SHA-256 hashed before storage.
resource is derived from path as an ID reference — never contains raw PHI.
The middleware never raises — failures are logged as warnings only.
"""
import base64
import json
import logging
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

_PHI_PREFIXES = (
    "/api/cases",
    "/api/queue",
    "/api/upload",
    "/api/batches",
    "/api/document-requests",
    "/api/ops/deadlines",
    "/api/clinic",
)

_METHOD_TO_ACTION = {
    "GET": "read",
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}


def _is_phi_route(path: str) -> bool:
    return any(path.startswith(p) for p in _PHI_PREFIXES)


def _resource_from_path(path: str) -> str:
    """Derive a safe resource identifier from the request path.

    Returns strings like "case:42", "batch:7", "queue", "clinic/dashboard".
    Never includes patient names, DOBs, or other PHI — only path segments and IDs.
    """
    parts = [p for p in path.strip("/").split("/") if p]
    # e.g. ["api", "cases", "42"] -> "case:42"
    # e.g. ["api", "queue", "cases"] -> "queue"
    if len(parts) >= 3 and parts[0] == "api":
        segment = parts[1]
        remainder = parts[2:]
        # Singularise well-known collections for readability
        name_map = {
            "cases": "case",
            "batches": "batch",
            "document-requests": "document_request",
        }
        resource_name = name_map.get(segment, segment)
        # If next part is numeric, it's an ID
        if remainder and remainder[0].isdigit():
            return f"{resource_name}:{remainder[0]}"
        if remainder:
            return f"{resource_name}/{'/'.join(remainder)}"
        return resource_name
    return path


def _decode_jwt_claims_unsafe(token: str) -> dict:
    """Decode JWT payload WITHOUT verifying signature — for logging only.

    The auth layer has already verified the token before this middleware
    reads the claims. We just need actor info for the access log.
    """
    try:
        payload_b64 = token.split(".")[1]
        # Add padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception:
        return {}


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Only log PHI-bearing routes
        if not _is_phi_route(request.url.path):
            return response

        # Fire-and-forget access log — never block the response
        try:
            await self._write_log(request, response.status_code)
        except Exception as exc:
            logger.warning("access_log write failed: %s", type(exc).__name__)

        return response

    async def _write_log(self, request: Request, status_code: int) -> None:
        from denialdesk.api.deps import get_session_factory
        from denialdesk.logging import hash_email
        from denialdesk.models.case import AccessLog

        # Extract JWT claims (no verification — auth layer already did it)
        actor_id = "anonymous"
        actor_role = "unknown"
        actor_email_hash: str | None = None
        tenant_id: int | None = None

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            claims = _decode_jwt_claims_unsafe(auth_header[7:])
            actor_id = claims.get("sub", "anonymous")
            actor_role = claims.get("role", "unknown")
            raw_email = claims.get("email", "")
            if raw_email:
                actor_email_hash = hash_email(raw_email)
            raw_tenant = claims.get("tenant_id")
            if raw_tenant is not None:
                try:
                    tenant_id = int(raw_tenant)
                except (ValueError, TypeError):
                    pass

        action = _METHOD_TO_ACTION.get(request.method.upper(), "read")
        resource = _resource_from_path(request.url.path)

        log_entry = AccessLog(
            tenant_id=tenant_id,
            actor_id=actor_id,
            actor_email=actor_email_hash,
            actor_role=actor_role,
            resource=resource,
            action=action,
            http_method=request.method.upper(),
            path=request.url.path,
            timestamp=datetime.now(timezone.utc),
        )

        factory = get_session_factory()
        async with factory() as session:
            session.add(log_entry)
            await session.commit()
