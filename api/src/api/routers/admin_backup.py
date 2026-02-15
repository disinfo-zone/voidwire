"""Admin backup management -- local and S3-compatible storage."""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.config import get_settings
from voidwire.models import AdminUser, SiteSetting
from voidwire.services.encryption import decrypt_value, encrypt_value

from api.dependencies import get_db, require_admin

router = APIRouter()

BACKUP_STORAGE_KEY = "backup.storage"


class BackupStorageUpdateRequest(BaseModel):
    provider: str = "local"  # local | s3
    s3_endpoint: str | None = None
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_prefix: str | None = None
    s3_use_ssl: bool | None = None


def _default_storage_config() -> dict:
    return {
        "provider": "local",
        "s3_endpoint": "",
        "s3_bucket": "",
        "s3_region": "us-east-1",
        "s3_access_key_encrypted": "",
        "s3_secret_key_encrypted": "",
        "s3_prefix": "voidwire-backups/",
        "s3_use_ssl": True,
    }


def _mask_tail(value: str, visible: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible:
        return "*" * len(text)
    return f"{'*' * max(len(text) - visible, 4)}{text[-visible:]}"


def _safe_filename(filename: str) -> str:
    """Validate filename to prevent directory traversal."""
    base = os.path.basename(filename)
    if not base or base != filename or ".." in base:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return base


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


async def _load_storage_config(db: AsyncSession) -> dict:
    row = await db.get(SiteSetting, BACKUP_STORAGE_KEY)
    merged = _default_storage_config()
    if row is not None and isinstance(row.value, dict):
        merged.update(row.value)
    return merged


def _storage_response_payload(config: dict) -> dict:
    access_key = ""
    secret_key = ""
    try:
        if config.get("s3_access_key_encrypted"):
            access_key = decrypt_value(str(config.get("s3_access_key_encrypted")))
    except Exception:
        access_key = ""
    try:
        if config.get("s3_secret_key_encrypted"):
            secret_key = decrypt_value(str(config.get("s3_secret_key_encrypted")))
    except Exception:
        secret_key = ""
    return {
        "provider": str(config.get("provider", "local")).strip().lower() or "local",
        "s3_endpoint": str(config.get("s3_endpoint", "")).strip(),
        "s3_bucket": str(config.get("s3_bucket", "")).strip(),
        "s3_region": str(config.get("s3_region", "us-east-1")).strip() or "us-east-1",
        "s3_prefix": str(config.get("s3_prefix", "voidwire-backups/")).strip(),
        "s3_use_ssl": bool(config.get("s3_use_ssl", True)),
        "s3_access_key_masked": _mask_tail(access_key),
        "s3_secret_key_masked": _mask_tail(secret_key),
        "s3_is_configured": bool(access_key and secret_key),
    }


def _merge_storage_update(current: dict, req: BackupStorageUpdateRequest) -> dict:
    provider = str(req.provider or current.get("provider", "local")).strip().lower()
    if provider not in {"local", "s3"}:
        raise HTTPException(status_code=400, detail="provider must be one of: local, s3")

    merged = dict(current)
    merged["provider"] = provider
    if req.s3_endpoint is not None:
        merged["s3_endpoint"] = req.s3_endpoint.strip()
    if req.s3_bucket is not None:
        merged["s3_bucket"] = req.s3_bucket.strip()
    if req.s3_region is not None:
        merged["s3_region"] = req.s3_region.strip() or "us-east-1"
    if req.s3_prefix is not None:
        merged["s3_prefix"] = req.s3_prefix.strip()
    if req.s3_use_ssl is not None:
        merged["s3_use_ssl"] = bool(req.s3_use_ssl)

    if req.s3_access_key is not None:
        access = req.s3_access_key.strip()
        if access:
            try:
                merged["s3_access_key_encrypted"] = encrypt_value(access)
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail="Could not encrypt S3 access key. Check ENCRYPTION_KEY."
                ) from exc
        else:
            merged["s3_access_key_encrypted"] = ""
    if req.s3_secret_key is not None:
        secret = req.s3_secret_key.strip()
        if secret:
            try:
                merged["s3_secret_key_encrypted"] = encrypt_value(secret)
            except Exception as exc:
                raise HTTPException(
                    status_code=400, detail="Could not encrypt S3 secret key. Check ENCRYPTION_KEY."
                ) from exc
        else:
            merged["s3_secret_key_encrypted"] = ""

    return merged


def _s3_prefix(config: dict) -> str:
    prefix = str(config.get("s3_prefix", "")).strip()
    if not prefix:
        return ""
    prefix = prefix.lstrip("/")
    if not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _s3_key_for_filename(config: dict, filename: str) -> str:
    return f"{_s3_prefix(config)}{filename}"


