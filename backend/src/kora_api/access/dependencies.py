"""Authentication dependencies for routes.

- `AuthenticatedSession`: any live session, including one whose password must still be changed.
  Use only for sign-out, sign-out-all, current-account and change-password.
- `CurrentAccount`: a live session whose account is fully usable. Use for every other route;
  it enforces the temporary-password gate server-side.
"""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from kora_api.access import security, service
from kora_api.access.models import AuthSession, UserAccount
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
