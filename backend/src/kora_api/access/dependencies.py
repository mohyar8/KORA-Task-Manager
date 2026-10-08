"""Authentication and authorization dependencies for routes.

- `AuthenticatedSession`: any live session, including one whose password must still be changed.
  Use only for sign-out, sign-out-all, current-account and change-password.
- `CurrentAccount`: a live session whose account is fully usable. Use for every other route;
  it enforces the temporary-password gate server-side.
- `SystemAdmin`: a `CurrentAccount` holding System Admin authority.
- `CurrentAccess`: a `CurrentAccount` plus its effective-access snapshot. Services call
  `snapshot.require(...)`; `require_permission(...)` checks a unit taken from the path.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from kora_api.access import authorization, security, service
from kora_api.access.evaluation import AccessDeniedError, AccessSnapshot
from kora_api.access.models import AuthSession, UserAccount
from kora_api.access.org_facts import OrganizationFacts
from kora_api.access.permissions import Permission
from kora_api.core.database import DbSession

SESSION_COOKIE = "kora_session"
CSRF_COOKIE = "kora_csrf"
CSRF_HEADER = "X-CSRF-Token"
# The session cookie is sent only to the API. The CSRF cookie is not a secret and must be
# readable by the frontend's pages (document.cookie only exposes cookies whose path matches).
SESSION_COOKIE_PATH = "/api"
CSRF_COOKIE_PATH = "/"
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class Authenticated:
    session: AuthSession
    account: UserAccount


async def get_authenticated(request: Request, db: DbSession) -> Authenticated:
    token = request.cookies.get(SESSION_COOKIE)
    resolved = await service.resolve_session(db, token) if token else None
    if resolved is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated.")
    session, account = resolved

    if request.method not in SAFE_METHODS:
        csrf_token = request.headers.get(CSRF_HEADER)
        if not csrf_token or not security.token_matches(csrf_token, session.csrf_token_hash):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token missing or invalid.")

    return Authenticated(session=session, account=account)


AuthenticatedSession = Annotated[Authenticated, Depends(get_authenticated)]


async def require_usable_account(auth: AuthenticatedSession) -> UserAccount:
    if auth.account.password_is_temporary:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Password change required.")
    return auth.account


CurrentAccount = Annotated[UserAccount, Depends(require_usable_account)]


async def require_system_admin(account: CurrentAccount, db: DbSession) -> UserAccount:
    if not await service.is_system_admin(db, account.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "System Admin authority required.")
    return account


SystemAdmin = Annotated[UserAccount, Depends(require_system_admin)]


def get_organization_facts(request: Request) -> OrganizationFacts:
    return cast(OrganizationFacts, request.app.state.organization_facts)


OrgFacts = Annotated[OrganizationFacts, Depends(get_organization_facts)]


@dataclass(frozen=True)
class AccessContext:
    account: UserAccount
    snapshot: AccessSnapshot


async def get_current_access(
    account: CurrentAccount, db: DbSession, facts: OrgFacts
) -> AccessContext:
    return AccessContext(account, await authorization.load_snapshot(db, facts, account.id))


CurrentAccess = Annotated[AccessContext, Depends(get_current_access)]


def require_permission(
    permission: Permission, unit_param: str = "unit_id"
) -> Callable[..., Awaitable[AccessContext]]:
    """Dependency factory: 403 unless `permission` is allowed on the unit in the path."""

    async def dependency(request: Request, access: CurrentAccess) -> AccessContext:
        try:
            unit_id = uuid.UUID(str(request.path_params.get(unit_param)))
        except ValueError:
            raise AccessDeniedError(permission, None) from None
        access.snapshot.require(permission, unit_id)
        return access

    return dependency


async def _access_denied(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": "Not permitted."})


def register_access_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AccessDeniedError, _access_denied)