def _build_s3_client(config: dict):
    try:
        import boto3
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="S3 support is unavailable (missing boto3 in API image). Rebuild API image.",
        ) from exc

    endpoint = str(config.get("s3_endpoint", "")).strip()
    bucket = str(config.get("s3_bucket", "")).strip()
    region = str(config.get("s3_region", "us-east-1")).strip() or "us-east-1"
    if not endpoint or not bucket:
        raise HTTPException(
            status_code=400, detail="S3 backup storage is missing endpoint or bucket"
        )

    access = ""
    secret = ""
    try:
        if config.get("s3_access_key_encrypted"):
            access = decrypt_value(str(config.get("s3_access_key_encrypted")))
        if config.get("s3_secret_key_encrypted"):
            secret = decrypt_value(str(config.get("s3_secret_key_encrypted")))
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail="S3 backup credentials could not be decrypted"
        ) from exc

    if not access or not secret:
        raise HTTPException(
            status_code=400, detail="S3 backup storage is missing access key or secret key"
        )

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=region,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        use_ssl=bool(config.get("s3_use_ssl", True)),
    )
    return client, bucket


def _is_s3_mode(config: dict) -> bool:
    return str(config.get("provider", "local")).strip().lower() == "s3"


async def _run_backup_storage_drill(storage: dict) -> dict:
    started = datetime.now(UTC)
    t0 = perf_counter()
    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        marker = backup_dir / f"voidwire_drill_{started.strftime('%Y%m%d_%H%M%S')}.txt"
        payload = f"voidwire-backup-drill:{started.isoformat()}".encode()
        marker.write_bytes(payload)
        roundtrip = marker.read_bytes()
        marker.unlink(missing_ok=True)
        if roundtrip != payload:
            raise RuntimeError("Backup drill read/write mismatch")
        return {
            "status": "ok",
            "provider": "local",
            "started_at": started.isoformat(),
            "duration_ms": round((perf_counter() - t0) * 1000, 2),
        }

    client, bucket = _build_s3_client(storage)
    key = _s3_key_for_filename(storage, f"voidwire_drill_{started.strftime('%Y%m%d_%H%M%S')}.txt")
    payload = f"voidwire-backup-drill:{started.isoformat()}".encode()
    await asyncio.to_thread(client.put_object, Bucket=bucket, Key=key, Body=payload)
    obj = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
    roundtrip = await asyncio.to_thread(obj["Body"].read)
    await asyncio.to_thread(client.delete_object, Bucket=bucket, Key=key)
    if roundtrip != payload:
        raise RuntimeError("S3 backup drill read/write mismatch")
    return {
        "status": "ok",
        "provider": "s3",
        "started_at": started.isoformat(),
        "duration_ms": round((perf_counter() - t0) * 1000, 2),
    }


