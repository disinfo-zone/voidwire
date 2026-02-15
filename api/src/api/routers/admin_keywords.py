"""Admin CRUD for PlanetaryKeyword and AspectKeyword tables."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser
from voidwire.models.archetypal_meaning import AspectKeyword, PlanetaryKeyword

from api.dependencies import get_db, require_admin

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────


class PlanetaryKeywordRequest(BaseModel):
    keywords: list[str]
    archetype: str
    domain_affinities: list[str] = []


class AspectKeywordRequest(BaseModel):
    keywords: list[str]
    archetype: str


# ── Helpers ───────────────────────────────────────────────────────


def _planetary_dict(pk: PlanetaryKeyword) -> dict:
    return {
        "body": pk.body,
        "keywords": pk.keywords,
        "archetype": pk.archetype,
        "domain_affinities": pk.domain_affinities,
    }


def _aspect_dict(ak: AspectKeyword) -> dict:
    return {
        "aspect_type": ak.aspect_type,
        "keywords": ak.keywords,
        "archetype": ak.archetype,
    }


# ── Planetary Keywords ────────────────────────────────────────────


@router.get("/planetary")
async def list_planetary(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    result = await db.execute(select(PlanetaryKeyword).order_by(PlanetaryKeyword.body))
    return [_planetary_dict(pk) for pk in result.scalars().all()]


@router.get("/planetary/{body}")
async def get_planetary(
    body: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    pk = await db.get(PlanetaryKeyword, body)
    if not pk:
        raise HTTPException(status_code=404, detail="Planetary keyword not found")
    return _planetary_dict(pk)


@router.put("/planetary/{body}")
async def upsert_planetary(
    body: str,
    req: PlanetaryKeywordRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    pk = await db.get(PlanetaryKeyword, body)
    if pk:
        pk.keywords = req.keywords
        pk.archetype = req.archetype
        pk.domain_affinities = req.domain_affinities
    else:
        pk = PlanetaryKeyword(
            body=body,
            keywords=req.keywords,
            archetype=req.archetype,
            domain_affinities=req.domain_affinities,
        )
        db.add(pk)
    await db.flush()
    return _planetary_dict(pk)


@router.delete("/planetary/{body}")
async def delete_planetary(
    body: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    pk = await db.get(PlanetaryKeyword, body)
    if not pk:
        raise HTTPException(status_code=404, detail="Planetary keyword not found")
    await db.delete(pk)
    return {"status": "deleted"}


# ── Aspect Keywords ───────────────────────────────────────────────


@router.get("/aspect")
async def list_aspect(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    result = await db.execute(select(AspectKeyword).order_by(AspectKeyword.aspect_type))
    return [_aspect_dict(ak) for ak in result.scalars().all()]


@router.get("/aspect/{aspect_type}")
async def get_aspect(
    aspect_type: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    ak = await db.get(AspectKeyword, aspect_type)
    if not ak:
        raise HTTPException(status_code=404, detail="Aspect keyword not found")
    return _aspect_dict(ak)


@router.put("/aspect/{aspect_type}")
async def upsert_aspect(
    aspect_type: str,
    req: AspectKeywordRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    ak = await db.get(AspectKeyword, aspect_type)
    if ak:
        ak.keywords = req.keywords
        ak.archetype = req.archetype
    else:
        ak = AspectKeyword(
            aspect_type=aspect_type,
            keywords=req.keywords,
            archetype=req.archetype,
        )
        db.add(ak)
    await db.flush()
    return _aspect_dict(ak)


@router.delete("/aspect/{aspect_type}")
async def delete_aspect(
    aspect_type: str,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    ak = await db.get(AspectKeyword, aspect_type)
    if not ak:
        raise HTTPException(status_code=404, detail="Aspect keyword not found")
    await db.delete(ak)
    return {"status": "deleted"}
