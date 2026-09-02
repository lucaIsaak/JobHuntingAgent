"""API entrypoint."""

from fastapi import FastAPI

from jobhunter.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Job Hunting Agent API", version="0.1.0")
    app.include_router(router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
