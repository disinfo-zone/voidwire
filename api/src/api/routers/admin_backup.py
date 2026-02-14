"""Admin backup management -- list, create, restore, delete, download."""
from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AdminUser

from api.dependencies import get_db, require_admin

router = APIRouter()


def _backup_dir() -> Path:
    settings = get_settings()
    p = Path(settings.backup_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _db_params() -> dict[str, str]:
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


def _backup_info(path: Path) -> dict:
    stat = path.stat()
    return {
        "filename": path.name,
        "size_bytes": stat.st_size,
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }


def _safe_filename(filename: str) -> str:
    """Validate filename to prevent directory traversal."""
    base = os.path.basename(filename)
    if not base or base != filename or ".." in base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


@router.get("/")
async def list_backups(
    user: AdminUser = Depends(require_admin),
):
    backup_dir = _backup_dir()
    files = sorted(
        [*backup_dir.glob("*.dump"), *backup_dir.glob("*.sql.gz")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return {"backups": [_backup_info(f) for f in files]}


@router.post("/create")
async def create_backup(
    user: AdminUser = Depends(require_admin),
):
    params = _db_params()
    backup_dir = _backup_dir()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"voidwire_{timestamp}.dump"
    filepath = backup_dir / filename

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    # PostgreSQL custom archive format compatible with pg_restore.
    pg_dump_cmd = [
        "pg_dump",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-Fc",
        params["dbname"],
    ]

    proc = await asyncio.create_subprocess_exec(
        *pg_dump_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"pg_dump failed: {stderr.decode(errors='replace')[:500]}",
        )

    filepath.write_bytes(stdout)

    return _backup_info(filepath)


@router.post("/{filename}/restore")
async def restore_backup(
    filename: str,
    user: AdminUser = Depends(require_admin),
):
    safe = _safe_filename(filename)
    backup_dir = _backup_dir()
    filepath = backup_dir / safe

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    params = _db_params()
    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    pg_restore_cmd = [
        "pg_restore",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["dbname"],
        "--clean",
        "--if-exists",
        str(filepath),
    ]

    proc = await asyncio.create_subprocess_exec(
        *pg_restore_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err_text = stderr.decode(errors="replace")[:500]
        # pg_restore returns non-zero for warnings too; only fail on real errors
        if "error" in err_text.lower() and "warning" not in err_text.lower():
            raise HTTPException(status_code=500, detail=f"pg_restore failed: {err_text}")

    return {"status": "restored", "filename": safe}


@router.delete("/{filename}")
async def delete_backup(
    filename: str,
    user: AdminUser = Depends(require_admin),
):
    safe = _safe_filename(filename)
    backup_dir = _backup_dir()
    filepath = backup_dir / safe

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    filepath.unlink()
    return {"status": "deleted", "filename": safe}


@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Download backup file. Requires bearer token in Authorization header."""
    settings = get_settings()

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    raw_token = auth[7:]

    try:
        payload = jwt.decode(raw_token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub", "")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = await db.get(AdminUser, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    safe = _safe_filename(filename)
    backup_dir = _backup_dir()
    filepath = backup_dir / safe

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    return FileResponse(
        path=str(filepath),
        filename=safe,
        media_type="application/gzip" if safe.endswith(".gz") else "application/octet-stream",
    )
