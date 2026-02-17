"""User profile and natal chart management endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from ephemeris.natal import calculate_natal_chart
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from voidwire.models import User, UserProfile

from api.dependencies import get_current_public_user, get_db

router = APIRouter()


class BirthDataRequest(BaseModel):
    birth_date: date
    birth_time: str | None = None  # "HH:MM" or null
    birth_time_known: bool = False
    birth_city: str = Field(min_length=1, max_length=200)
    birth_latitude: float = Field(ge=-90, le=90)
    birth_longitude: float = Field(ge=-180, le=180)
    birth_timezone: str = Field(min_length=1, max_length=64)
    house_system: str = "placidus"

    @field_validator("birth_time")
    @classmethod
    def validate_birth_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        _parse_time(value)
        return value

    @field_validator("birth_timezone")
    @classmethod
    def validate_birth_timezone(cls, value: str) -> str:
        # Ensure timezone is an IANA identifier we can resolve deterministically.
        cleaned = value.strip()
        try:
            ZoneInfo(cleaned)
        except Exception as exc:
            raise ValueError("birth_timezone must be a valid IANA timezone") from exc
        return cleaned


class HouseSystemRequest(BaseModel):
    house_system: str


VALID_HOUSE_SYSTEMS = {"placidus", "whole_sign", "koch", "equal", "porphyry"}


def _parse_time(time_str: str | None) -> time | None:
    if not time_str:
        return None
    try:
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError("Invalid time format")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise ValueError("birth_time must use HH:MM 24-hour format")


def _profile_payload(profile: UserProfile) -> dict:
    return {
        "birth_date": profile.birth_date.isoformat(),
        "birth_time": profile.birth_time.strftime("%H:%M") if profile.birth_time else None,
        "birth_time_known": profile.birth_time_known,
        "birth_city": profile.birth_city,
        "birth_latitude": profile.birth_latitude,
        "birth_longitude": profile.birth_longitude,
        "birth_timezone": profile.birth_timezone,
        "house_system": profile.house_system,
        "natal_chart_computed_at": (
            profile.natal_chart_computed_at.isoformat() if profile.natal_chart_computed_at else None
        ),
    }


def _compute_and_cache(profile: UserProfile) -> dict:
    """Compute natal chart and cache in profile."""
    chart = calculate_natal_chart(
        birth_date=profile.birth_date,
        birth_time=profile.birth_time,
        birth_latitude=profile.birth_latitude,
        birth_longitude=profile.birth_longitude,
        birth_timezone=profile.birth_timezone,
        house_system=profile.house_system,
    )
    profile.natal_chart_json = chart
    profile.natal_chart_computed_at = datetime.now(UTC)
    return chart


@router.get("/")
async def get_profile(
    user: User = Depends(get_current_public_user),
):
    if not user.profile:
        return {"has_profile": False}
    return {"has_profile": True, **_profile_payload(user.profile)}


@router.put("/birth-data")
async def set_birth_data(
    req: BirthDataRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if req.house_system not in VALID_HOUSE_SYSTEMS:
        raise HTTPException(status_code=400, detail=f"Invalid house system: {req.house_system}")
    if req.birth_date > date.today():
        raise HTTPException(status_code=400, detail="Birth date cannot be in the future")
    if req.birth_time_known and not req.birth_time:
        raise HTTPException(
            status_code=400,
            detail="birth_time is required when birth_time_known is true",
        )

    try:
        parsed_time = _parse_time(req.birth_time) if req.birth_time_known else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    profile = user.profile
    if not profile:
        profile = UserProfile(user_id=user.id)
        db.add(profile)

    profile.birth_date = req.birth_date
    profile.birth_time = parsed_time
    profile.birth_time_known = req.birth_time_known
    profile.birth_city = req.birth_city.strip()
    profile.birth_latitude = req.birth_latitude
    profile.birth_longitude = req.birth_longitude
    profile.birth_timezone = req.birth_timezone.strip()
    profile.house_system = req.house_system
    profile.updated_at = datetime.now(UTC)

    # Compute natal chart
    _compute_and_cache(profile)
    await db.flush()

    return {"detail": "Birth data saved", **_profile_payload(profile)}


@router.put("/house-system")
async def set_house_system(
    req: HouseSystemRequest,
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if req.house_system not in VALID_HOUSE_SYSTEMS:
        raise HTTPException(status_code=400, detail=f"Invalid house system: {req.house_system}")

    if not user.profile:
        raise HTTPException(status_code=400, detail="No profile. Set birth data first.")

    user.profile.house_system = req.house_system
    user.profile.updated_at = datetime.now(UTC)

    # Recompute chart with new system
    _compute_and_cache(user.profile)

    return {"detail": "House system updated", "house_system": req.house_system}


@router.get("/natal-chart")
async def get_natal_chart(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="No profile. Set birth data first.")

    chart = user.profile.natal_chart_json
    # Recompute if chart is stale (e.g., missing part_of_fortune)
    if not chart or not any(
        p.get("body") == "part_of_fortune"
        for p in (chart.get("positions") or [])
    ):
        chart = _compute_and_cache(user.profile)
        await db.commit()

    return chart


@router.post("/natal-chart/recalculate")
async def recalculate_natal_chart(
    user: User = Depends(get_current_public_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.profile:
        raise HTTPException(status_code=400, detail="No profile. Set birth data first.")

    chart = _compute_and_cache(user.profile)
    return chart
