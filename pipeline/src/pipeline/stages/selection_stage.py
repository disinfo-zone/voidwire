"""Stochastic signal selection stage."""

from __future__ import annotations

import logging
import math
import random

from voidwire.services.pipeline_settings import SelectionSettings

logger = logging.getLogger(__name__)


async def run_selection_stage(
    signals: list[dict],
    seed: int,
    settings: SelectionSettings | None = None,
) -> list[dict]:
    if not signals:
        return []
    s = settings or SelectionSettings()
    n_select = s.n_select
    n_wild = s.n_wild
    intensity_scores = s.intensity_scores
    wild_card_excluded = set(s.wild_card_excluded_domains)
    diversity_bonus = s.diversity_bonus
    quality_floor = s.quality_floor
    min_text_length = s.min_text_length

    rng = random.Random(seed)
    major = [sig for sig in signals if sig.get("intensity") == "major"]
    non_major = [sig for sig in signals if sig.get("intensity") != "major"]
    selected = list(major)
    for sig in selected:
        sig["was_selected"] = True
        sig["selection_weight"] = 1.0
    remaining = max(0, n_select - len(selected) - n_wild)
    if remaining > 0 and non_major:
        domain_counts: dict[str, int] = {}
        for sig in selected:
            d = sig.get("domain", "")
            domain_counts[d] = domain_counts.get(d, 0) + 1
        weighted = []
        for sig in non_major:
            w = intensity_scores.get(sig.get("intensity", "minor"), 1.0) * sig.get("weight", 0.5)
            if domain_counts.get(sig.get("domain", ""), 0) == 0:
                w *= diversity_bonus
            weighted.append((sig, w))
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
            domain_counts[chosen.get("domain", "")] = (
                domain_counts.get(chosen.get("domain", ""), 0) + 1
            )
    # Wild card: select signal with maximum cosine distance from major centroid
    if n_wild > 0 and non_major:
        wild_cands = [sig for sig in non_major if not sig.get("was_selected")]
        # Quality floor: moderate+ intensity or source weight >= quality_floor
        wild_cands = [
            sig
            for sig in wild_cands
            if sig.get("intensity") in ("major", "moderate")
            or sig.get("weight", 0) >= quality_floor
        ]
        # Domain exclusion
        wild_cands = [sig for sig in wild_cands if sig.get("domain") not in wild_card_excluded]
        # Minimum text length check
        wild_cands = [sig for sig in wild_cands if len(sig.get("summary", "")) >= min_text_length]
        if wild_cands:
            wild = _select_wild_card_by_distance(wild_cands, major, rng)
            wild["was_selected"] = True
            wild["was_wild_card"] = True
            wild["selection_weight"] = 0.0
            selected.append(wild)
    return selected


def _select_wild_card_by_distance(
    candidates: list[dict], majors: list[dict], rng: random.Random
) -> dict:
    """Select wild card as signal most distant from major centroid."""
    major_embeddings = [m.get("embedding") for m in majors if m.get("embedding")]
    if not major_embeddings:
        return rng.choice(candidates)
    # Compute centroid of major signals
    dim = len(major_embeddings[0])
    centroid = [0.0] * dim
    for emb in major_embeddings:
        for i in range(dim):
            centroid[i] += emb[i]
    n = len(major_embeddings)
    centroid = [c / n for c in centroid]
    # Find candidate with maximum distance (minimum similarity) from centroid
    best_candidate = None
    max_distance = -1.0
    for cand in candidates:
        emb = cand.get("embedding")
        if not emb:
            continue
        sim = _cosine_similarity(emb, centroid)
        distance = 1.0 - sim
        cand["_wild_card_distance"] = round(distance, 4)
        if distance > max_distance:
            max_distance = distance
            best_candidate = cand
    if best_candidate is None:
        return rng.choice(candidates)
    return best_candidate


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)
