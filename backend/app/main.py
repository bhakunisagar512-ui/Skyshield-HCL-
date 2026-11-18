from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.core.taxonomy import taxonomy_payload
from app.routers import admin, auth, dashboard, incidents, measures, policies

settings = get_settings()

app = FastAPI(
    title="SkyShield API",
    description="Aviation safety and incident reporting: report, review, AI-suggested measures, admin oversight.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (auth.router, incidents.router, measures.router, admin.router, dashboard.router, policies.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "embedding_provider": settings.embedding_provider}


@app.get("/api/meta/taxonomy", tags=["meta"])
def taxonomy():
    return taxonomy_payload()
