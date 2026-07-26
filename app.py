"""FastAPI app factory: роутеры, статика, health-check, планировщик."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from services.scheduler import shutdown_scheduler, start_scheduler
from web.routers import connect, deal, my_day, worklist


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Срабатывает только при реальном запуске (uvicorn); TestClient без `with`
    # lifespan не поднимает, поэтому в тестах фоновых джобов нет.
    start_scheduler()
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="Sales Agent", lifespan=lifespan)

    app.mount("/static", StaticFiles(directory="web/static"), name="static")
    app.include_router(worklist.router)
    app.include_router(my_day.router)
    app.include_router(connect.router)
    app.include_router(deal.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
