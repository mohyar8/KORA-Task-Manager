from datetime import UTC, datetime


def utcnow() -> datetime:
    """Timezone-aware UTC now. Call as `clock.utcnow()` so tests can patch it."""
    return datetime.now(UTC)
