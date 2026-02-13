"""Stochastic signal selection stage."""
from __future__ import annotations
import logging
import math
import random
from typing import Any

logger = logging.getLogger(__name__)
INTENSITY_SCORES = {"major": 3.0, "moderate": 2.0, "minor": 1.0}

async def run_selection_stage(signals: list[dict], seed: int, n_select: int = 9, n_wild: int = 1) -> list[dict]:
    if not signals:
        return []
    rng = random.Random(seed)
    major = [s for s in signals if s.get("intensity") == "major"]
    non_major = [s for s in signals if s.get("intensity") != "major"]
    selected = list(major)
    for s in selected:
        s["was_selected"] = True
        s["selection_weight"] = 1.0
    remaining = max(0, n_select - len(selected) - n_wild)
    if remaining > 0 and non_major:
        domain_counts: dict[str, int] = {}
        for s in selected:
            d = s.get("domain","")
            domain_counts[d] = domain_counts.get(d, 0) + 1
        weighted = []
        for s in non_major:
            w = INTENSITY_SCORES.get(s.get("intensity","minor"), 1.0) * s.get("weight", 0.5)
            if domain_counts.get(s.get("domain",""), 0) == 0:
                w *= 1.5
            weighted.append((s, w))
        for _ in range(min(remaining, len(weighted))):
            if not weighted:
                break
            total = sum(w for _, w in weighted)
            if total <= 0:
                break
            r = rng.random() * total
            cum = 0.0
            idx = 0
            for i, (_, w) in enumerate(weighted):
                cum += w
                if cum >= r:
                    idx = i
                    break
            chosen, cw = weighted.pop(idx)
            chosen["was_selected"] = True
            chosen["selection_weight"] = cw
            selected.append(chosen)
            domain_counts[chosen.get("domain","")] = domain_counts.get(chosen.get("domain",""), 0) + 1
    if n_wild > 0 and non_major:
        wild_cands = [s for s in non_major if not s.get("was_selected")]
        wild_cands = [s for s in wild_cands if s.get("intensity") in ("major","moderate") or s.get("weight",0) >= 0.5]
        if wild_cands:
            wild = rng.choice(wild_cands)
            wild["was_selected"] = True
            wild["was_wild_card"] = True
            wild["selection_weight"] = 0.0
            selected.append(wild)
    return selected

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(x*x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
