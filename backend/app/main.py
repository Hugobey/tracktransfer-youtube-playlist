"""FastAPI entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.errors import AppError
from app.services.container import get_services


def create_app() -> FastAPI:
    app = FastAPI(title="TrackTransfer", docs_url="/api/docs", redoc_url=None)
    settings = get_services().settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)

    @app.exception_handler(AppError)
    def handle_app_error(_request: object, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})

    @app.exception_handler(RequestValidationError)
    def handle_validation(_request: object, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        message = "The request is missing required fields."
        if errors:
            loc = ".".join(str(part) for part in errors[0].get("loc", []) if part != "body")
            detail = errors[0].get("msg", message)
            message = f"{loc}: {detail}" if loc else str(detail)
        return JSONResponse(status_code=422, content={"error": {"code": "invalid_request", "message": message}})

    return app


app = create_app()
