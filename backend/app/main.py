from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import alerts, analytics, auth, ingestion, monitoring, reports, streaming, wells
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="PetroEdge AI API",
        version="0.1.0",
        description="Real-time well logging analytics API for PetroEdge AI.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(ingestion.router, prefix="/api/v1/ingestion", tags=["ingestion"])
    app.include_router(streaming.router, prefix="/api/v1/streaming", tags=["streaming"])
    app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
    app.include_router(wells.router, prefix="/api/v1/wells", tags=["wells"])
    app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
    app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
    app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()

