"""Backup service -- delegates to pg_dump/pg_restore via subprocess."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from voidwire.config import get_settings


def get_backup_dir() -> Path:
    settings = get_settings()
    p = Path(settings.backup_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_db_params() -> dict[str, str]:
    """Extract host/port/user/dbname from DATABASE_URL."""
    settings = get_settings()
    url = settings.database_url.replace("+asyncpg", "")
    parsed = urlparse(url)
    return {
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "user": parsed.username or "voidwire",
        "password": parsed.password or "",
        "dbname": parsed.path.lstrip("/") or "voidwire",
    }


async def create_backup() -> dict:
    """Run pg_dump and save to backup directory. Returns backup metadata."""
    params = get_db_params()
    backup_dir = get_backup_dir()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"voidwire_{timestamp}.sql.gz"
    filepath = backup_dir / filename

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    proc = await asyncio.create_subprocess_exec(
        "pg_dump",
        "-h",
        params["host"],
        "-p",
        params["port"],
        "-U",
        params["user"],
        "-Fc",
        params["dbname"],
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"pg_dump failed: {stderr.decode(errors='replace')[:500]}")

    filepath.write_bytes(stdout)

    stat = filepath.stat()
    return {
        "filename": filepath.name,
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }


async def restore_backup(filename: str) -> None:
    """Restore database from a backup file."""
    params = get_db_params()
    backup_dir = get_backup_dir()
    filepath = backup_dir / filename

    if not filepath.exists():
        raise FileNotFoundError(f"Backup file not found: {filename}")

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    proc = await asyncio.create_subprocess_exec(
        "pg_restore",
        "-h",
        params["host"],
        "-p",
        params["port"],
        "-U",
        params["user"],
        "-d",
        params["dbname"],
        "--clean",
        "--if-exists",
        str(filepath),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err_text = stderr.decode(errors="replace")[:500]
        if "error" in err_text.lower() and "warning" not in err_text.lower():
            raise RuntimeError(f"pg_restore failed: {err_text}")
