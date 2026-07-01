"""
BreatheSafe — ADK-style Agent Tools
====================================
Three tools, each callable with explicit args. Used by the agent router
in agent.py. Each tool returns a structured dict the agent can format
into a final response with citations.

In a full ADK deployment, these would be wrapped with @tool decorators
and registered with the agent runtime. For the 7-day demo, we use plain
Python functions and a simple router loop.
"""

from __future__ import annotations
import csv
import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from .rag_corpus import search as rag_search, CORPUS

logger = logging.getLogger("breathesafe.tools")

PROCESSED_DIR = Path(__file__).parent.parent / "data" / "processed"

# -----------------------------------------------------------------------------
# Vertex AI wiring (GCP-native; replaces google.generativeai SDK)
# -----------------------------------------------------------------------------
# Auth is automatic on Cloud Run via the service account. Locally, set
# `gcloud auth application-default login`. If GCP_PROJECT_ID is missing or
# the SDK isn't installed, we fall back to the deterministic mock so the
# demo never breaks.
try:
    import vertexai  # type: ignore
    from vertexai.generative_models import GenerativeModel, Part  # type: ignore
    _VERTEX_AVAILABLE = True
except Exception:
    _VERTEX_AVAILABLE = False

GCP_PROJECT_ID = (
    os.environ.get("GCP_PROJECT_ID")
    or os.environ.get("BQ_PROJECT_ID", "")
).strip()
GCP_REGION = os.environ.get("GCP_REGION", "asia-south1").strip()
VERTEX_MODEL = os.environ.get("VERTEX_MODEL", "gemini-2.5-flash").strip()

USE_REAL_LLM = _VERTEX_AVAILABLE and bool(GCP_PROJECT_ID)

_vertex_initialized = False


def _ensure_vertex_initialized() -> bool:
    """Initialize Vertex AI once per process. Returns False if unavailable."""
    global _vertex_initialized
    if not USE_REAL_LLM:
        return False
    if _vertex_initialized:
        return True
    try:
        vertexai.init(project=GCP_PROJECT_ID, location=GCP_REGION)
        _vertex_initialized = True
        return True
    except Exception:
        return False


def _call_llm_vision(image_bytes: bytes, mime_type: str) -> dict | None:
    """
    Call Vertex AI (Gemini 2.5 Flash) for image extraction. Returns
    a dict on success, or a dict with '__error' on any failure so the
    caller can fall back to the mock.
    """
    if not _ensure_vertex_initialized():
        return {"__error": "vertexai not initialized (missing project / region / credentials)"}

    try:
        logger.info(
            f"Calling Vertex AI Vision with model={VERTEX_MODEL} "
            f"mime={mime_type} size={len(image_bytes)}B"
        )
        model = GenerativeModel(VERTEX_MODEL)
        prompt = (
            "You are analyzing a newspaper clipping, AQI screenshot, or "
            "public-health poster. Extract a JSON object with these "
            "exact fields:\n"
            '  "location_name": string (the MOST SPECIFIC place name visible '
            '— a town, city, district, or state. India-first. Use the most '
            'granular place mentioned, e.g. "Byrnihat", "Vapi", "Gurugram", '
            '"Lucknow", "Tamil Nadu". If nothing is identifiable, return ""),\n'
            '  "state_hint": string or null (the Indian state, if you can '
            'infer it, e.g. "Meghalaya", "Gujarat", "Uttar Pradesh"),\n'
            '  "latitude": number or null (approximate decimal degrees),\n'
            '  "longitude": number or null (approximate decimal degrees),\n'
            '  "topic": string (e.g. "air pollution", "sleep apnea", '
            '"obesity", "PM2.5", "industrial pollution"),\n'
            '  "headline_text": string (the visible headline, '
            'paraphrased),\n'
            '  "date_mentioned": string or null,\n'
            '  "key_signals": array of 2-4 short strings\n'
            "Return ONLY the JSON. No prose, no markdown fences."
        )
        # Vertex AI: pass image via Part.from_data, then the text prompt
        image_part = Part.from_data(data=image_bytes, mime_type=mime_type)
        response = model.generate_content(
            [image_part, prompt],
            generation_config={"response_mime_type": "application/json"},
        )
        text = (response.text or "").strip()
        # Strip code fences if Gemini added them
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text).strip()
        parsed = json.loads(text)
        return {
            "location_name": parsed.get("location_name", ""),
            "state_hint": parsed.get("state_hint"),
            "latitude": parsed.get("latitude"),
            "longitude": parsed.get("longitude"),
            "topic": parsed.get("topic", ""),
            "headline_text": parsed.get("headline_text", ""),
            "date_mentioned": parsed.get("date_mentioned"),
            "key_signals": parsed.get("key_signages", parsed.get("key_signals", [])),
        }
    except Exception as e:
        logger.error(f"Vertex AI Vision call failed: {type(e).__name__}: {e}", exc_info=True)
        return {"__error": f"vertex call failed: {type(e).__name__}: {e}"}


