from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from denialdesk.api.middleware.access_log import AccessLogMiddleware
from denialdesk.api.routers import auth, cases, clinic, document_requests, kpis, onboarding, ops, outcomes, queue, reviews, statements, upload, users
from denialdesk.config import settings
from denialdesk.logging import configure_phi_safe_logging

configure_phi_safe_logging()



@asynccontextmanager
async def lifespan(_app: FastAPI):
    # SQLite is the zero-setup standalone/dev database: create tables on first run.
    # Postgres deployments are managed with `alembic upgrade head` instead.
    if settings.database_url.startswith("sqlite"):
        from denialdesk.api.deps import get_session_factory
        from denialdesk.models.case import Base

        engine = get_session_factory().kw["bind"]
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="DenialDesk", version="0.2.0", lifespan=lifespan)

_cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
    allow_credentials=True,
)
app.add_middleware(AccessLogMiddleware)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(outcomes.router, prefix="/api")
app.include_router(kpis.router, prefix="/api")
app.include_router(clinic.router, prefix="/api")
app.include_router(document_requests.router, prefix="/api")
app.include_router(ops.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(statements.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve the built frontend (npm run build) from the same origin, so the whole
# product runs as one process. Unknown non-API paths fall back to index.html so
# client-side routes survive a refresh.
_dist = Path(settings.frontend_dist).resolve()


@app.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    if path.startswith("api/") or not (_dist / "index.html").exists():
        raise HTTPException(status_code=404, detail="Not found")
    candidate = (_dist / path).resolve()
    if path and candidate.is_file() and _dist in candidate.parents:
        return FileResponse(candidate)
    return FileResponse(_dist / "index.html")
