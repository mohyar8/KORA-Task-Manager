"""Release-readiness regressions over the whole mounted API (not a hand-picked list).

- Every unsafe route requires a session, a matching CSRF token and a usable (non-temporary)
  password, except the approved public route (sign-in) and the routes a temporary-password
  session needs (sign-out, sign-out-all, change-password).
- OpenAPI documents exactly the mounted routes, so no hidden route bypasses review.
- Staging/production refuse unsafe configuration; session cookies are always Secure.

Admin-only routes rejecting non-admins: tests/access/test_authorization_api.py. No bootstrap
HTTP endpoint: tests/access/test_system_admin.py.
"""

import re
import subprocess
import sys
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Literal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import CSRF_COOKIE, SESSION_COOKIE
from kora_api.core.config import LOCAL_DATABASE_URL, Settings
from kora_api.core.database import get_db_session
from kora_api.main import create_app
from tests.access.helpers import create_account, csrf_headers, sign_in, signed_in
from tests.conftest import DEPLOYED_DATABASE_URL, ClientFactory, production_settings
from tests.route_tree import mounted_routes

pytestmark = pytest.mark.anyio

BACKEND_DIR = Path(__file__).resolve().parent.parent
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PUBLIC_UNSAFE = {("POST", "/api/v1/auth/sign-in")}
# Reachable with a temporary password (CSRF still required).
TEMPORARY_PASSWORD_ALLOWED = {
    ("POST", "/api/v1/auth/sign-out"),
    ("POST", "/api/v1/auth/sign-out-all"),
    ("POST", "/api/v1/auth/change-password"),
}


def _unsafe_routes(app: FastAPI) -> list[tuple[str, str]]:
    routes = [
        (method, path)
        for methods, path in mounted_routes(app)
        for method in sorted(methods & UNSAFE)
    ]
    assert len(routes) > 40  # the walk reached every router
    return routes


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


async def test_every_unsafe_route_requires_session_csrf_and_usable_password(
    db_app: FastAPI, db_session: AsyncSession, client_factory: ClientFactory
) -> None:
    routes = _unsafe_routes(db_app)
    assert set(routes) >= PUBLIC_UNSAFE | TEMPORARY_PASSWORD_ALLOWED
    anonymous = client_factory()

    for method, path in routes:
        if (method, path) in PUBLIC_UNSAFE:
            continue
        response = await anonymous.request(method, _concrete(path), json={})
        assert response.status_code == 401, (method, path)

    await create_account(db_session, "usable")
    usable = client_factory()
    await signed_in(usable, "usable")
    for method, path in routes:
        if (method, path) in PUBLIC_UNSAFE:
            continue
        for headers in ({}, csrf_headers("forged-token")):
            response = await usable.request(method, _concrete(path), json={}, headers=headers)
            assert response.status_code == 403, (method, path)
            assert response.json() == {"detail": "CSRF token missing or invalid."}

    await create_account(db_session, "temporary", temporary=True)
    temporary = client_factory()
    csrf = await signed_in(temporary, "temporary")
    for method, path in routes:
        if (method, path) in PUBLIC_UNSAFE | TEMPORARY_PASSWORD_ALLOWED:
            continue
        response = await temporary.request(
            method, _concrete(path), json={}, headers=csrf_headers(csrf)
        )
        assert response.status_code == 403, (method, path)
        assert response.json() == {"detail": "Password change required."}
    # The exempt routes are reachable (an empty body fails validation, not the gate).
    response = await temporary.post(
        "/api/v1/auth/change-password", json={}, headers=csrf_headers(csrf)
    )
    assert response.status_code == 422


async def test_sign_in_is_the_only_unauthenticated_unsafe_route(db_app: FastAPI) -> None:
    anonymous = AsyncClient(transport=ASGITransport(app=db_app), base_url="https://test")
    async with anonymous:
        response = await anonymous.post("/api/v1/auth/sign-in", json={})
    assert response.status_code == 422  # reaches validation without a session


def test_bootstrap_cli_loads_every_model_it_may_flush() -> None:
    """Regression: run alone, the CLI must still resolve cross-domain foreign keys (e.g. the
    audit record's scope -> `org_units`). A clean interpreter, since this one imports all."""
    script = "; ".join(
        (
            "import kora_api.access.bootstrap",
            "from sqlalchemy.orm import configure_mappers",
            "from kora_api.core.database import Base",
            "configure_mappers()",
            "[fk.column for table in Base.metadata.tables.values() for fk in table.foreign_keys]",
        )
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=BACKEND_DIR, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr


def test_openapi_documents_exactly_the_mounted_routes() -> None:
    app = create_app(Settings(environment="test"))
    documented = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    mounted = {
        (method, path)
        for methods, path in mounted_routes(app)
        for method in methods - {"HEAD"}
        if path not in ("/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json")
    }
    assert documented == mounted
    assert all(path.startswith("/api/v1/") for _, path in mounted)
    assert not [path for _, path in mounted if "bootstrap" in path.lower()]


# --- Configuration ------------------------------------------------------------------------------


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_deployed_environments_reject_unsafe_settings(
    environment: Literal["staging", "production"],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv("KORA_DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)  # no local .env file
    with pytest.raises(ValidationError, match="KORA_DATABASE_URL"):
        Settings(environment=environment)
    with pytest.raises(ValidationError, match="KORA_DEBUG"):
        Settings(environment=environment, database_url=DEPLOYED_DATABASE_URL, debug=True)
    settings = Settings(environment=environment, database_url=DEPLOYED_DATABASE_URL)
    assert not settings.docs_enabled


def test_local_defaults_stay_local_and_no_cookie_security_setting_exists() -> None:
    assert Settings(environment="local").database_url.get_secret_value() == LOCAL_DATABASE_URL
    # Cookie security is fixed in code (always Secure/HttpOnly/SameSite); nothing can relax it.
    assert not [
        name
        for name in Settings.model_fields
        if any(part in name for part in ("cookie", "secure", "csrf", "samesite", "cors"))
    ]
    example = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    assert f"KORA_DATABASE_URL={LOCAL_DATABASE_URL}" in example  # local compose credentials only
    assert ".env" in (BACKEND_DIR / ".gitignore").read_text(encoding="utf-8").splitlines()


async def test_production_session_cookies_are_secure(
    test_database_url: str, db_session: AsyncSession
) -> None:
    app = create_app(production_settings())

    async def _session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _session_override
    await create_account(db_session, "alice")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="https://test") as client:
        response = await sign_in(client, "alice")
    assert response.status_code == 200
    cookies = {
        header.split("=", 1)[0]: header.lower()
        for header in response.headers.get_list("set-cookie")
    }
    assert {"secure", "httponly", "samesite=lax", "path=/api"} <= set(
        cookies[SESSION_COOKIE].split("; ")
    )
    assert {"secure", "samesite=strict"} <= set(cookies[CSRF_COOKIE].split("; "))
    assert app.docs_url is None and app.openapi_url is None


def test_database_url_is_never_rendered() -> None:
    settings = Settings(database_url=SecretStr("postgresql+asyncpg://u:hunter2@h/db"))
    assert "hunter2" not in repr(settings) and "hunter2" not in str(settings.model_dump())
