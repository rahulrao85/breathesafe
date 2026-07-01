"""
BreatheSafe — Town/City to District Resolver
=============================================
When the multimodal Vision extraction returns a town or city name (not
a district), this module maps it to the containing district and falls
back to coordinate-based nearest-district search if no exact match.

This closes the "I don't know the answer" loop for ~500+ Indian towns
and cities, so a newspaper screenshot about "Byrnihat" or "Vapi" still
returns a useful risk impact card instead of an empty result.
"""
from __future__ import annotations
import json
import math
import re
from pathlib import Path
from typing import Optional

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"


def _load_towns() -> dict:
    with open(PROCESSED_DIR / "towns.json", encoding="utf-8") as f:
        return json.load(f)


def _load_districts() -> list[dict]:
    """Load the processed district CSV once at import time."""
    import csv
    rows = []
    with open(PROCESSED_DIR / "district_risk_scores.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                r["latitude"] = float(r.get("latitude") or 0) or None
                r["longitude"] = float(r.get("longitude") or 0) or None
            except (ValueError, TypeError):
                r["latitude"] = r["longitude"] = None
            rows.append(r)
    return rows


_TOWNS = _load_towns()
_DISTRICTS = _load_districts()


def _normalize(name: str) -> str:
    """Lowercase, strip punctuation, collapse spaces."""
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two points in km."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def resolve_to_district(location_name: str) -> list[dict]:
    """
    Given a free-text location string (town, city, district, or state),
    return a list of candidate district matches ranked by confidence.

    Each result is a dict with:
        - district_name, state_name, district_id
        - risk_score, risk_category, awareness_gap_score,
          estimated_undiagnosed, pm25_annual_mean
        - match_type: "exact_town", "alias_town", "district_name",
                      "state_name", "nearest_geo"
        - distance_km (for nearest_geo matches)
        - confidence: 0.0-1.0
        - via_town: the town that resolved to this district (if any)
    """
    norm = _normalize(location_name)
    if not norm:
        return []

    results: list[dict] = []

    # 1) Town lookup (exact, then alias)
    for state, towns in _TOWNS.items():
        if state.startswith("_"):
            continue
        for town, district in towns.items():
            if _normalize(town) == norm:
                results.extend(
                    _district_rows_matching(district, state, match_type="exact_town", via_town=town, confidence=0.95)
                )
            elif norm in _normalize(town) or _normalize(town) in norm:
                # fuzzy alias (e.g. "Bombay" inside "Bombay HC")
                if len(_normalize(town)) >= 5:  # avoid 2-letter false positives
                    results.extend(
                        _district_rows_matching(district, state, match_type="alias_town", via_town=town, confidence=0.7)
                    )

    # 2) Direct district name match
    for r in _DISTRICTS:
        if _normalize(r["district_name"]) == norm:
            results.append(
                _row_to_match(r, match_type="district_name", confidence=0.9, via_town=None)
            )

    # 3) State name match → return top HIGH/MODERATE districts in that state
    for r in _DISTRICTS:
        if _normalize(r["state_name"]) == norm:
            results.append(
                _row_to_match(r, match_type="state_name", confidence=0.6, via_town=None)
            )

    # De-duplicate by district_id, keep highest confidence
    seen: dict[str, dict] = {}
    for r in results:
        did = r.get("district_id") or f"{r['state_name']}|{r['district_name']}"
        if did not in seen or r["confidence"] > seen[did]["confidence"]:
            seen[did] = r

    deduped = list(seen.values())
    deduped.sort(key=lambda x: (x["confidence"], x.get("risk_score", 0) or 0), reverse=True)
    return deduped[:5]


def _district_rows_matching(district_name: str, state_name: str, match_type: str, via_town: str, confidence: float) -> list[dict]:
    matches = []
    for r in _DISTRICTS:
        if _normalize(r["district_name"]) == _normalize(district_name):
            # If state was specified, prefer the same-state match
            conf = confidence
            if state_name and _normalize(r["state_name"]) != _normalize(state_name):
                conf *= 0.7  # mild penalty
            matches.append(_row_to_match(r, match_type=match_type, confidence=conf, via_town=via_town))
    return matches


def _row_to_match(r: dict, match_type: str, confidence: float, via_town: Optional[str]) -> dict:
    return {
        "district_id": r.get("district_id"),
        "state_name": r.get("state_name"),
        "district_name": r.get("district_name"),
        "risk_score": _safe_float(r.get("risk_score")),
        "risk_category": r.get("risk_category"),
        "awareness_gap_score": _safe_float(r.get("awareness_gap_score")),
        "estimated_undiagnosed": _safe_int(r.get("estimated_undiagnosed")),
        "pm25_annual_mean": _safe_float(r.get("pm25_annual_mean")),
        "pct_adults_overweight_obese": _safe_float(r.get("pct_adults_overweight_obese")),
        "pct_adults_hypertension": _safe_float(r.get("pct_adults_hypertension")),
        "pct_age_50_plus": _safe_float(r.get("pct_age_50_plus")),
        "pct_male": _safe_float(r.get("pct_male")),
        "is_awareness_desert": (r.get("is_awareness_desert") == "True"),
        "match_type": match_type,
        "confidence": round(confidence, 2),
        "via_town": via_town,
    }


def find_nearest_districts(lat: float, lon: float, limit: int = 3, max_km: float = 150) -> list[dict]:
    """Find the closest districts to a lat/lon, within max_km."""
    if lat is None or lon is None:
        return []
    candidates = []
    for r in _DISTRICTS:
        d_km = _haversine_km(lat, lon, r.get("latitude"), r.get("longitude"))
        if d_km <= max_km:
            candidates.append((d_km, r))
    candidates.sort(key=lambda x: x[0])
    return [
        {**_row_to_match(r, match_type="nearest_geo", confidence=max(0.3, 0.8 - d_km / 200), via_town=None),
         "distance_km": round(d_km, 1)}
        for d_km, r in candidates[:limit]
    ]


def _safe_float(v) -> Optional[float]:
    if v in (None, ""):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _safe_int(v) -> Optional[int]:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
