"""FastAPI app: CORS and router registration. No business logic lives here."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import day, export, meta, metrics


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Wind forecast accuracy API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
        expose_headers=["Content-Disposition"],
    )
    for module in (meta, day, metrics, export):
        app.include_router(module.router)
    return app


app = create_app()
