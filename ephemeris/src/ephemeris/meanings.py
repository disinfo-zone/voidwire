"""Archetypal dictionary lookup with compositional fallback."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default planetary keywords for compositional fallback
DEFAULT_PLANETARY_KEYWORDS: dict[str, dict[str, Any]] = {
    "sun": {
        "keywords": ["identity", "vitality", "authority", "will", "purpose"],
        "archetype": "The conscious self and its drive toward expression and authority.",
        "domain_affinities": ["culture", "social"],
    },
    "moon": {
        "keywords": ["emotion", "instinct", "memory", "nourishment", "fluctuation"],
        "archetype": "The unconscious, emotional body and its tidal needs.",
        "domain_affinities": ["social", "health"],
    },
    "mercury": {
        "keywords": ["communication", "commerce", "thought", "mediation", "trickery"],
        "archetype": "The messenger principle: thought, speech, trade, and cunning.",
        "domain_affinities": ["technology", "economy", "culture"],
    },
    "venus": {
        "keywords": ["desire", "beauty", "value", "attraction", "harmony"],
        "archetype": "The principle of attraction, beauty, and the valuation of what matters.",
        "domain_affinities": ["culture", "economy", "diplomacy"],
    },
    "mars": {
        "keywords": ["force", "severance", "conflict", "drive", "assertion"],
        "archetype": "The principle of force, will, and the capacity to cut.",
        "domain_affinities": ["conflict", "legal"],
    },
    "jupiter": {
        "keywords": ["expansion", "abundance", "faith", "excess", "law"],
        "archetype": "The principle of expansion, meaning-making, and the reach beyond limit.",
        "domain_affinities": ["economy", "legal", "culture"],
    },
    "saturn": {
        "keywords": ["structure", "restriction", "limitation", "time", "authority"],
        "archetype": "The principle of limitation, structure, and the weight of consequence.",
        "domain_affinities": ["economy", "legal", "conflict"],
    },
    "uranus": {
        "keywords": ["disruption", "liberation", "innovation", "shock", "awakening"],
        "archetype": "The principle of sudden rupture, radical change, and systemic shock.",
        "domain_affinities": ["technology", "social", "conflict"],
    },
    "neptune": {
        "keywords": ["dissolution", "illusion", "transcendence", "confusion", "dream"],
        "archetype": "The principle of dissolution, where boundaries dissolve into fog or vision.",
        "domain_affinities": ["culture", "health", "environment"],
    },
    "pluto": {
        "keywords": ["transformation", "power", "death", "regeneration", "compulsion"],
        "archetype": "The principle of irreversible transformation and the power beneath the surface.",
        "domain_affinities": ["conflict", "economy", "social"],
    },
    "north_node": {
        "keywords": ["destiny", "growth", "collective direction", "appetite"],
        "archetype": "The point of collective hunger and evolutionary direction.",
        "domain_affinities": ["social", "culture"],
    },
    "chiron": {
        "keywords": ["wound", "healing", "teaching", "bridge", "vulnerability"],
        "archetype": "The wound that teaches: where damage becomes expertise.",
        "domain_affinities": ["health", "social", "culture"],
    },
}

# Default aspect keywords for compositional fallback
DEFAULT_ASPECT_KEYWORDS: dict[str, dict[str, Any]] = {
    "conjunction": {
        "keywords": ["fusion", "intensification", "merging", "concentration"],
        "archetype": "Two principles occupying the same point: fusion or mutual intensification.",
    },
    "sextile": {
        "keywords": ["opportunity", "facilitation", "productive friction", "opening"],
        "archetype": "A productive angle offering opportunity without force.",
    },
    "square": {
        "keywords": ["friction", "tension", "obstruction", "crisis", "action"],
        "archetype": "Structural friction demanding action: the angle of crisis and forced growth.",
    },
    "trine": {
        "keywords": ["flow", "ease", "harmony", "talent", "complacency"],
        "archetype": "The angle of ease and inherited capacity: gifts and their attendant laziness.",
    },
    "opposition": {
        "keywords": ["polarity", "confrontation", "projection", "awareness", "balance"],
        "archetype": "The full tension of polarity: confrontation, projection, and the possibility of synthesis.",
    },
    "quincunx": {
        "keywords": ["adjustment", "irritation", "misalignment", "recalibration"],
        "archetype": "An angle of persistent misalignment requiring constant adjustment.",
    },
    "semisquare": {
        "keywords": ["irritation", "minor friction", "agitation", "restlessness"],
        "archetype": "Low-grade friction producing irritation and restless agitation.",
    },
    "sesquiquadrate": {
        "keywords": ["tension", "agitation", "overreach", "friction"],
        "archetype": "Accumulated tension seeking release through agitation.",
    },
}



async def lookup_meaning(
    body1: str,
    body2: str | None,
    aspect_type: str | None,
    event_type: str,
    db_session: Any | None = None,
) -> dict[str, Any]:
    """Look up archetypal meaning with three-tier fallback.

    1. Check database for curated override
    2. Check database for LLM-generated entry
    3. Compositional fallback from keywords

    Args:
        body1: Primary celestial body
        body2: Secondary body (None for single-body events)
        aspect_type: Aspect type (None for non-aspect events)
        event_type: Type of event (aspect, retrograde, ingress, station, lunar_phase)
        db_session: Optional async database session

    Returns:
        Dict with core_meaning, keywords, domain_affinities
    """
    # Tier 1 & 2: Database lookup
    if db_session is not None:
        try:
            from sqlalchemy import select
            from voidwire.models.archetypal_meaning import ArchetypalMeaning

            query = select(ArchetypalMeaning).where(
                ArchetypalMeaning.body1 == body1,
                ArchetypalMeaning.event_type == event_type,
            )
            if body2:
                query = query.where(ArchetypalMeaning.body2 == body2)
            if aspect_type:
                query = query.where(ArchetypalMeaning.aspect_type == aspect_type)

            # Prefer curated over generated
            query = query.order_by(
                ArchetypalMeaning.source.desc()  # 'curated' > 'generated'
            )

            result = await db_session.execute(query)
            meaning = result.scalars().first()
            if meaning:
                return {
                    "core_meaning": meaning.core_meaning,
                    "keywords": list(meaning.keywords),
                    "domain_affinities": list(meaning.domain_affinities),
                }
        except Exception as e:
            logger.warning("Database lookup failed, using fallback: %s", e)

    # Tier 3: Compositional fallback
    return compose_meaning(body1, body2, aspect_type, event_type)


def compose_meaning(
    body1: str,
    body2: str | None,
    aspect_type: str | None,
    event_type: str,
) -> dict[str, Any]:
    """Compose a meaning from planetary and aspect keywords."""
    b1_data = DEFAULT_PLANETARY_KEYWORDS.get(body1, {})
    b1_keywords = b1_data.get("keywords", [body1])
    b1_archetype = b1_data.get("archetype", body1.title())
    domains = list(b1_data.get("domain_affinities", []))

    if event_type == "aspect" and body2 and aspect_type:
        b2_data = DEFAULT_PLANETARY_KEYWORDS.get(body2, {})
        b2_keywords = b2_data.get("keywords", [body2])
        a_data = DEFAULT_ASPECT_KEYWORDS.get(aspect_type, {})
        a_keywords = a_data.get("keywords", [aspect_type])

        core = (
            f"{body1.title()} ({'/'.join(b1_keywords[:2])}) in "
            f"{aspect_type.title()} ({'/'.join(a_keywords[:2])}) with "
            f"{body2.title()} ({'/'.join(b2_keywords[:2])})"
        )
        keywords = b1_keywords[:2] + a_keywords[:2] + b2_keywords[:2]
        domains.extend(b2_data.get("domain_affinities", []))
    elif event_type == "retrograde":
        core = f"{body1.title()} stations retrograde. {b1_archetype} The principle turns inward, revisiting and revising."
        keywords = b1_keywords + ["reversal", "review", "internalization"]
    elif event_type == "station":
        core = f"{body1.title()} stations direct. {b1_archetype} The stalled principle resumes forward motion."
        keywords = b1_keywords + ["resumption", "release", "forward"]
    elif event_type == "ingress":
        core = f"{body1.title()} enters a new sign. {b1_archetype} The mode of expression shifts."
        keywords = b1_keywords + ["transition", "new mode", "shift"]
    elif event_type == "lunar_phase":
        core = f"Lunar phase event. The emotional and instinctual body marks a turning point."
        keywords = ["emotion", "instinct", "cycle", "turning point"]
    else:
        core = f"{body1.title()}: {b1_archetype}"
        keywords = b1_keywords

    return {
        "core_meaning": core,
        "keywords": keywords,
        "domain_affinities": list(set(domains)),
    }
