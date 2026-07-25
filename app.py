"""FastAPI app factory: роутеры, статика, health-check."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from web.routers import connect


def create_app() -> FastAPI:
    app = FastAPI(title="Sales Agent")

    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.include_router(connect.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/")
    def root() -> RedirectResponse:
        return RedirectResponse(url="/connect")

    return app


app = create_app()
