"""Admin user account and billing management."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import AdminUser, AuditLog, DiscountCode, Subscription, User

from api.dependencies import get_db, require_admin
from api.services.billing_reconciliation import run_billing_reconciliation
from api.services.discount_code_service import (
    is_discount_code_usable,
    normalize_discount_code,
)
from api.services.governance import run_retention_cleanup
from api.services.stripe_service import (
    create_coupon_and_promotion_code,
    set_promotion_code_active,
)
from api.services.subscription_service import has_active_pro_override

router = APIRouter()
ACTIVE_SUBSCRIPTION_STATUSES = ("active", "trialing")
ADMIN_ROLES: tuple[str, ...] = ("owner", "admin", "support", "readonly")


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _jsonable_detail(payload: dict) -> dict:
    normalized: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, datetime):
            normalized_datetime = _as_utc(value)
            normalized[key] = (
                normalized_datetime.isoformat() if normalized_datetime else None
            )
        else:
            normalized[key] = value
    return normalized


def _serialize_discount_code(code: DiscountCode) -> dict:
    percent_off = code.percent_off
    return {
        "id": str(code.id),
        "code": code.code,
        "description": code.description,
        "percent_off": float(percent_off) if isinstance(percent_off, Decimal) else percent_off,
        "amount_off_cents": code.amount_off_cents,
        "currency": code.currency,
        "duration": code.duration,
        "duration_in_months": code.duration_in_months,
        "max_redemptions": code.max_redemptions,
        "starts_at": code.starts_at.isoformat() if code.starts_at else None,
        "expires_at": code.expires_at.isoformat() if code.expires_at else None,
        "is_active": code.is_active,
        "is_usable_now": is_discount_code_usable(code),
        "created_at": code.created_at.isoformat() if code.created_at else None,
        "updated_at": code.updated_at.isoformat() if code.updated_at else None,
    }


def _serialize_user(user: User, *, has_active_subscription: bool) -> dict:
    tier = "pro" if has_active_pro_override(user) or has_active_subscription else "free"
    return {
        "id": str(user.id),
        "email": user.email,
        "display_name": user.display_name,
        "email_verified": user.email_verified,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "tier": tier,
        "has_active_subscription": has_active_subscription,
        "pro_override": user.pro_override,
        "pro_override_reason": user.pro_override_reason,
        "pro_override_until": (
            user.pro_override_until.isoformat() if user.pro_override_until else None
        ),
    }


def _serialize_admin_user(user: AdminUser) -> dict:
    role = str(getattr(user, "role", "owner")).strip().lower() or "owner"
    if role not in ADMIN_ROLES:
        role = "owner"
    return {
        "id": str(user.id),
        "email": user.email,
        "role": role,
        "is_active": bool(user.is_active),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


class UserProOverrideRequest(BaseModel):
    enabled: bool
    reason: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = None

    @field_validator("reason")
    @classmethod
    def _trim_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class DiscountCodeCreateRequest(BaseModel):
    code: str = Field(min_length=3, max_length=32)
    description: str | None = Field(default=None, max_length=240)
    percent_off: float | None = Field(default=None, gt=0, le=100)
    amount_off_cents: int | None = Field(default=None, ge=1)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    duration: Literal["once", "forever", "repeating"] = "once"
    duration_in_months: int | None = Field(default=None, ge=1, le=36)
    max_redemptions: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return normalize_discount_code(value)

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def _validate_discount_fields(self) -> DiscountCodeCreateRequest:
        if (self.percent_off is None) == (self.amount_off_cents is None):
            raise ValueError("Provide exactly one of percent_off or amount_off_cents")
        if self.amount_off_cents is not None and not self.currency:
            raise ValueError("currency is required with amount_off_cents")
        if self.amount_off_cents is None and self.currency:
            raise ValueError("currency is only allowed with amount_off_cents")
        if self.duration == "repeating" and self.duration_in_months is None:
            raise ValueError("duration_in_months is required for repeating discounts")
        if self.duration != "repeating" and self.duration_in_months is not None:
            raise ValueError("duration_in_months is only valid for repeating discounts")

        starts_at = _as_utc(self.starts_at)
        expires_at = _as_utc(self.expires_at)
        if starts_at and expires_at and expires_at <= starts_at:
            raise ValueError("expires_at must be after starts_at")
        return self


class DiscountCodeUpdateRequest(BaseModel):
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=240)
    starts_at: datetime | None = None
    expires_at: datetime | None = None

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class AdminUserUpdateRequest(BaseModel):
    role: Literal["owner", "admin", "support", "readonly"] | None = None
    is_active: bool | None = None


async def _count_active_owners(db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count(AdminUser.id)).where(
            AdminUser.role == "owner",
            AdminUser.is_active.is_(True),
        )
    )
    return int(result.scalar() or 0)


@router.get("/users")
async def list_users(
    q: str | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    query = select(User).order_by(User.created_at.desc())
    if q:
        query = query.where(func.lower(User.email).contains(q.strip().lower()))
    if not include_inactive:
        query = query.where(User.is_active.is_(True))

    result = await db.execute(query.limit(limit).offset(offset))
    users = result.scalars().all()
    if not users:
        return []

    user_ids = [u.id for u in users]
    active_subs_result = await db.execute(
        select(Subscription.user_id)
        .where(
            Subscription.user_id.in_(user_ids),
            Subscription.status.in_(ACTIVE_SUBSCRIPTION_STATUSES),
        )
        .group_by(Subscription.user_id)
    )
    active_sub_user_ids = {row[0] for row in active_subs_result.all()}
    return [
        _serialize_user(u, has_active_subscription=u.id in active_sub_user_ids) for u in users
    ]


@router.get("/admin-users")
async def list_admin_users(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    result = await db.execute(select(AdminUser).order_by(AdminUser.created_at.asc()))
    return [_serialize_admin_user(admin_user) for admin_user in result.scalars().all()]


@router.patch("/admin-users/{admin_user_id}")
async def update_admin_user(
    admin_user_id: uuid.UUID,
    req: AdminUserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    changes = req.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    target = await db.get(AdminUser, admin_user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Admin user not found")

    actor_role = str(getattr(user, "role", "owner")).strip().lower() or "owner"
    if actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only owner can modify admin roles")

    if "role" in changes and req.role is not None:
        next_role = str(req.role).strip().lower()
        if next_role not in ADMIN_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        if target.role == "owner" and next_role != "owner":
            owner_count = await _count_active_owners(db)
            if owner_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot demote the last active owner",
                )
        target.role = next_role

    if "is_active" in changes:
        if req.is_active is None:
            raise HTTPException(status_code=400, detail="is_active cannot be null")
        if target.id == user.id and req.is_active is False:
            raise HTTPException(
                status_code=400,
                detail="You cannot deactivate your own admin account",
            )
        if target.role == "owner" and req.is_active is False:
            owner_count = await _count_active_owners(db)
            if owner_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot deactivate the last active owner",
                )
        target.is_active = req.is_active

    db.add(
        AuditLog(
            user_id=user.id,
            action="admin_user.update",
            target_type="admin_user",
            target_id=str(target.id),
            detail={"changes": changes},
        )
    )
    await db.flush()
    return _serialize_admin_user(target)


@router.patch("/users/{user_id}/pro-override")
async def update_user_pro_override(
    user_id: uuid.UUID,
    req: UserProOverrideRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(require_admin),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    now = datetime.now(UTC)
    expires_at = _as_utc(req.expires_at)
    if req.enabled and expires_at is not None and expires_at <= now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    if req.enabled:
        user.pro_override = True
        user.pro_override_reason = req.reason
        user.pro_override_until = expires_at
    else:
        user.pro_override = False
        user.pro_override_reason = None
        user.pro_override_until = None

    db.add(
        AuditLog(
            user_id=admin.id,
            action="user.pro_override.update",
            target_type="user",
            target_id=str(user.id),
            detail={
                "enabled": user.pro_override,
                "expires_at": (
                    user.pro_override_until.isoformat()
                    if user.pro_override_until
                    else None
                ),
                "reason": user.pro_override_reason,
            },
        )
    )
    return {
        "status": "ok",
        "user_id": str(user.id),
        "pro_override": user.pro_override,
        "pro_override_reason": user.pro_override_reason,
        "pro_override_until": (
            user.pro_override_until.isoformat() if user.pro_override_until else None
        ),
    }


@router.get("/discount-codes")
async def list_discount_codes(
    include_inactive: bool = True,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    del user
    query = select(DiscountCode)
    if not include_inactive:
        query = query.where(DiscountCode.is_active.is_(True))
    query = query.order_by(DiscountCode.created_at.desc()).limit(500)
    result = await db.execute(query)
    return [_serialize_discount_code(code) for code in result.scalars().all()]


@router.post("/discount-codes")
async def create_discount_code(
    req: DiscountCodeCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    now = datetime.now(UTC)
    starts_at = _as_utc(req.starts_at)
    expires_at = _as_utc(req.expires_at)
    if expires_at and expires_at <= now:
        raise HTTPException(status_code=400, detail="expires_at must be in the future")

    existing = await db.execute(select(DiscountCode.id).where(DiscountCode.code == req.code))
    if existing.scalars().first() is not None:
        raise HTTPException(status_code=409, detail="Discount code already exists")

    try:
        stripe_ids = create_coupon_and_promotion_code(
            code=req.code,
            percent_off=req.percent_off,
            amount_off_cents=req.amount_off_cents,
            currency=req.currency,
            duration=req.duration,
            duration_in_months=req.duration_in_months,
            max_redemptions=req.max_redemptions,
            expires_at=expires_at,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to create discount code in Stripe")

    discount_code = DiscountCode(
        code=req.code,
        description=req.description,
        stripe_coupon_id=stripe_ids["stripe_coupon_id"],
        stripe_promotion_code_id=stripe_ids["stripe_promotion_code_id"],
        percent_off=req.percent_off,
        amount_off_cents=req.amount_off_cents,
        currency=req.currency,
        duration=req.duration,
        duration_in_months=req.duration_in_months,
        max_redemptions=req.max_redemptions,
        starts_at=starts_at,
        expires_at=expires_at,
        is_active=True,
        created_by_admin_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db.add(discount_code)
    await db.flush()

    db.add(
        AuditLog(
            user_id=user.id,
            action="discount_code.create",
            target_type="discount_code",
            target_id=str(discount_code.id),
            detail={
                "code": discount_code.code,
                "duration": discount_code.duration,
                "percent_off": req.percent_off,
                "amount_off_cents": req.amount_off_cents,
            },
        )
    )
    return _serialize_discount_code(discount_code)


@router.delete("/discount-codes/{discount_code_id}")
async def delete_discount_code(
    discount_code_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    discount_code = await db.get(DiscountCode, discount_code_id)
    if not discount_code:
        raise HTTPException(status_code=404, detail="Discount code not found")

    if discount_code.is_active:
        try:
            set_promotion_code_active(
                discount_code.stripe_promotion_code_id,
                active=False,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Failed to deactivate promotion code in Stripe",
            )
        discount_code.is_active = False

    code_label = discount_code.code
    await db.delete(discount_code)
    db.add(
        AuditLog(
            user_id=user.id,
            action="discount_code.delete",
            target_type="discount_code",
            target_id=str(discount_code_id),
            detail={"code": code_label},
        )
    )
    return {"status": "deleted"}


@router.patch("/discount-codes/{discount_code_id}")
async def update_discount_code(
    discount_code_id: uuid.UUID,
    req: DiscountCodeUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    discount_code = await db.get(DiscountCode, discount_code_id)
    if not discount_code:
        raise HTTPException(status_code=404, detail="Discount code not found")

    changes = req.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No changes provided")

    now = datetime.now(UTC)
    if "description" in changes:
        discount_code.description = req.description
    if "starts_at" in changes:
        discount_code.starts_at = _as_utc(req.starts_at)
    if "expires_at" in changes:
        normalized_expires = _as_utc(req.expires_at)
        if normalized_expires and normalized_expires <= now:
            raise HTTPException(status_code=400, detail="expires_at must be in the future")
        discount_code.expires_at = normalized_expires
    if (
        discount_code.starts_at
        and discount_code.expires_at
        and discount_code.expires_at <= discount_code.starts_at
    ):
        raise HTTPException(status_code=400, detail="expires_at must be after starts_at")

    if "is_active" in changes:
        if req.is_active is None:
            raise HTTPException(status_code=400, detail="is_active cannot be null")
        if discount_code.is_active != req.is_active:
            try:
                set_promotion_code_active(
                    discount_code.stripe_promotion_code_id,
                    active=req.is_active,
                )
            except RuntimeError as exc:
                raise HTTPException(status_code=503, detail=str(exc))
            except Exception:
                raise HTTPException(
                    status_code=400,
                    detail="Failed to update promotion code in Stripe",
                )
            discount_code.is_active = req.is_active

    discount_code.updated_at = now
    db.add(
        AuditLog(
            user_id=user.id,
            action="discount_code.update",
            target_type="discount_code",
            target_id=str(discount_code.id),
            detail=_jsonable_detail(changes),
        )
    )
    return _serialize_discount_code(discount_code)


@router.post("/billing/reconcile")
async def reconcile_billing(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    summary = await run_billing_reconciliation(db, trigger="manual")
    db.add(
        AuditLog(
            user_id=user.id,
            action="billing.reconcile.manual",
            target_type="billing",
            target_id="stripe",
            detail=summary,
        )
    )
    return summary


@router.post("/retention/cleanup")
async def trigger_retention_cleanup(
    db: AsyncSession = Depends(get_db),
    user: AdminUser = Depends(require_admin),
):
    summary = await run_retention_cleanup(db, trigger="manual")
    db.add(
        AuditLog(
            user_id=user.id,
            action="retention.cleanup.manual",
            target_type="governance",
            target_id="retention",
            detail=summary,
        )
    )
    return summary
