from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from denialdesk.api.routers import auth, cases, clinic, document_requests, kpis, outcomes, queue, reviews, upload

app = FastAPI(title="DenialDesk", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(queue.router, prefix="/api")
app.include_router(cases.router, prefix="/api")
app.include_router(reviews.router, prefix="/api")
app.include_router(outcomes.router, prefix="/api")
app.include_router(kpis.router, prefix="/api")
app.include_router(clinic.router, prefix="/api")
app.include_router(document_requests.router, prefix="/api")

# Serve frontend build at / (enable after frontend is built)
# app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="static")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