def _mock_vision_extraction(image_bytes: bytes, filename: str) -> dict:
    """
    Deterministic mock that pretends Vertex AI extracted a Delhi pollution
    newspaper image. Returns a structured dict identical in shape to
    the real call. Used when Vertex AI is not configured.
    """
    size_kb = len(image_bytes) // 1024
    return {
        "location_name": "Delhi NCR",
        "topic": "air pollution / PM2.5",
        "headline_text": (
            f"Stubble burning pushes Delhi NCR PM2.5 to 'severe' — "
            f"AQI over 400 [demo, {size_kb}KB image, {filename}]"
        ),
        "date_mentioned": "winter",
        "key_signals": [
            "PM2.5 level reported as 'severe' (>250 µg/m³)",
            "Geographic focus: Delhi, Gurgaon, Noida, Ghaziabad, Faridabad",
            "Public health advisory: avoid outdoor activity",
            "Stubble burning in Punjab/Haryana cited as primary driver",
        ],
    }


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


# ============================================================================
# TOOL 1: query_district_risk
# ============================================================================
def query_district_risk(
    state: str | None = None,
    risk_category: str | None = None,
    awareness_desert: bool | None = None,
    sort_by: str = "awareness_gap_score",
    limit: int = 20,
) -> dict:
    """
    Query the unified district risk view (the BigQuery view, served from
    the processed CSV locally).

    Returns:
        {
            "count": N,
            "rows": [{...}, ...],
            "query_summary": "Filtered 341 districts to N: state=X, category=Y",
        }
    """
    rows = _load_districts()

    # Filters
    if state:
        s = state.strip().lower()
        rows = [r for r in rows if r["state_name"].lower() == s]
    if risk_category:
        c = risk_category.strip().upper()
        rows = [r for r in rows if r["risk_category"] == c]
    if awareness_desert is not None:
        rows = [r for r in rows if r["is_awareness_desert"] == ("True" if awareness_desert else "False")]

    # Sort
    if sort_by in ("risk_score", "awareness_gap_score", "estimated_undiagnosed",
                   "pct_adults_overweight_obese", "pct_adults_hypertension",
                   "pm25_annual_mean", "total_population"):
        rows.sort(key=lambda r: float(r.get(sort_by) or 0), reverse=True)

    rows = rows[:limit]
    return {
        "tool": "query_district_risk",
        "count": len(rows),
        "rows": rows,
        "filters_applied": {
            "state": state,
            "risk_category": risk_category,
            "awareness_desert": awareness_desert,
            "sort_by": sort_by,
            "limit": limit,
        },
    }


# ============================================================================
# TOOL 2: lookup_guidelines (RAG)
# ============================================================================
def lookup_guidelines(query: str, top_k: int = 3) -> dict:
    """
    Retrieve relevant passages from the curated OSA / sleep apnea RAG corpus.
    Each passage has a citation. Returns the passages for the agent to use
    when answering, with sources surfaced.
    """
    passages = rag_search(query, top_k=top_k)
    if not passages:
        # Fall back to the most general ones
        passages = CORPUS[:top_k]
    return {
        "tool": "lookup_guidelines",
        "query": query,
        "passages": passages,
    }


# ============================================================================
# TOOL 3: analyze_image (Vertex AI Vision with deterministic mock fallback)
# ============================================================================
def analyze_image(image_bytes: bytes, filename: str = "uploaded.jpg") -> dict:
    """
    Extract location and topic from a newspaper / poster / screenshot.

    If Vertex AI is configured (GCP_PROJECT_ID set, SDK available, ADC
    reachable), calls Gemini on Vertex AI with a vision prompt and
    returns the parsed JSON. On any failure (import, auth, network,
    parse), falls back to the deterministic mock so the demo never breaks.

    If Vertex AI is not configured, returns the mock directly.
    """
    mime_type = "image/jpeg"
    fn = (filename or "").lower()
    if fn.endswith(".png"):
        mime_type = "image/png"
    elif fn.endswith(".webp"):
        mime_type = "image/webp"
    elif fn.endswith(".gif"):
        mime_type = "image/gif"

    if USE_REAL_LLM:
        logger.info(f"Vertex AI is configured, attempting real Vision call")
        result = _call_llm_vision(image_bytes, mime_type)
        if result and "__error" not in result:
            return {
                "tool": "analyze_image",
                "extracted": result,
                "source": "vertex-ai-gemini-2.5-flash",
                "note": None,
            }
        # On failure, fall through to the mock but surface the error
        fallback = _mock_vision_extraction(image_bytes, filename)
        err_detail = result.get("__error", "unknown") if result else "unknown"
        logger.warning(f"Vertex AI Vision failed ({err_detail}) — returning mock fallback")
        return {
            "tool": "analyze_image",
            "extracted": fallback,
            "source": "mock_fallback",
            "note": (
                f"Vertex AI Vision unavailable ({err_detail}); "
                "showing deterministic demo response."
            ),
        }

    # No GCP project configured — return the deterministic mock.
    logger.info("Vertex AI not configured — using deterministic mock for analyze_image")
    return {
        "tool": "analyze_image",
        "extracted": _mock_vision_extraction(image_bytes, filename),
        "source": "deterministic_mock_for_demo",
        "note": "Set GCP_PROJECT_ID + GCP_REGION to enable real Vertex AI Vision",
    }


# ============================================================================
# Tool registry
# ============================================================================
TOOLS = {
    "query_district_risk": {
        "fn": query_district_risk,
        "description": "Query the unified district risk view. Args: state, risk_category, awareness_desert, sort_by, limit",
    },
    "lookup_guidelines": {
        "fn": lookup_guidelines,
        "description": "Retrieve relevant passages from the OSA/sleep apnea RAG corpus. Args: query, top_k",
    },
    "analyze_image": {
        "fn": analyze_image,
        "description": "Extract location/topic from a news image. Args: image_bytes, filename",
    },
}
