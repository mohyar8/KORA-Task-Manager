"""Checks every response the test suite receives against the OpenAPI document.

`RecordResponses` wraps the test apps and records each response. At the end of the session
`undocumented(...)` reports any (method, route, status) whose status is not documented for that
operation, and any error body that does not have the documented shape (422: `detail` is a list
or a string; other errors: `detail` is a string). Requests to paths or methods that OpenAPI
does not describe (e.g. test-only routes, 405s) are not checked.
"""

import json
import re
from dataclasses import dataclass
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass(frozen=True)
class Observed:
    method: str
    path: str
    status: int
    body: bytes


RESPONSES: list[Observed] = []


class RecordResponses:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        status = 0
        body = bytearray()

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            elif message["type"] == "http.response.body" and status >= 400:
                body.extend(message.get("body", b""))
            await send(message)

        await self.app(scope, receive, capture)
        RESPONSES.append(Observed(scope["method"], scope["path"], status, bytes(body)))


def _operations(schema: dict[str, Any]) -> list[tuple[str, re.Pattern[str], str, set[int]]]:
    found: list[tuple[str, re.Pattern[str], str, set[int]]] = []
    for template, operations in schema["paths"].items():
        pattern = re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", template) + "$")
        for method, operation in operations.items():
            codes = {int(code) for code in operation["responses"]}
            found.append((method.upper(), pattern, template, codes))
    # Prefer literal segments (`/notifications/preferences`) over parameters.
    found.sort(key=lambda op: op[2].count("{"))
    return found


def _shape_problem(observed: Observed) -> str | None:
    if observed.status < 400 or not observed.body:
        return None
    try:
        detail = json.loads(observed.body)["detail"]
    except (ValueError, KeyError, TypeError):
        return "error body has no `detail`"
    if observed.status == 422:
        return None if isinstance(detail, str | list) else "422 `detail` is not a list or string"
    return None if isinstance(detail, str) else "`detail` is not a string"


def undocumented(schema: dict[str, Any]) -> list[str]:
    operations = _operations(schema)
    problems: set[str] = set()
    for observed in RESPONSES:
        match = next(
            (
                (template, codes)
                for method, pattern, template, codes in operations
                if method == observed.method and pattern.match(observed.path)
            ),
            None,
        )
        if match is None:
            continue
        template, codes = match
        if observed.status not in codes:
            problems.add(f"{observed.method} {template}: {observed.status} not documented")
        shape = _shape_problem(observed)
        if shape:
            problems.add(f"{observed.method} {template} {observed.status}: {shape}")
    return sorted(problems)
