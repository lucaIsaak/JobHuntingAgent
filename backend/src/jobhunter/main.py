"""API entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jobhunter.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Job Hunting Agent API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
