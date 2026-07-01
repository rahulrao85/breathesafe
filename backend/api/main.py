"""
BreatheSafe — FastAPI Backend
==============================
Single Cloud Run container serving:
  - REST API for district/state data + agent
  - Static frontend SPA

Local mode: reads from processed CSVs (no BigQuery credentials needed).
Production mode: query BigQuery when GOOGLE_APPLICATION_CREDENTIALS is set
and BQ_PROJECT_ID is configured.
"""

from __future__ import annotations
import os
import csv
import io
import json
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Query

# Load .env before anything else so GCP_PROJECT_ID / GCP_REGION are
# available at import time (Vertex AI SDK reads them in tools.py / agent.py)
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")
logger = logging.getLogger("breathesafe")
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Local imports
import sys
BACKEND_DIR = Path(__file__).parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend.agent.agent import ask as agent_ask
from backend.agent.tools import analyze_image
from backend.agent.geo import resolve_to_district, find_nearest_districts

# ============================================================================
# Setup
# ============================================================================
BASE_DIR = Path(__file__).parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app = FastAPI(
    title="BreatheSafe API",
    description="District-level sleep apnea awareness intelligence for India",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Data loaders
# ============================================================================
def _load_districts():
    rows = []
    with open(PROCESSED_DIR / "district_risk_scores.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def _load_states():
    rows = []
    with open(PROCESSED_DIR / "state_summary.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def _coerce(row: dict) -> dict:
    """Convert numeric strings to float/int for JSON serialization."""
    out = {}
    for k, v in row.items():
        if v in (None, ""):
            out[k] = None
            continue
        if k in ("total_population", "estimated_undiagnosed"):
            try:
                out[k] = int(v)
            except (ValueError, TypeError):
                out[k] = None
        elif k in ("risk_score", "awareness_gap_score", "awareness_normalized",
                   "pct_adults_overweight_obese", "pct_adults_hypertension",
                   "pct_age_50_plus", "pct_male", "pct_urban", "latitude",
                   "longitude", "pm25_annual_mean", "sleep_apnea_interest",
                   "snoring_interest", "cpap_interest"):
            try:
                out[k] = float(v)
            except (ValueError, TypeError):
                out[k] = None
        elif k == "is_awareness_desert":
            out[k] = (v == "True")
        else:
            out[k] = v
    return out


# ============================================================================
# Endpoints
# ============================================================================
@app.get("/health")
def health():
    return {"status": "ok", "service": "breathesafe"}


@app.get("/api/summary")
def summary():
    """National-level KPIs."""
    districts = _load_districts()
    states = _load_states()
    districts = [_coerce(r) for r in districts]
    high = [d for d in districts if d["risk_category"] == "HIGH"]
    deserts = [d for d in districts if d["is_awareness_desert"]]

    if deserts:
        top = deserts[0]
        top_desert = {
            "district": top["district_name"],
            "state": top["state_name"],
            "risk_score": top["risk_score"],
            "awareness_gap": top["awareness_gap_score"],
            "estimated_undiagnosed": top["estimated_undiagnosed"],
        }
    else:
        top_desert = None

    return {
        "districts_analyzed": len(districts),
        "high_risk_count": len(high),
        "awareness_desert_count": len(deserts),
        "top_awareness_desert": top_desert,
        "avg_risk_score": round(
            sum(d["risk_score"] for d in districts) / max(len(districts), 1), 3
        ),
        "states_analyzed": len(states),
        "data_sources": ["NFHS-5", "Census 2011 (calibrated synthetic)", "CPCB/OpenAQ-style AQI", "Google Trends awareness"],
    }


@app.get("/api/districts")
def districts(
    state: Optional[str] = Query(None, description="Filter by state name"),
    risk_category: Optional[str] = Query(None, description="HIGH / MODERATE / LOW"),
    awareness_desert: Optional[bool] = Query(None),
    sort_by: str = Query("awareness_gap_score"),
    limit: int = Query(100, ge=1, le=500),
):
    rows = _load_districts()

    if state:
        s = state.strip().lower()
        rows = [r for r in rows if r["state_name"].lower() == s]
    if risk_category:
        c = risk_category.strip().upper()
        rows = [r for r in rows if r["risk_category"] == c]
    if awareness_desert is not None:
        rows = [r for r in rows if r["is_awareness_desert"] == ("True" if awareness_desert else "False")]

    numeric_sort = sort_by in (
        "risk_score", "awareness_gap_score", "estimated_undiagnosed",
        "pct_adults_overweight_obese", "pct_adults_hypertension",
        "pm25_annual_mean", "total_population",
    )
    if numeric_sort:
        rows.sort(key=lambda r: float(r.get(sort_by) or 0), reverse=True)

    rows = rows[:limit]
    return {
        "count": len(rows),
        "rows": [_coerce(r) for r in rows],
        "filters": {"state": state, "risk_category": risk_category,
                    "awareness_desert": awareness_desert, "sort_by": sort_by, "limit": limit},
    }


@app.get("/api/states")
def states():
    rows = _load_states()
    return {"count": len(rows), "rows": [_coerce(r) for r in rows]}


@app.get("/api/district/{state}/{district}")
def district_detail(state: str, district: str):
    rows = _load_districts()
    s = state.strip().lower()
    d = district.strip().lower()
    for r in rows:
        if r["state_name"].lower() == s and r["district_name"].lower() == d:
            return _coerce(r)
    raise HTTPException(404, f"District '{district}' not found in '{state}'")


@app.post("/api/ask")
async def ask(payload: dict):
    """Agent chat endpoint."""
    question = (payload or {}).get("question", "").strip()
    if not question:
        raise HTTPException(400, "Missing 'question' in body")
    result = agent_ask(question)
    # Strip tool_results from response payload (could be large)
    return {
        "question": result["question"],
        "answer": result["answer"],
        "tools_called": result["tools_called"],
        "tool_results_count": result["tool_results_count"],
    }


@app.post("/api/analyze-image")
async def analyze_image_endpoint(file: UploadFile = File(...)):
    """Multimodal: extract location + topic from an uploaded image."""
    # Hard 8 MB cap to keep Vertex AI Vision calls fast and bounded
    MAX_BYTES = 8 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Image too large ({len(contents)} bytes). Max {MAX_BYTES} bytes.",
        )
    result = analyze_image(contents, filename=file.filename or "uploaded.jpg")
    extracted = result.get("extracted") or {}
    extracted_location = extracted.get("location_name", "")

    # 360-degree cross-reference: town → district, plus nearest-geo fallback
    matches: list[dict] = []
    resolution_note = None
    if extracted_location:
        matches = resolve_to_district(extracted_location)
        if matches:
            top = matches[0]
            if top["match_type"] == "exact_town":
                resolution_note = (
                    f"'{extracted_location}' resolved to {top['district_name']} "
                    f"district via town lookup"
                )
            elif top["match_type"] == "alias_town":
                resolution_note = (
                    f"'{extracted_location}' fuzzy-matched to {top['via_town']} → "
                    f"{top['district_name']} district"
                )
            elif top["match_type"] == "district_name":
                resolution_note = f"'{extracted_location}' matched directly as a district"
            elif top["match_type"] == "state_name":
                resolution_note = (
                    f"'{extracted_location}' matched as a state; returning the "
                    f"highest-risk district in it"
                )
        else:
            resolution_note = (
                f"'{extracted_location}' not in our town/district/state index; "
                "no exact match"
            )

    # If still no match, try a coordinate-based nearest fallback when
    # the prompt gave us lat/lon (Vertex AI Vision doesn't, but this is
    # a hook for when we wire that in)
    if not matches:
        lat = extracted.get("latitude")
        lon = extracted.get("longitude")
        if lat is not None and lon is not None:
            try:
                geo_matches = find_nearest_districts(float(lat), float(lon))
                if geo_matches:
                    matches = geo_matches
                    resolution_note = (
                        f"No name match for '{extracted_location}'; returning the "
                        f"nearest districts by coordinate"
                    )
            except (ValueError, TypeError):
                pass

    # Backwards-compat: keep `cross_reference` as the top single match
    cross_ref = None
    if matches:
        m = matches[0]
        cross_ref = {
            "matched_district": m["district_name"],
            "matched_state": m["state_name"],
            "match_type": m["match_type"],
            "via_town": m.get("via_town"),
            "distance_km": m.get("distance_km"),
            "confidence": m.get("confidence"),
            "risk_score": m.get("risk_score"),
            "risk_category": m.get("risk_category"),
            "awareness_gap": m.get("awareness_gap_score"),
            "pm25_annual_mean": m.get("pm25_annual_mean"),
            "estimated_undiagnosed": m.get("estimated_undiagnosed"),
        }

    return {
        "extracted": extracted,
        "source": result.get("source"),
        "cross_reference": cross_ref,
        "matches": matches,  # all top-5 candidates; UI shows a list
        "resolution_note": resolution_note,
        "note": result.get("note"),
    }


# ============================================================================
# Static frontend
# ============================================================================
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    @app.get("/")
    def root():
        index = FRONTEND_DIR / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return JSONResponse({"message": "BreatheSafe API", "docs": "/docs"})


# ============================================================================
# Main (for local dev)
# ============================================================================
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
