"""FastAPI app: CORS and router registration. No business logic lives here."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import meta


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Wind forecast accuracy API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET"],
    )
    app.include_router(meta.router)
    return app


app = create_app()
