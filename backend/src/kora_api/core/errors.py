from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def _validation_error_without_input(_: Request, exc: Exception) -> JSONResponse:
    """422 response that never echoes submitted values (they may be passwords or tokens)."""
    assert isinstance(exc, RequestValidationError)
    errors: list[dict[str, Any]] = [
        {key: value for key, value in error.items() if key != "input"} for error in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": jsonable_encoder(errors)},
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(RequestValidationError, _validation_error_without_input)
