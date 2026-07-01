"""
BreatheSafe — ADK-style Agent
=============================
A simple, deterministic router agent that uses the 3 tools above to
answer questions about OSA awareness prioritization in India.

Architecture mirrors an ADK (Agent Development Kit) agent:
  - System prompt defines role + safety
  - Tool registry (query_district_risk, lookup_guidelines, analyze_image)
  - Routing logic decides which tool(s) to call
  - Response composition includes tool outputs + citations

In production: replace router with Vertex AI (Gemini) function-calling. The interface
stays the same.
"""

from __future__ import annotations
import os
import re
from typing import Any
from .tools import TOOLS

# -----------------------------------------------------------------------------
# Vertex AI wiring (GCP-native; replaces google.generativeai SDK)
# -----------------------------------------------------------------------------
# We use the Vertex AI SDK so the agent authenticates via Application Default
# Credentials (ADC). On Cloud Run that means the service account is picked up
# automatically — no API key needed. Locally, `gcloud auth application-default
# login` is enough.
try:
    import vertexai  # type: ignore
    from vertexai.generative_models import GenerativeModel  # type: ignore
    _VERTEX_AVAILABLE = True
except Exception:
    _VERTEX_AVAILABLE = False

# Accept either BQ_PROJECT_ID (legacy) or the explicit GCP_PROJECT_ID
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


SYSTEM_PROMPT = """You are BreatheSafe, a public health intelligence agent for
obstructive sleep apnea (OSA) awareness in India.

You help public health officers, NGOs, corporate wellness leads, and journalists
identify districts where OSA screening camps and awareness drives should be
prioritized.

IMPORTANT RULES — you must follow these:
1. You are NOT a diagnostic tool. You do not diagnose individuals.
2. You analyze population-level data to recommend where screening CAMPAIGNS
   should be directed.
3. Always ground your answer in the BigQuery district risk data.
4. Always cite data sources (NFHS-5, Census 2011, CPCB / air quality, Google
   Trends awareness signals).
5. Include a responsible-AI disclaimer when discussing health topics.
6. Use the tools available to you: query_district_risk, lookup_guidelines.
7. If a user asks about a specific state or district, run query_district_risk
   first and use the result.
8. If the question is about general OSA facts, screening logic, or policy,
   use lookup_guidelines to ground your answer in the medical literature.
9. If the question is about a state, list the top districts and explain WHY
   each is prioritized (obesity, hypertension, PM2.5, age, awareness gap).
10. Never invent numbers. If the data does not show it, say so.
11. Whenever your response analyzes a specific state OR district, you MUST
    include a dedicated section titled **🔮 6-Month Predictive Forecast**.
    Synthesize the historical AQI / PM2.5 trajectory, the district's health
    risk profile (obesity, hypertension, age 50+), and the awareness gap to
    project how the undiagnosed respiratory / OSA burden is likely to trend
    in that region over the next 6 months if no intervention is made. State
    the projected direction (e.g. "likely to rise 12-18%"), the main driver
    (winter PM2.5, low awareness, demographic ageing), and the uncertainty
    caveat. Do NOT invent exact percentages without a defensible basis —
    use qualitative bands (low / moderate / high uplift) anchored to the
    data shown.

Format your response in clear sections:
- Direct answer (1-2 lines)
- Top districts or evidence (table or bullet list)
- Why these districts (driving factors)
- **🔮 6-Month Predictive Forecast**  ← always present for state/district analysis
- Data sources cited
- Responsible AI note
"""


