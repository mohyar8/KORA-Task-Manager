from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


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


# --- OpenAPI documentation of error responses --------------------------------------------------


class ErrorResponse(BaseModel):
    """Every error except 422: a human-readable message."""

    detail: str


class ValidationIssue(BaseModel):
    type: str
    loc: list[str | int]
    msg: str
    ctx: dict[str, Any] | None = Field(
        default=None, description="Present for some issue types only."
    )


class ValidationErrorResponse(BaseModel):
    """422: a list of issues when the request fails validation (submitted values are never
    echoed), or a message string when a business rule is violated."""

    detail: list[ValidationIssue] | str


ERROR_DESCRIPTIONS: dict[int, str] = {
    400: "Bad request.",
    401: "Not authenticated: no session, or it is unknown, revoked or expired.",
    403: (
        "Forbidden: CSRF token missing or invalid (unsafe methods), password change required, "
        "System Admin authority required (admin routes), or not permitted."
    ),
    404: "Not found.",
    409: "The resource's current state prevents the operation.",
    422: "Request validation failed (`detail` is a list) or a business rule was violated "
    "(`detail` is a string).",
    429: "Too many failed sign-in attempts; retry after the `Retry-After` seconds.",
}


def errors(*statuses: int | tuple[int, str]) -> dict[int | str, dict[str, Any]]:
    """`responses=` entries for error statuses; a `(status, description)` pair overrides the
    default description."""
    responses: dict[int | str, dict[str, Any]] = {}
    for item in statuses:
        code, description = item if isinstance(item, tuple) else (item, ERROR_DESCRIPTIONS[item])
        model = ValidationErrorResponse if code == 422 else ErrorResponse
        responses[code] = {"model": model, "description": description}
    return responses


# Guards: a session is required (401) and may be refused (403) for CSRF, the temporary-password
# gate, missing System Admin authority, or a permission/visibility check.
AUTHENTICATED = errors(401, 403)


def use_actual_validation_error_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Point every 422 response at `ValidationErrorResponse` (FastAPI's default schema documents
    an `input` field the API never returns, and no string form)."""
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    generated = ValidationErrorResponse.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    components.update(generated.pop("$defs", {}))
    components["ValidationErrorResponse"] = generated
    for operations in schema.get("paths", {}).values():
        for operation in operations.values():
            response = operation.get("responses", {}).get("422")
            if response is not None:
                response["content"] = {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
                    }
                }
                response["description"] = ERROR_DESCRIPTIONS[422]
    for name in ("HTTPValidationError", "ValidationError"):
        components.pop(name, None)
    return schema


def document_validation_errors(app: FastAPI) -> None:
    """Apply `use_actual_validation_error_schema` to the app's generated OpenAPI schema."""
    generate = app.openapi

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = use_actual_validation_error_schema(generate())
        return app.openapi_schema

    app.openapi = openapi
