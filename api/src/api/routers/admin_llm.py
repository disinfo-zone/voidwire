"""Admin LLM configuration management."""
from __future__ import annotations
import time
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import LLMConfig, AdminUser, AuditLog
from voidwire.services.encryption import encrypt_value
from api.dependencies import get_db, require_admin
from api.services.llm_slots import ensure_default_llm_slots

router = APIRouter()

class LLMSlotUpdateRequest(BaseModel):
    provider_name: str | None = None
    api_endpoint: str | None = None
    model_id: str | None = None
    api_key: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    extra_params: dict | None = None
    is_active: bool | None = None


def _normalize_model_id(model_id: str | None, provider_name: str | None) -> str | None:
    if model_id is None:
        return None
    normalized = model_id.strip()
    provider = (provider_name or "").strip()
    if normalized and "/" not in normalized and provider:
        return f"{provider}/{normalized}"
    return normalized


def _slot_dict(c: LLMConfig) -> dict:
    masked_key = ""
    if c.api_key_encrypted:
        try:
            from voidwire.services.encryption import decrypt_value
            key = decrypt_value(c.api_key_encrypted)
            masked_key = f"****{key[-4:]}" if len(key) >= 4 else "****"
        except Exception:
            masked_key = "****"
    return {
        "id": str(c.id), "slot": c.slot,
        "provider_name": c.provider_name,
        "api_endpoint": c.api_endpoint,
        "model_id": c.model_id,
        "api_key_masked": masked_key,
        "max_tokens": c.max_tokens,
        "temperature": c.temperature,
        "extra_params": c.extra_params,
        "is_active": c.is_active,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

@router.get("/")
async def list_slots(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    slots = await ensure_default_llm_slots(db)
    return [_slot_dict(c) for c in slots]

@router.get("/{slot}")
async def get_slot(slot: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(LLMConfig).where(LLMConfig.slot == slot))
    config = result.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Slot not found")
    return _slot_dict(config)

@router.put("/{slot}")
async def update_slot(slot: str, req: LLMSlotUpdateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(LLMConfig).where(LLMConfig.slot == slot))
    config = result.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Slot not found")
    if req.provider_name is not None:
        config.provider_name = req.provider_name
    if req.api_endpoint is not None:
        config.api_endpoint = req.api_endpoint
    if req.model_id is not None:
        config.model_id = _normalize_model_id(
            req.model_id, req.provider_name or config.provider_name
        )
    if req.api_key is not None:
        config.api_key_encrypted = encrypt_value(req.api_key)
    if req.max_tokens is not None:
        config.max_tokens = req.max_tokens
    if req.temperature is not None:
        config.temperature = req.temperature
    if req.extra_params is not None:
        config.extra_params = req.extra_params
    if req.is_active is not None:
        config.is_active = req.is_active
    db.add(
        AuditLog(
            user_id=user.id,
            action="llm.update_slot",
            target_type="llm",
            target_id=slot,
            detail={
                "provider_name": config.provider_name,
                "api_endpoint": config.api_endpoint,
                "model_id": config.model_id,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "is_active": config.is_active,
                "api_key_updated": req.api_key is not None,
            },
        )
    )
    return {"status": "ok"}

@router.post("/{slot}/test")
async def test_slot(slot: str, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(LLMConfig).where(LLMConfig.slot == slot))
    config = result.scalars().first()
    if not config:
        raise HTTPException(status_code=404, detail="Slot not found")
    if not config.is_active:
        return {"status": "error", "error": "Slot is inactive"}
    from voidwire.services.llm_client import LLMClient, LLMSlotConfig
    client = LLMClient(timeout=30.0)
    client.configure_slot(LLMSlotConfig(
        slot=slot, provider_name=config.provider_name,
        api_endpoint=config.api_endpoint, model_id=config.model_id,
        api_key_encrypted=config.api_key_encrypted,
        max_tokens=config.max_tokens, temperature=config.temperature or 0.7,
    ))
    start = time.monotonic()
    try:
        if slot == "embedding":
            vectors = await client.generate_embeddings(
                slot,
                ["Voidwire embedding connectivity probe"],
            )
            dim = len(vectors[0]) if vectors and vectors[0] else 0
            response = f"Embedding generated ({dim} dimensions)"
        else:
            response = await client.generate(
                slot,
                [{"role": "user", "content": "Reply with exactly: OK"}],
            )
        latency_ms = round((time.monotonic() - start) * 1000)
        db.add(
            AuditLog(
                user_id=user.id,
                action="llm.test_slot",
                target_type="llm",
                target_id=slot,
                detail={"result": "ok", "latency_ms": latency_ms},
            )
        )
        await client.close()
        return {"status": "ok", "response": response.strip(), "latency_ms": latency_ms}
    except Exception as e:
        latency_ms = round((time.monotonic() - start) * 1000)
        db.add(
            AuditLog(
                user_id=user.id,
                action="llm.test_slot",
                target_type="llm",
                target_id=slot,
                detail={"result": "error", "latency_ms": latency_ms, "error": str(e)},
            )
        )
        await client.close()
        return {"status": "error", "error": str(e), "latency_ms": latency_ms}