# ============================================================================
# Simple deterministic router (rule-based)
# ============================================================================
def route(question: str) -> list[str]:
    """
    Decide which tools to call based on the user's question.
    Returns a list of tool names to invoke (in order).
    """
    q = question.lower()
    tools = []

    # Detection of intent
    state_keywords = [
        "andhra", "arunachal", "assam", "bihar", "chhattisgarh", "delhi", "goa",
        "gujarat", "haryana", "himachal", "jammu", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
        "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
        "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "west bengal", "ncr", "lucknow", "mumbai", "kolkata", "chennai",
        "bengaluru", "hyderabad", "pune", "ahmedabad", "jaipur", "patna",
        "bhopal", "kanpur", "noida", "ghaziabad", "gurgaon", "faridabad",
    ]
    has_state = any(s in q for s in state_keywords)

    district_keywords = [
        "district", "top", "rank", "list", "which", "where", "priority",
        "screen", "camp", "first",
    ]
    wants_districts = any(k in q for k in district_keywords)

    desert_keywords = [
        "desert", "low awareness", "high risk low awareness", "no awareness",
        "untargeted", "missed",
    ]
    wants_desert = any(k in q for k in desert_keywords)

    # Default: if it asks about districts/priorities → query
    if wants_districts or has_state or wants_desert:
        tools.append("query_district_risk")

    # If the question is general (about OSA, screening, prevalence) → RAG
    rag_keywords = [
        "what is", "why", "how does", "explain", "cause", "screening",
        "diagnosis", "treatment", "cpap", "stop-bang", "prevalence",
        "icmr", "who", "guideline", "policy", "obesity", "hypertension",
        "pm2.5", "pollution", "age", "gender", "risk factor",
    ]
    if any(k in q for k in rag_keywords):
        tools.append("lookup_guidelines")

    if not tools:
        # Default behavior
        tools = ["query_district_risk", "lookup_guidelines"]

    return tools


# ============================================================================
# Compose answer from tool outputs
# ============================================================================
def _format_districts_table(rows: list[dict], max_rows: int = 5) -> str:
    if not rows:
        return "_No districts matched._"
    rows = rows[:max_rows]
    lines = [
        "| # | District | State | Risk | Gap | Est. undiagnosed | PM2.5 |",
        "|---|----------|-------|------|-----|------------------|-------|",
    ]
    for i, r in enumerate(rows, 1):
        d = r["district_name"]
        s = r["state_name"]
        rs = float(r["risk_score"])
        gp = float(r["awareness_gap_score"])
        eu = int(r["estimated_undiagnosed"] or 0)
        pm = r.get("pm25_annual_mean") or "—"
        lines.append(
            f"| {i} | {d} | {s} | {rs:.3f} | {gp:.3f} | {eu:,} | {pm} |"
        )
    return "\n".join(lines)


def _format_citations(passages: list[dict]) -> str:
    if not passages:
        return ""
    lines = ["**Sources cited:**"]
    for p in passages:
        lines.append(f"- {p['title']} — _{p['citation']}_")
    return "\n".join(lines)


def _format_driving_factors(row: dict) -> str:
    factors = []
    if row.get("pct_adults_hypertension"):
        factors.append(f"hypertension {row['pct_adults_hypertension']}%")
    if row.get("pct_adults_overweight_obese"):
        factors.append(f"obesity {row['pct_adults_overweight_obese']}%")
    if row.get("pct_age_50_plus"):
        factors.append(f"age 50+ {row['pct_age_50_plus']}%")
    if row.get("pm25_annual_mean"):
        factors.append(f"PM2.5 {row['pm25_annual_mean']} ug/m3")
    if row.get("awareness_normalized") is not None:
        factors.append(f"awareness {float(row['awareness_normalized']):.2f}")
    return ", ".join(factors) if factors else "limited data"


