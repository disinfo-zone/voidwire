"""Setup wizard API."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, LLMConfig, NewsSource, SetupState, SiteSetting
from voidwire.services.encryption import encrypt_value
from api.dependencies import get_db
from api.middleware.auth import hash_password, generate_totp_secret, get_totp_uri
from api.services.llm_slots import ensure_default_llm_slots
from api.services.template_defaults import ensure_starter_prompt_template

router = APIRouter()

class AdminCreateRequest(BaseModel):
    email: str
    password: str

class LLMSlotRequest(BaseModel):
    slot: str
    provider_name: str
    api_endpoint: str
    model_id: str
    api_key: str
    temperature: float = 0.7

class SiteConfigRequest(BaseModel):
    site_title: str = "VOIDWIRE"
    timezone: str = "UTC"
    auto_publish: bool = False

@router.get("/status")
async def get_setup_status(db: AsyncSession = Depends(get_db)):
    state = await db.get(SetupState, 1)
    if not state:
        return {"is_complete": False, "steps_completed": []}
    return {"is_complete": state.is_complete, "steps_completed": state.steps_completed or []}

@router.post("/init-db")
async def init_database(db: AsyncSession = Depends(get_db)):
    state = await db.get(SetupState, 1)
    if not state:
        state = SetupState(id=1, steps_completed=[])
        db.add(state)
    steps = list(state.steps_completed or [])
    if "db_init" not in steps:
        steps.append("db_init")
        state.steps_completed = steps
    await ensure_default_llm_slots(db)
    await ensure_starter_prompt_template(db)
    return {"status": "ok", "step": "db_init"}

@router.post("/create-admin")
async def create_admin(req: AdminCreateRequest, db: AsyncSession = Depends(get_db)):
    state = await db.get(SetupState, 1)
    if not state:
        raise HTTPException(status_code=400, detail="Run init-db first")
    totp_secret = generate_totp_secret()
    admin = AdminUser(email=req.email, password_hash=hash_password(req.password), totp_secret=encrypt_value(totp_secret))
    db.add(admin)
    steps = list(state.steps_completed or [])
    if "admin_created" not in steps:
        steps.append("admin_created")
        state.steps_completed = steps
    return {"status": "ok", "totp_uri": get_totp_uri(totp_secret, req.email), "totp_secret": totp_secret}

@router.post("/configure-llm")
async def configure_llm(req: LLMSlotRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(LLMConfig).where(LLMConfig.slot == req.slot))
    config = existing.scalars().first()
    encrypted_key = encrypt_value(req.api_key)
    if config:
        config.provider_name = req.provider_name
        config.api_endpoint = req.api_endpoint
        config.model_id = req.model_id
        config.api_key_encrypted = encrypted_key
    else:
        db.add(LLMConfig(slot=req.slot, provider_name=req.provider_name, api_endpoint=req.api_endpoint, model_id=req.model_id, api_key_encrypted=encrypted_key, temperature=req.temperature))
    state = await db.get(SetupState, 1)
    if state:
        steps = list(state.steps_completed or [])
        if "llm_configured" not in steps:
            steps.append("llm_configured")
            state.steps_completed = steps
    return {"status": "ok", "slot": req.slot}

@router.post("/configure-site")
async def configure_site(req: SiteConfigRequest, db: AsyncSession = Depends(get_db)):
    for key, val, cat in [("site.title", {"value": req.site_title}, "general"), ("site.timezone", {"value": req.timezone}, "general"), ("pipeline.auto_publish", {"enabled": req.auto_publish}, "pipeline")]:
        setting = await db.get(SiteSetting, key)
        if setting:
            setting.value = val
        else:
            db.add(SiteSetting(key=key, value=val, category=cat))
    state = await db.get(SetupState, 1)
    if state:
        steps = list(state.steps_completed or [])
        if "settings_configured" not in steps:
            steps.append("settings_configured")
            state.steps_completed = steps
    return {"status": "ok"}

@router.post("/complete")
async def complete_setup(db: AsyncSession = Depends(get_db)):
    state = await db.get(SetupState, 1)
    if not state:
        raise HTTPException(status_code=400, detail="Setup not initialized")
    await ensure_default_llm_slots(db)
    await ensure_starter_prompt_template(db)
    state.is_complete = True
    state.completed_at = datetime.now(timezone.utc)
    return {"status": "ok", "setup_complete": True}
