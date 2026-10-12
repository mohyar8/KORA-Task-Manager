"""The OpenAPI document matches the API's real behavior (see also tests/response_contract.py,
which checks every response the suite receives against it)."""

from typing import Any

import pytest

from kora_api.core.config import Settings
from kora_api.main import create_app
from tests import response_contract

UNSAFE = {"post", "put", "patch", "delete"}
PUBLIC = {("get", "/api/v1/health"), ("post", "/api/v1/auth/sign-in")}


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    return create_app(Settings(environment="test")).openapi()


def _operations(schema: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method, path, operation)
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
    ]


def test_422_documents_the_actual_format(schema: dict[str, Any]) -> None:
    components = schema["components"]["schemas"]
    assert "HTTPValidationError" not in components
    assert "ValidationError" not in components
    detail = components["ValidationErrorResponse"]["properties"]["detail"]["anyOf"]
    assert detail[0]["items"] == {"$ref": "#/components/schemas/ValidationIssue"}
    assert detail[1] == {"type": "string"}
    assert "input" not in components["ValidationIssue"]["properties"]
    refs = [
        op["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
        for _, _, op in _operations(schema)
        if "422" in op["responses"]
    ]
    assert refs and set(refs) == {"#/components/schemas/ValidationErrorResponse"}


def test_guard_errors_are_documented(schema: dict[str, Any]) -> None:
    for method, path, operation in _operations(schema):
        codes = set(operation["responses"])
        if (method, path) in PUBLIC:
            assert "403" not in codes, (method, path)
            continue
        assert "401" in codes, (method, path)
        if method in UNSAFE or path != "/api/v1/auth/me":
            assert "403" in codes, (method, path)
        for code in codes - {"200", "201", "204", "422"}:
            content = operation["responses"][code]["content"]["application/json"]["schema"]
            assert content == {"$ref": "#/components/schemas/ErrorResponse"}, (method, path, code)


def test_calendar_range_is_required_and_event_scope_is_not_an_input(
    schema: dict[str, Any],
) -> None:
    params = {
        p["name"]: p["required"] for p in schema["paths"]["/api/v1/calendar"]["get"]["parameters"]
    }
    assert params == {"from": True, "to": True}
    update = schema["components"]["schemas"]["UpdateEventRequest"]["properties"]
    assert "scope_unit_id" not in update


def test_response_schemas_use_precise_types(schema: dict[str, Any]) -> None:
    components = schema["components"]["schemas"]
    series = components["SeriesResponse"]["properties"]
    assert series["status"] == {"$ref": "#/components/schemas/SeriesStatus"}
    assert series["subtask_templates"]["items"] == {
        "$ref": "#/components/schemas/SubtaskTemplateResponse"
    }
    member = components["MemberResponse"]["properties"]
    # A response carries no input constraints.
    assert not [name for name, field in member.items() if "Length" in str(field)]
    assert {"$ref": "#/components/schemas/RoleKey"} in member["role_key"]["anyOf"]
    assert components["TaskEventResponse"]["properties"]["kind"] == {
        "$ref": "#/components/schemas/EventKind"
    }
    assert set(components["HistoryResponse"]["properties"]["kind"]["enum"]) == {
        "created",
        "updated",
        "cancelled",
        "invitee_added",
        "invitee_removed",
    }
    for name in ("PermissionResponse", "RoleDefaultResponse", "OverrideResponse"):
        field = components[name]["properties"].get("permission") or components[name][
            "properties"
        ].get("key")
        assert field == {"$ref": "#/components/schemas/Permission"}, name


def test_response_check_reports_undocumented_statuses(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guards the guard: an undocumented status or a malformed error body is reported."""
    schema: dict[str, Any] = {
        "paths": {"/api/v1/things/{id}": {"get": {"responses": {"200": {}, "404": {}}}}}
    }
    observed = [
        response_contract.Observed("GET", "/api/v1/things/1", 200, b""),
        response_contract.Observed("GET", "/api/v1/things/1", 404, b'{"detail": "Not found."}'),
        response_contract.Observed("GET", "/api/v1/things/1", 409, b'{"detail": "x"}'),
        response_contract.Observed("GET", "/api/v1/things/1", 404, b'{"detail": ["x"]}'),
        response_contract.Observed("GET", "/api/v1/other", 500, b""),  # not described: skipped
    ]
    monkeypatch.setattr(response_contract, "RESPONSES", observed)

    assert response_contract.undocumented(schema) == [
        "GET /api/v1/things/{id} 404: `detail` is not a string",
        "GET /api/v1/things/{id}: 409 not documented",
    ]
