"""Focused checks for session-cookie, CSRF and information-disclosure requirements."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from kora_api.access.dependencies import CSRF_COOKIE, SESSION_COOKIE, CurrentAccount
from kora_api.core.config import Settings
from kora_api.core.database import create_engine
from tests.access.helpers import (
    CHANGE_PASSWORD,
    ME,
    PASSWORD,
    SIGN_IN,
    SIGN_OUT,
    SIGN_OUT_ALL,
    create_account,
    csrf_headers,
    sign_in,
    signed_in,
)
from tests.conftest import ClientFactory

pytestmark = pytest.mark.anyio

NEW_PASSWORD = "a brand new passphrase"
PROTECTED_ACTION = "/api/v1/_test/protected-action"


def _set_cookies(response: Response) -> dict[str, dict[str, str]]:
    """Parse Set-Cookie headers into {name: {"value": ..., lowercased attribute: value}}."""
    cookies: dict[str, dict[str, str]] = {}
    for header in response.headers.get_list("set-cookie"):
        first, *attributes = header.split("; ")
        name, value = first.split("=", 1)
        parsed = {"value": value}
        for attribute in attributes:
            key, _, attr_value = attribute.partition("=")
            parsed[key.lower()] = attr_value
        cookies[name] = parsed
    return cookies


# --- Cookies and token exposure ----------------------------------------------------------------


async def test_session_cookie_attributes_and_token_never_in_body(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")

    response = await sign_in(db_client, "alice")

    cookies = _set_cookies(response)
    session = cookies[SESSION_COOKIE]
    assert "httponly" in session
    assert "secure" in session
    assert session["samesite"] == "lax"
    assert session["path"] == "/api"
    assert session["value"] not in response.text
    assert set(response.json()) == {"account", "csrf_token"}

    csrf = cookies[CSRF_COOKIE]
    assert "httponly" not in csrf  # intentionally readable; not a secret
    assert "secure" in csrf
    assert csrf["samesite"] == "strict"
    assert csrf["path"] == "/"  # readable from any frontend page
    assert csrf["value"] == response.json()["csrf_token"]


async def test_me_response_contains_no_tokens(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    response = await db_client.get(ME)

    assert db_client.cookies[SESSION_COOKIE] not in response.text
    assert csrf not in response.text


async def test_sign_out_expires_both_cookies_with_matching_attributes(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    response = await db_client.post(SIGN_OUT, headers=csrf_headers(csrf))

    cookies = _set_cookies(response)
    assert cookies[SESSION_COOKIE]["path"] == "/api"
    assert cookies[CSRF_COOKIE]["path"] == "/"
    assert all(cookie["max-age"] == "0" for cookie in cookies.values())
    assert not db_client.cookies


# --- CSRF --------------------------------------------------------------------------------------


async def test_sign_in_needs_no_csrf_token_even_with_existing_session(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    await signed_in(db_client, "alice")

    response = await db_client.post(SIGN_IN, json={"username": "alice", "password": PASSWORD})

    assert response.status_code == 200


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (SIGN_OUT, None),
        (SIGN_OUT_ALL, None),
        (CHANGE_PASSWORD, {"current_password": PASSWORD, "new_password": NEW_PASSWORD}),
    ],
)
@pytest.mark.parametrize("csrf_header", [None, "forged-token"])
async def test_state_changing_auth_routes_enforce_csrf(
    db_client: AsyncClient,
    db_session: AsyncSession,
    path: str,
    body: dict[str, str] | None,
    csrf_header: str | None,
) -> None:
    await create_account(db_session, "alice")
    await signed_in(db_client, "alice")
    headers = csrf_headers(csrf_header) if csrf_header else {}

    response = await db_client.post(path, json=body, headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "CSRF token missing or invalid."}
    assert (await db_client.get(ME)).status_code == 200  # session not revoked
    assert (await sign_in(db_client, "alice", PASSWORD)).status_code == 200  # password unchanged


async def test_csrf_token_from_another_session_is_rejected(
    client_factory: ClientFactory, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    mine, theirs = client_factory(), client_factory()
    await signed_in(mine, "alice")
    other_csrf = await signed_in(theirs, "alice")

    response = await mine.post(SIGN_OUT, headers=csrf_headers(other_csrf))

    assert response.status_code == 403


async def test_every_authenticated_unsafe_route_enforces_csrf(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    @db_app.post(PROTECTED_ACTION)
    async def protected_action(account: CurrentAccount) -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"username": account.username}

    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    assert (await db_client.post(PROTECTED_ACTION)).status_code == 403
    assert (await db_client.post(PROTECTED_ACTION, headers=csrf_headers(csrf))).status_code == 200


# --- Information disclosure --------------------------------------------------------------------


async def test_lockout_response_is_identical_for_existing_and_unknown_usernames(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    await create_account(db_session, "alice")
    locked: list[Response] = []
    for username in ("alice", "ghost"):
        for _ in range(5):
            await sign_in(db_client, username, "wrong password")
        locked.append(await sign_in(db_client, username))

    existing, unknown = locked
    assert existing.status_code == unknown.status_code == 429
    assert existing.json() == unknown.json()
    assert existing.headers["Retry-After"] == unknown.headers["Retry-After"]


@pytest.mark.parametrize(
    ("path", "body"),
    [
        (SIGN_IN, {"username": "alice", "password": "Leaked-Secret!" * 100}),
        (CHANGE_PASSWORD, {"current_password": PASSWORD, "new_password": "Leaked-Secret!" * 10}),
    ],
)
async def test_validation_errors_do_not_echo_submitted_passwords(
    db_client: AsyncClient, db_session: AsyncSession, path: str, body: dict[str, str]
) -> None:
    await create_account(db_session, "alice")
    csrf = await signed_in(db_client, "alice")

    response = await db_client.post(path, json=body, headers=csrf_headers(csrf))

    assert response.status_code == 422
    assert "Leaked-Secret!" not in response.text
    assert PASSWORD not in response.text


def test_database_engine_hides_sql_parameters_from_logs_and_errors() -> None:
    engine = create_engine(Settings(environment="test", database_echo=True))
    assert engine.sync_engine.hide_parameters is True
