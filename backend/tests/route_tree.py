"""Enumerate the routes actually mounted on an app, independent of the OpenAPI schema.

Walks the Starlette/FastAPI route tree recursively: included routers (FastAPI keeps them as
nested `_IncludedRouter` objects exposing `original_router` + `include_context.prefix`), mounts
and sub-routers (`routes`), so routes with `include_in_schema=False` are found too.
"""

from collections.abc import Iterable, Iterator
from typing import Any

from fastapi import FastAPI


def mounted_routes(app: FastAPI) -> list[tuple[frozenset[str], str]]:
    """(HTTP methods, full path) for every leaf route; methods is empty for non-HTTP routes."""
    return sorted(_walk(app.routes, ""), key=lambda item: (item[1], sorted(item[0])))


def _walk(routes: Iterable[Any], prefix: str) -> Iterator[tuple[frozenset[str], str]]:
    for route in routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            yield from _walk(original_router.routes, prefix + route.include_context.prefix)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:  # Mount / Router
            yield from _walk(nested, prefix + getattr(route, "path", ""))
            continue
        yield frozenset(getattr(route, "methods", None) or ()), prefix + route.path
