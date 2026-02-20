"""Planet definitions, orb tables, and sign data."""

from __future__ import annotations

# Celestial body IDs for pyswisseph
# These map to swisseph constants
BODY_IDS: dict[str, int] = {
    "sun": 0,  # SE_SUN
    "moon": 1,  # SE_MOON
    "mercury": 2,  # SE_MERCURY
    "venus": 3,  # SE_VENUS
    "mars": 4,  # SE_MARS
    "jupiter": 5,  # SE_JUPITER
    "saturn": 6,  # SE_SATURN
    "uranus": 7,  # SE_URANUS
    "neptune": 8,  # SE_NEPTUNE
    "pluto": 9,  # SE_PLUTO
    "north_node": 11,  # SE_TRUE_NODE (true node, not mean)
    "lilith": 12,  # SE_MEAN_APOG (Black Moon Lilith, mean apogee)
    "chiron": 15,  # SE_CHIRON
}

# Bodies to include in position calculations (all)
ALL_BODIES = list(BODY_IDS.keys())

# Bodies to check for aspects (exclude nodes, include Chiron/Lilith)
ASPECT_BODIES = [b for b in ALL_BODIES if b != "north_node"]

# Zodiac signs in order
SIGNS = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

# Aspect definitions: name -> exact angle
ASPECTS: dict[str, float] = {
    "conjunction": 0.0,
    "sextile": 60.0,
    "square": 90.0,
    "trine": 120.0,
    "opposition": 180.0,
    "quincunx": 150.0,
    "semisquare": 45.0,
    "sesquiquadrate": 135.0,
}

# Default orbs by aspect type (in degrees)
# Major aspects get wider orbs
DEFAULT_ORBS: dict[str, float] = {
    "conjunction": 10.0,
    "opposition": 10.0,
    "square": 8.0,
    "trine": 8.0,
    "sextile": 6.0,
    "quincunx": 3.0,
    "semisquare": 2.0,
    "sesquiquadrate": 2.0,
}

# Orb modifiers by body type
# Luminaries (Sun, Moon) get full orb; outer planets get reduced
ORB_MODIFIERS: dict[str, float] = {
    "sun": 1.0,
    "moon": 1.0,
    "mercury": 0.8,
    "venus": 0.8,
    "mars": 0.8,
    "jupiter": 0.7,
    "saturn": 0.7,
    "uranus": 0.6,
    "neptune": 0.6,
    "pluto": 0.6,
    "lilith": 0.5,
    "chiron": 0.5,
    "north_node": 0.5,
}

# Significance classification
MAJOR_ASPECTS = {"conjunction", "opposition", "square", "trine"}
MODERATE_ASPECTS = {"sextile", "quincunx"}
MINOR_ASPECTS = {"semisquare", "sesquiquadrate"}


def get_effective_orb(body1: str, body2: str, aspect: str) -> float:
    """Calculate effective orb for an aspect between two bodies."""
    base_orb = DEFAULT_ORBS.get(aspect, 5.0)
    mod1 = ORB_MODIFIERS.get(body1, 0.7)
    mod2 = ORB_MODIFIERS.get(body2, 0.7)
    # Use average of the two body modifiers
    return base_orb * (mod1 + mod2) / 2


def longitude_to_sign(longitude: float) -> tuple[str, float]:
    """Convert ecliptic longitude to sign and degree within sign."""
    longitude = longitude % 360.0
    sign_index = int(longitude / 30.0)
    degree = longitude - (sign_index * 30.0)
    return SIGNS[sign_index], degree


def aspect_significance(aspect_type: str) -> str:
    """Classify aspect significance."""
    if aspect_type in MAJOR_ASPECTS:
        return "major"
    elif aspect_type in MODERATE_ASPECTS:
        return "moderate"
    return "minor"
