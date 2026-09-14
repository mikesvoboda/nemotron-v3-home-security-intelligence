#!/usr/bin/env python3
"""Reset the admin user password to a known value.

Usage:
    uv run python scripts/reset-admin-password.py
    # Or from inside backend container:
    python scripts/reset-admin-password.py
"""
import asyncio
import os
import re
import socket
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def _load_env_and_fix_database_url() -> None:
    """Load .env and fix DATABASE_URL for local execution (postgres -> localhost)."""
    from dotenv import load_dotenv

    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        return

    match = re.search(r"@([^:/@]+):(\d+)/", database_url)
    if not match:
        return

    hostname, port = match.groups()
    try:
        socket.gethostbyname(hostname)
        return
    except socket.gaierror:
        pass

    postgres_port = os.environ.get("POSTGRES_PORT", "5432")
    new_url = database_url.replace(f"@{hostname}:{port}/", f"@127.0.0.1:{postgres_port}/")
    os.environ["DATABASE_URL"] = new_url


async def main() -> None:
    _load_env_and_fix_database_url()

    from sqlalchemy import select

    from backend.core.database import get_session, init_db
    from backend.models.user import User
    from backend.services.auth_service import hash_password

    await init_db()

    async with get_session() as session:
        result = await session.execute(select(User).where(User.username == "admin"))
        user = result.scalar_one_or_none()
        if not user:
            print("Admin user not found.")
            sys.exit(1)

        user.password_hash = hash_password("admin")
        await session.commit()
        print("Admin password set to 'admin'.")


if __name__ == "__main__":
    asyncio.run(main())
