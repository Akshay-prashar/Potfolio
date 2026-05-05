"""FastAPI app entrypoint."""

from fastapi import FastAPI

from .api import router


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(title="IPL Live Prediction API", version="0.1.0")
    app.include_router(router, prefix="/api/v1", tags=["prediction"])
    return app


app = create_app()

