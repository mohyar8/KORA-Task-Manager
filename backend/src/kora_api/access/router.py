from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status

from kora_api.access import service
from kora_api.access.dependencies import (
    CSRF_COOKIE,
    CSRF_COOKIE_PATH,
    SESSION_COOKIE,
    SESSION_COOKIE_PATH,
    AuthenticatedSession,
)
from kora_api.access.models import UserAccount
from kora_api.access.schemas import (
    AccountResponse,
    ChangePasswordRequest,
    SessionResponse,
    SignInRequest,
)
from kora_api.core.database import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid username or password."


@router.post("/sign-in")
async def sign_in(body: SignInRequest, response: Response, db: DbSession) -> SessionResponse:
    try:
        issued = await service.sign_in(db, body.username, body.password)
    except service.AuthenticationFailedError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, INVALID_CREDENTIALS) from None
    except service.SignInLockedError as exc:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(exc.retry_after_seconds)},
        ) from None
    return await _start_session(db, response, issued)


@router.post("/sign-out", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out(auth: AuthenticatedSession, response: Response, db: DbSession) -> None:
    await service.sign_out(db, auth.session)
    _clear_cookies(response)


@router.post("/sign-out-all", status_code=status.HTTP_204_NO_CONTENT)
async def sign_out_all(auth: AuthenticatedSession, response: Response, db: DbSession) -> None:
    await service.sign_out_all(db, auth.account.id)
    _clear_cookies(response)


@router.get("/me")
async def current_account(auth: AuthenticatedSession, db: DbSession) -> AccountResponse:
    return await _account_response(db, auth.account)


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest, auth: AuthenticatedSession, response: Response, db: DbSession
) -> SessionResponse:
    try:
        issued = await service.change_password(
            db, auth.account, body.current_password, body.new_password
        )
    except service.CurrentPasswordIncorrectError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect.") from None
    except service.InvalidPasswordError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Password does not meet the policy."
        ) from None
    return await _start_session(db, response, issued)


async def _start_session(
    db: DbSession, response: Response, issued: service.IssuedSession
) -> SessionResponse:
    session = issued.session
    # The session token travels only in this HttpOnly cookie, never in a response body.
    cookies: tuple[tuple[str, str, str, bool, Literal["lax", "strict"]], ...] = (
        (SESSION_COOKIE, issued.token, SESSION_COOKIE_PATH, True, "lax"),
        # Readable by the frontend so it can echo the value in the X-CSRF-Token header.
        (CSRF_COOKIE, issued.csrf_token, CSRF_COOKIE_PATH, False, "strict"),
    )
    for name, value, path, httponly, samesite in cookies:
        response.set_cookie(
            name,
            value,
            expires=session.expires_at,
            path=path,
            secure=True,
            httponly=httponly,
            samesite=samesite,
        )
    account = await db.get_one(UserAccount, session.account_id)
    return SessionResponse(
        account=await _account_response(db, account), csrf_token=issued.csrf_token
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE, path=SESSION_COOKIE_PATH, secure=True, httponly=True, samesite="lax"
    )
    response.delete_cookie(CSRF_COOKIE, path=CSRF_COOKIE_PATH, secure=True, samesite="strict")


async def _account_response(db: DbSession, account: UserAccount) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        username=account.username,
        must_change_password=account.password_is_temporary,
        is_system_admin=await service.is_system_admin(db, account.id),
    )
