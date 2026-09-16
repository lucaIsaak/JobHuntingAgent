"""API entrypoint."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobhunter.agent import health_monitor
from jobhunter.api import routes
from jobhunter.api.candidate_routes import router as candidate_router
from jobhunter.api.routes import router
from jobhunter.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(
        health_monitor.run_loop(
            scrapers=routes.scrapers,
            repository=routes.repository,
            interval_seconds=settings.health_check_interval_seconds,
        )
    )
    yield
    task.cancel()


def create_app() -> FastAPI:
    app = FastAPI(title="Job Hunting Agent API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    app.include_router(candidate_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
