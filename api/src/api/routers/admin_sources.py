"""Admin news source management."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import NewsSource, AuditLog, AdminUser
from api.dependencies import get_db, require_admin

router = APIRouter()

class SourceCreateRequest(BaseModel):
    name: str
    source_type: str = "rss"
    url: str
    domain: str = "anomalous"
    weight: float = 0.5
    max_articles: int = 10
    allow_fulltext: bool = False
    config: dict = {}

class SourceUpdateRequest(BaseModel):
    name: str | None = None
    url: str | None = None
    domain: str | None = None
    weight: float | None = None
    status: str | None = None
    max_articles: int | None = None
    allow_fulltext: bool | None = None
    config: dict | None = None

def _source_dict(s: NewsSource) -> dict:
    return {
        "id": str(s.id), "name": s.name, "source_type": s.source_type,
        "url": s.url, "domain": s.domain, "weight": s.weight,
        "status": s.status, "max_articles": s.max_articles,
        "allow_fulltext": s.allow_fulltext_extract,
        "config": s.config,
        "last_fetch_at": s.last_fetch_at.isoformat() if s.last_fetch_at else None,
        "last_error": s.last_error, "error_count_7d": s.error_count_7d,
    }

@router.get("/")
async def list_sources(db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    result = await db.execute(select(NewsSource).order_by(NewsSource.name))
    return [_source_dict(s) for s in result.scalars().all()]

@router.get("/{source_id}")
async def get_source(source_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = await db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _source_dict(source)

@router.post("/")
async def create_source(req: SourceCreateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = NewsSource(
        name=req.name, source_type=req.source_type, url=req.url,
        domain=req.domain, weight=req.weight, max_articles=req.max_articles,
        allow_fulltext_extract=req.allow_fulltext, config=req.config,
    )
    db.add(source)
    await db.flush()
    db.add(
        AuditLog(
            user_id=user.id,
            action="source.create",
            target_type="source",
            target_id=str(source.id),
            detail={"name": source.name, "domain": source.domain, "url": source.url},
        )
    )
    return {"id": str(source.id), "status": "created"}

@router.patch("/{source_id}")
async def update_source(source_id: UUID, req: SourceUpdateRequest, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = await db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for field in ("name", "url", "domain", "weight", "status", "max_articles", "config"):
        val = getattr(req, field, None)
        if val is not None:
            setattr(source, field, val)
    if req.allow_fulltext is not None:
        source.allow_fulltext_extract = req.allow_fulltext
    db.add(
        AuditLog(
            user_id=user.id,
            action="source.update",
            target_type="source",
            target_id=str(source_id),
            detail=req.model_dump(exclude_none=True),
        )
    )
    return {"status": "ok"}

@router.delete("/{source_id}")
async def delete_source(source_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = await db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    db.add(
        AuditLog(
            user_id=user.id,
            action="source.delete",
            target_type="source",
            target_id=str(source_id),
            detail={"name": source.name, "url": source.url},
        )
    )
    return {"status": "deleted"}

@router.post("/{source_id}/test-fetch")
async def test_fetch(source_id: UUID, db: AsyncSession = Depends(get_db), user: AdminUser = Depends(require_admin)):
    source = await db.get(NewsSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.source_type != "rss":
        raise HTTPException(status_code=400, detail="Test fetch only supported for RSS sources")
    from pipeline.news.rss_fetcher import fetch_rss
    try:
        articles = await fetch_rss(
            source_id=str(source.id), url=source.url,
            max_articles=3, domain=source.domain,
            weight=source.weight, allow_fulltext=source.allow_fulltext_extract,
        )
        db.add(
            AuditLog(
                user_id=user.id,
                action="source.test_fetch",
                target_type="source",
                target_id=str(source_id),
                detail={"result": "ok", "article_count": len(articles)},
            )
        )
        return {"status": "ok", "count": len(articles), "articles": articles}
    except Exception as e:
        db.add(
            AuditLog(
                user_id=user.id,
                action="source.test_fetch",
                target_type="source",
                target_id=str(source_id),
                detail={"result": "error", "error": str(e)},
            )
        )
        return {"status": "error", "error": str(e)}