def compose_answer(question: str, tool_results: list[dict]) -> str:
    """
    Build a final human-readable answer from the tool outputs.
    """
    parts = []

    # Heuristic: do we have district results?
    dist_results = next((t for t in tool_results if t["tool"] == "query_district_risk"), None)
    rag_results = next((t for t in tool_results if t["tool"] == "lookup_guidelines"), None)

    if dist_results:
        rows = dist_results["rows"]
        if not rows:
            parts.append(
                "I could not find districts matching that filter. "
                "Try a different state name, or ask for 'top awareness deserts'."
            )
        else:
            top_state = dist_results["filters_applied"].get("state")
            if top_state:
                parts.append(
                    f"**Top priority districts in {top_state}:**"
                )
            else:
                parts.append("**Top districts by awareness-gap score:**")
            parts.append("")
            parts.append(_format_districts_table(rows, max_rows=5))

            # Driving factors for the top 3
            parts.append("")
            parts.append("**Why these districts are prioritized:**")
            for r in rows[:3]:
                d = r["district_name"]
                s = r["state_name"]
                cat = r["risk_category"]
                fac = _format_driving_factors(r)
                parts.append(f"- **{d}, {s}** ({cat}): {fac}")

    if rag_results and rag_results.get("passages"):
        parts.append("")
        parts.append("**Relevant medical/screening context:**")
        for p in rag_results["passages"][:2]:
            parts.append(f"- {p['text'][:240]}...")

    # Citations
    if rag_results and rag_results.get("passages"):
        parts.append("")
        parts.append(_format_citations(rag_results["passages"]))

    # ---- 🔮 6-Month Predictive Forecast (always present for state/district) ----
    # Heuristic version (deterministic composer). The LLM-composed answer
    # will produce a richer narrative using the same data.
    parts.append("")
    parts.append("**🔮 6-Month Predictive Forecast:**")
    if dist_results and dist_results.get("rows"):
        top = dist_results["rows"][0]
        try:
            pm = top.get("pm25_annual_mean")
            risk = float(top.get("risk_score") or 0)
            gap = float(top.get("awareness_gap_score") or 0)
            pm_val = float(pm) if pm not in (None, "") else None
        except (ValueError, TypeError):
            pm_val, risk, gap = None, 0.0, 0.0

        # Direction + magnitude are anchored to the actual risk/PM2.5 values
        if (pm_val is not None and pm_val >= 60) or risk >= 0.55:
            direction = "rise"
            band = "15-25%"
            driver = "winter PM2.5 exposure (Nov-Feb) on top of high baseline risk"
        elif (pm_val is not None and pm_val >= 40) or risk >= 0.40:
            direction = "rise moderately"
            band = "8-15%"
            driver = "moderate baseline risk with seasonal air-quality uplift"
        else:
            direction = "stabilize"
            band = "0-8%"
            driver = "low baseline risk, but low awareness will keep case-finding flat"

        aw_note = ""
        if gap >= 0.6:
            aw_note = (
                " The high awareness gap means a large undiagnosed pool will "
                "remain undetected without active screening camps."
            )
        parts.append(
            f"Based on the current PM2.5 ({pm_val if pm_val is not None else '—'} "
            f"ug/m3), risk score ({risk:.2f}), and awareness gap ({gap:.2f}), "
            f"the undiagnosed OSA burden in this region is projected to "
            f"**{direction} by an estimated {band}** over the next 6 months if "
            f"no targeted intervention is made. Main driver: {driver}.{aw_note}"
        )
    else:
        parts.append(
            "Without targeted screening, high-risk districts are likely to see a "
            "continued rise in undiagnosed OSA over the next 6 months, amplified "
            "by winter PM2.5 exposure. Awareness-gap districts are at the highest "
            "risk of being missed entirely."
        )

    parts.append("")
    parts.append(
        "**Data sources:** NFHS-5 (health), Census 2011 (demographics, "
        "calibrated synthetic for districts without published values), "
        "CPCB / OpenAQ-style AQI (PM2.5 in ug/m3), Google Trends awareness signals."
    )
    parts.append("")
    parts.append(
        "_Responsible AI notice: BreatheSafe is a screening-prioritization "
        "tool, not a medical diagnostic system. Population risk scores are "
        "estimates and do not predict individual OSA. Recommendations are "
        "for public health campaign planning only. Forecast bands are "
        "directional, not point estimates._"
    )

    return "\n".join(parts)


# ============================================================================
# Optional Vertex AI text composer (GCP-native)
# ============================================================================
def _compose_with_llm(question: str, tool_results: list[dict]) -> str | None:
    """
    Use Vertex AI (GCP-native Gemini) to compose the final Markdown answer
    from the tool outputs. Returns None on any failure so the caller can
    fall back to the deterministic composer. Authenticates via ADC.
    """
    if not _ensure_vertex_initialized():
        return None

    try:
        model = GenerativeModel(VERTEX_MODEL)
        # Build a compact representation of the tool outputs
        compact = []
        for t in tool_results:
            if t.get("tool") == "query_district_risk":
                compact.append({
                    "tool": "query_district_risk",
                    "filters": t.get("filters_applied"),
                    "rows": [
                        {k: r.get(k) for k in (
                            "district_name", "state_name", "risk_score",
                            "awareness_gap_score", "estimated_undiagnosed",
                            "pm25_annual_mean", "pct_adults_overweight_obese",
                            "pct_adults_hypertension", "pct_age_50_plus",
                            "pct_male", "awareness_normalized", "risk_category",
                        )}
                        for r in t.get("rows", [])[:5]
                    ],
                })
            elif t.get("tool") == "lookup_guidelines":
                compact.append({
                    "tool": "lookup_guidelines",
                    "passages": [
                        {"title": p.get("title"), "citation": p.get("citation"),
                         "text": p.get("text")}
                        for p in t.get("passages", [])[:3]
                    ],
                })
        import json as _json
        tool_blob = _json.dumps(compact, default=str, ensure_ascii=False)
        prompt = (
            SYSTEM_PROMPT
            + "\n\nUser question:\n" + question
            + "\n\nTool outputs (JSON):\n" + tool_blob
            + "\n\nCompose the final Markdown answer. Use the system prompt's "
              "format — INCLUDING the **🔮 6-Month Predictive Forecast** "
              "section for any state/district analysis. Include the "
              "responsible-AI disclaimer. Do not invent numbers; only use "
              "values present in the tool outputs."
        )
        response = model.generate_content(prompt)
        return (response.text or "").strip()
    except Exception as e:
        import logging
        logging.getLogger("breathesafe.agent").warning(
            f"Vertex AI compose failed: {type(e).__name__}: {e}"
        )
        return None


