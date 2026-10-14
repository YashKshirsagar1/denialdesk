from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from denialdesk.api.middleware.access_log import AccessLogMiddleware
from denialdesk.api.routers import auth, cases, clinic, document_requests, kpis, onboarding, ops, outcomes, queue, reviews, statements, upload
from denialdesk.config import settings
from denialdesk.logging import configure_phi_safe_logging

configure_phi_safe_logging()

app = FastAPI(title="DenialDesk", version="0.1.0")

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

# Serve frontend build at / (enable after frontend is built)
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
