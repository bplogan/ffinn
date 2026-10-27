"""
Custom exceptions and FastAPI exception handlers.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from jwt import PyJWTError as JWTError


class BusinessException(Exception):
    """Raised for business rule violations (400-level errors)."""
    def __init__(self, message: str, code: str = "BUSINESS_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundException(BusinessException):
    """Resource not found."""
    def __init__(self, resource: str, identifier: str | None = None):
        # When called with two args, format as "Resource not found: <id>".
        # When called with one arg (a full message), use it verbatim.
        if identifier is not None:
            msg = f"{resource} not found: {identifier}"
        else:
            msg = resource  # caller already includes "not found" in the message
        super().__init__(msg, "NOT_FOUND")


class UnauthorizedException(BusinessException):
    """Authentication required or failed."""
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, "UNAUTHORIZED")


class ForbiddenException(BusinessException):
    """Access denied."""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, "FORBIDDEN")


class ConflictException(BusinessException):
    """Resource conflict (duplicate, etc.)."""
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")


class ValidationException(BusinessException):
    """Input validation failed."""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class PaymentException(BusinessException):
    """Payment processing error."""
    def __init__(self, message: str):
        super().__init__(message, "PAYMENT_ERROR")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(BusinessException)
    async def business_exception_handler(request: Request, exc: BusinessException):
        status_code = {
            "NOT_FOUND": status.HTTP_404_NOT_FOUND,
            "UNAUTHORIZED": status.HTTP_401_UNAUTHORIZED,
            "FORBIDDEN": status.HTTP_403_FORBIDDEN,
            "CONFLICT": status.HTTP_409_CONFLICT,
            "VALIDATION_ERROR": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PAYMENT_ERROR": status.HTTP_402_PAYMENT_REQUIRED,
        }.get(exc.code, status.HTTP_400_BAD_REQUEST)

        headers = {}
        if exc.code == "UNAUTHORIZED":
            headers["WWW-Authenticate"] = "Bearer"

        return ORJSONResponse(
            status_code=status_code,
            content={"error": exc.code, "message": exc.message},
            headers=headers or None,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        from app.core.config import settings
        # In production hide field-level details to prevent info leakage
        if settings.is_production:
            details = None
        else:
            details = exc.errors()
        content = {
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
        }
        if details is not None:
            content["details"] = details
        return ORJSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=content,
        )

    @app.exception_handler(JWTError)
    async def jwt_error_handler(request: Request, exc: JWTError):
        return ORJSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": "INVALID_TOKEN", "message": "Invalid or expired token"},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        import structlog
        log = structlog.get_logger(__name__)
        log.exception("Unhandled exception", path=request.url.path, exc_info=exc)
        return ORJSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred"},
        )
