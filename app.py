"""FastAPI app factory: роутеры, статика, health-check."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def create_app() -> FastAPI:
    app = FastAPI(title="Sales Agent")

    app.mount("/static", StaticFiles(directory="web/static"), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
