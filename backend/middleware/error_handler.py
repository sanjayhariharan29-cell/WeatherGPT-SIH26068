from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.encoders import jsonable_encoder
from backend.config.logging import logger
from backend.config.settings import settings


def classify_error_category(status_code: int, exc: Exception = None) -> str:
    """Categorize operational errors into standard observability error classes."""
    exc_name = type(exc).__name__ if exc else ""
    exc_str = str(exc).lower() if exc else ""

    if "timeout" in exc_str or "timeout" in exc_name.lower():
        return "TIMEOUT_ERROR"
    if "operationalerror" in exc_name.lower() or "database" in exc_str or "sqlite" in exc_str or "postgres" in exc_str:
        return "DATABASE_ERROR"
    if status_code in (401, 403):
        return "AUTH_ERROR"
    if status_code in (400, 404, 422):
        return "CLIENT_ERROR"
    if status_code in (502, 503):
        return "PROVIDER_ERROR"

    return "INTERNAL_SERVER_ERROR"


def register_exception_handlers(app: FastAPI):
    """Registers global exception handlers to sanitize production error responses and log metadata."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        req_id = getattr(request.state, "request_id", "untracked")
        category = classify_error_category(exc.status_code, exc)
        logger.warning(
            f"[{category}] HTTP {exc.status_code} on {request.url.path}: {exc.detail} [request_id={req_id}]"
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers={"X-Request-ID": req_id},
            content={
                "detail": exc.detail,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "category": category,
                    "status_code": exc.status_code,
                    "message": exc.detail,
                    "request_id": req_id
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        req_id = getattr(request.state, "request_id", "untracked")
        category = "CLIENT_ERROR"
        logger.warning(f"[{category}] Validation Error on {request.url.path}: {exc.errors()} [request_id={req_id}]")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            headers={"X-Request-ID": req_id},
            content={
                "error": {
                    "code": category,
                    "status_code": 422,
                    "message": "Input validation failed",
                    "request_id": req_id,
                    "details": jsonable_encoder(exc.errors()) if settings.DEBUG else "Invalid payload parameters"
                }
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        req_id = getattr(request.state, "request_id", "untracked")
        category = classify_error_category(500, exc)
        logger.error(
            f"[{category}] Unhandled Exception on {request.url.path}: {type(exc).__name__}: {str(exc)} [request_id={req_id}]",
            exc_info=True
        )
        message = str(exc) if settings.DEBUG else "An internal server error occurred. Please try again later."
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            headers={"X-Request-ID": req_id},
            content={
                "error": {
                    "code": category,
                    "status_code": 500,
                    "message": message,
                    "request_id": req_id
                }
            }
        )