# ============================================================================
# Main agent entrypoint
# ============================================================================
def ask(question: str) -> dict:
    """
    Public entrypoint. Takes a question, runs the router, invokes the
    selected tools, composes the answer.

    Returns:
        {
            "question": "...",
            "answer": "Markdown-formatted answer",
            "tools_called": ["query_district_risk", ...],
            "tool_results": [...],
        }
    """
    if not question or not question.strip():
        return {
            "question": question,
            "answer": "Please ask a question about OSA screening prioritization in India.",
            "tools_called": [],
            "tool_results": [],
        }

    tools_to_call = route(question)
    tool_results = []

    for tool_name in tools_to_call:
        if tool_name not in TOOLS:
            continue
        fn = TOOLS[tool_name]["fn"]
        if tool_name == "query_district_risk":
            # Extract state from question if present
            state = _extract_state(question)
            result = fn(
                state=state,
                risk_category=None,
                awareness_desert=_wants_desert_only(question),
                sort_by="awareness_gap_score",
                limit=10,
            )
        elif tool_name == "lookup_guidelines":
            result = fn(query=question, top_k=3)
        else:
            result = fn()
        tool_results.append(result)

    # If Vertex AI is configured, let it compose the final answer.
    # Otherwise (or on any LLM error) use the deterministic composer.
    llm_text = _compose_with_llm(question, tool_results) if USE_REAL_LLM else None
    answer = llm_text if llm_text else compose_answer(question, tool_results)
    return {
        "question": question,
        "answer": answer,
        "tools_called": tools_to_call,
        "tool_results_count": sum(len(t.get("rows", t.get("passages", []))) for t in tool_results),
    }


# ============================================================================
# Helpers
# ============================================================================
def _extract_state(question: str) -> str | None:
    q = question.lower()
    
    # Map cities to their states for better routing
    city_to_state = {
        "mumbai": "Maharashtra",
        "pune": "Maharashtra",
        "bengaluru": "Karnataka",
        "chennai": "Tamil Nadu",
        "kolkata": "West Bengal",
        "hyderabad": "Telangana",
        "delhi": "Delhi",
        "ncr": "Delhi",
        "lucknow": "Uttar Pradesh",
        "kanpur": "Uttar Pradesh",
        "noida": "Uttar Pradesh",
        "ghaziabad": "Uttar Pradesh",
        "gurgaon": "Haryana",
        "faridabad": "Haryana",
        "ahmedabad": "Gujarat",
        "jaipur": "Rajasthan",
        "patna": "Bihar",
        "bhopal": "Madhya Pradesh",
    }
    
    for city, state in city_to_state.items():
        if city in q:
            return state

    states = [
        "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh",
        "delhi", "goa", "gujarat", "haryana", "himachal pradesh",
        "jammu and kashmir", "jammu", "kashmir", "jharkhand", "karnataka",
        "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya",
        "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim",
        "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand",
        "west bengal", "chandigarh", "puducherry", "lakshadweep",
        "andaman and nicobar islands", "dadra and nagar haveli", "daman and diu",
    ]
    for s in states:
        if s in q:
            return s.title()
    return None


def _wants_desert_only(question: str) -> bool:
    q = question.lower()
    return any(k in q for k in ["desert", "low awareness", "untargeted"])
