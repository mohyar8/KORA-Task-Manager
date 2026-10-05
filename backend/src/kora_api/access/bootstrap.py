"""One-time creation of the first System Admin.

Usage: uv run python -m kora_api.access.bootstrap <username>

Prints a temporary password once; it expires in 7 days and must be changed at first sign-in.
Refuses to run if any System Admin grant has ever existed. There is no HTTP equivalent.
"""

import argparse
import asyncio
import sys

from kora_api.access import service
from kora_api.core.config import get_settings
from kora_api.core.database import create_engine, create_session_factory


async def _run(username: str) -> int:
    engine = create_engine(get_settings())
    try:
        async with create_session_factory(engine)() as db:
            account, temporary_password = await service.bootstrap_first_system_admin(db, username)
    except service.BootstrapAlreadyCompletedError:
        print("error: a System Admin already exists; bootstrap can run only once.", file=sys.stderr)
        return 1
    except service.InvalidUsernameError:
        print(
            "error: username must be 3-64 characters of letters, digits, '.', '_' or '-'.",
            file=sys.stderr,
        )
        return 1
    except service.UsernameTakenError:
        print("error: that username is already in use.", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()

    print(f"Created System Admin '{account.username}'.")
    print(f"Temporary password (shown once, expires in 7 days): {temporary_password}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m kora_api.access.bootstrap",
        description="Create the first System Admin account (one-time).",
    )
    parser.add_argument("username")
    args = parser.parse_args(argv)
    return asyncio.run(_run(args.username))


if __name__ == "__main__":
    sys.exit(main())