@router.get("/")
async def list_backups(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    storage = await _load_storage_config(db)
    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        files = sorted(
            [*backup_dir.glob("*.dump"), *backup_dir.glob("*.sql.gz")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return {"backups": [_backup_info(f) for f in files], "storage": "local"}

    client, bucket = _build_s3_client(storage)
    prefix = _s3_prefix(storage)
    try:
        result = await asyncio.to_thread(client.list_objects_v2, Bucket=bucket, Prefix=prefix)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"S3 list failed: {exc}") from exc

    backups = []
    for item in result.get("Contents", []) or []:
        key = str(item.get("Key", ""))
        if not key or key.endswith("/"):
            continue
        if not (key.endswith(".dump") or key.endswith(".sql.gz")):
            continue
        backups.append(
            {
                "filename": key[len(prefix) :] if prefix and key.startswith(prefix) else key,
                "size_bytes": int(item.get("Size", 0)),
                "created_at": item.get("LastModified").isoformat()
                if item.get("LastModified")
                else None,
            }
        )
    backups.sort(key=lambda b: b.get("created_at") or "", reverse=True)
    return {"backups": backups, "storage": "s3"}


@router.get("/storage")
async def get_backup_storage_settings(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    config = await _load_storage_config(db)
    return _storage_response_payload(config)


@router.post("/drill")
async def run_backup_drill(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    storage = await _load_storage_config(db)
    try:
        return await _run_backup_storage_drill(storage)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Backup drill failed: {exc}") from exc


@router.put("/storage")
async def update_backup_storage_settings(
    req: BackupStorageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    current = await _load_storage_config(db)
    merged = _merge_storage_update(current, req)
    setting = await db.get(SiteSetting, BACKUP_STORAGE_KEY)
    if setting is None:
        setting = SiteSetting(
            key=BACKUP_STORAGE_KEY,
            value=merged,
            category="backup",
            description="Backup storage configuration (local or S3-compatible)",
        )
        db.add(setting)
    else:
        setting.value = merged
        setting.category = "backup"
        setting.updated_at = datetime.now(UTC)
    await db.flush()
    return _storage_response_payload(merged)


@router.post("/create")
async def create_backup(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    params = _db_params()
    storage = await _load_storage_config(db)
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"voidwire_{timestamp}.dump"

    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    # PostgreSQL custom archive format compatible with pg_restore.
    pg_dump_cmd = [
        "pg_dump",
        "-h",
        params["host"],
        "-p",
        params["port"],
        "-U",
        params["user"],
        "-Fc",
        params["dbname"],
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *pg_dump_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await proc.communicate()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="pg_dump is not installed in API container. Rebuild with PostgreSQL client tools.",
        ) from exc

    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"pg_dump failed: {stderr.decode(errors='replace')[:500]}",
        )

    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        filepath = backup_dir / filename
        filepath.write_bytes(stdout)
        return _backup_info(filepath)

    client, bucket = _build_s3_client(storage)
    key = _s3_key_for_filename(storage, filename)
    try:
        await asyncio.to_thread(
            client.put_object,
            Bucket=bucket,
            Key=key,
            Body=stdout,
            ContentType="application/octet-stream",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {exc}") from exc

    return {
        "filename": filename,
        "size_bytes": len(stdout),
        "created_at": datetime.now(UTC).isoformat(),
    }


@router.post("/{filename}/restore")
async def restore_backup(
    filename: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    safe = _safe_filename(filename)
    storage = await _load_storage_config(db)
    params = _db_params()
    env = os.environ.copy()
    if params["password"]:
        env["PGPASSWORD"] = params["password"]

    restore_path: str | None = None
    tmp_path: Path | None = None
    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        filepath = backup_dir / safe
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        restore_path = str(filepath)
    else:
        client, bucket = _build_s3_client(storage)
        key = _s3_key_for_filename(storage, safe)
        try:
            obj = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
            body = await asyncio.to_thread(obj["Body"].read)
        except Exception as exc:
            raise HTTPException(
                status_code=404, detail=f"S3 backup file not found: {safe}"
            ) from exc
        fd, tmp_name = tempfile.mkstemp(prefix="voidwire_restore_", suffix=".dump")
        os.close(fd)
        tmp_path = Path(tmp_name)
        tmp_path.write_bytes(body)
        restore_path = str(tmp_path)

    pg_restore_cmd = [
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
        str(restore_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *pg_restore_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        _, stderr = await proc.communicate()
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="pg_restore is not installed in API container. Rebuild with PostgreSQL client tools.",
        ) from exc
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    if proc.returncode != 0:
        err_text = stderr.decode(errors="replace")[:500]
        # pg_restore returns non-zero for warnings too; only fail on real errors
        if "error" in err_text.lower() and "warning" not in err_text.lower():
            raise HTTPException(status_code=500, detail=f"pg_restore failed: {err_text}")

    return {"status": "restored", "filename": safe}


@router.delete("/{filename}")
async def delete_backup(
    filename: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    _ = user
    safe = _safe_filename(filename)
    storage = await _load_storage_config(db)
    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        filepath = backup_dir / safe
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        filepath.unlink()
        return {"status": "deleted", "filename": safe}

    client, bucket = _build_s3_client(storage)
    key = _s3_key_for_filename(storage, safe)
    try:
        await asyncio.to_thread(client.delete_object, Bucket=bucket, Key=key)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"S3 delete failed: {exc}") from exc
    return {"status": "deleted", "filename": safe}


@router.get("/{filename}/download")
async def download_backup(
    filename: str,
    user: AdminUser = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    """Download backup file."""
    _ = user

    safe = _safe_filename(filename)
    storage = await _load_storage_config(db)
    if not _is_s3_mode(storage):
        backup_dir = _backup_dir()
        filepath = backup_dir / safe
        if not filepath.exists():
            raise HTTPException(status_code=404, detail="Backup file not found")
        return FileResponse(
            path=str(filepath),
            filename=safe,
            media_type="application/gzip" if safe.endswith(".gz") else "application/octet-stream",
        )

    client, bucket = _build_s3_client(storage)
    key = _s3_key_for_filename(storage, safe)
    try:
        obj = await asyncio.to_thread(client.get_object, Bucket=bucket, Key=key)
        data = await asyncio.to_thread(obj["Body"].read)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Backup file not found") from exc

    media_type = "application/gzip" if safe.endswith(".gz") else "application/octet-stream"
    return Response(
        content=data,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )
