# BreatheSafe — Final Unified Handoff for OpenCode

**Project:** BreatheSafe  
**Hackathon:** Google Cloud Gen AI Academy APAC 2026 — Cohort 2  
**Theme:** "Unified Data Analytics & Intelligence"  
**Owner:** Rahul Rao  
**Date:** 29 Jun 2026  
**Decision:** BreatheSafe is LOCKED. PulseCare is DEAD. Do not build anything that looks like Sleep IQ.

---

## What This Document Is

Two agents brainstormed and scaffolded BreatheSafe independently:
- **Antigravity** — ideation, data research, data acquisition scripts, BigQuery schema + risk scoring SQL, STOP-BANG model, raw data downloads
- **Codex** — cleaned PRD, sharpened product direction, wrote the build handoff with API spec, UI layout, and 7-day plan

This document merges both into **one final spec** for OpenCode to execute. If anything conflicts, this document wins.

---

## The Idea (30 seconds)

India has ~100M+ undiagnosed obstructive sleep apnea cases. BreatheSafe is **not** a personal tracker. It is a **district-level public health intelligence platform** that joins 5 public datasets in BigQuery to answer:

> *"Where in India should we send sleep apnea screening camps first?"*

It finds **"awareness deserts"** — districts where estimated OSA risk is high but public awareness (Google Trends) is near zero.

---

## What Is Already Built

Everything lives in `F:\AGENTIC WORLD\GEN AI APEC Cohort 2\breathesafe\`

### Files ready to use

| File | What it is | Status |
|------|-----------|--------|
| `docs/PRD.md` | Locked product spec | ✅ Final |
| `docs/OPENCODE_HANDOFF.md` | Codex's build instructions | ✅ Final |
| `backend/bq/schema.sql` | BigQuery schema: 5 tables + `district_risk_scores` view + `state_summary` view | ✅ Ready to deploy |
| `backend/data/raw/nfhs5_districts.csv` | **Real** NFHS-5 district health data — 341 districts, 21 states, 104 indicators | ✅ 4.1 MB |
| `backend/data/raw/nfhs5_india_full.csv` | Full India NFHS dataset (wider, 10.8 MB) | ✅ Backup |
| `backend/data/raw/air_quality_districts.csv` | Synthetic AQI calibrated to real CPCB patterns — 50 districts | ✅ Ready |
| `backend/data/raw/trends_awareness.csv` | Synthetic Google Trends by state (36 states/UTs), calibrated to metro vs rural patterns | ✅ Ready |
| `backend/data/raw/stopbang_model.json` | STOP-BANG population risk model weights with citations | ✅ Ready |
| `scripts/fetch_data.py` | Data acquisition script (can re-run with `--all` or per-source flags) | ✅ Working |

### Folders created but empty (for OpenCode to fill)

| Folder | Purpose |
|--------|---------|
| `backend/agent/` | ADK agent code |
| `backend/api/` | FastAPI app |
| `backend/data/processed/` | Cleaned/pivoted data ready for BQ load |
| `frontend/static/css/` | Styles |
| `frontend/static/js/` | Client JS |

---

## Critical Data Details for OpenCode

### NFHS-5 CSV Structure (the tricky part)

The `nfhs5_districts.csv` is **long-format** (one row per indicator per district), not wide. Columns:

```
State, State-Code, District, Indicator, NFHS-5, NFHS-4, NFHS-5-note, NFHS-4-note
```

**OpenCode must pivot** this into wide format. The indicators needed for the risk model are:

| Indicator text in CSV | What it maps to | BQ column |
|----------------------|-----------------|-----------|
| `79. Women who are overweight or obese (BMI ≥25.0 kg/m2)21 (%)` | Obesity proxy (women) | `pct_women_overweight_obese` |
| `80. Men who are overweight or obese (BMI ≥25.0 kg/m2)21 (%)` | Obesity proxy (men) | `pct_men_overweight_obese` |
| `94. Elevated blood pressure (Systolic ≥140 mm of Hg and/or Diastolic ≥90 mm of Hg)...` | Hypertension (women) | `pct_women_hypertension` |
| `97. Elevated blood pressure (Systolic ≥140 mm of Hg and/or Diastolic ≥90 mm of Hg)...` | Hypertension (men) | `pct_men_hypertension` |
| `88. Blood sugar level - high or very high...` | Diabetes comorbidity (women) | `pct_women_high_blood_sugar` |
| `91. Blood sugar level - high or very high...` | Diabetes comorbidity (men) | `pct_men_high_blood_sugar` |
| `101. Women age 15 years and above who use any kind of tobacco (%)` | Tobacco (women) | `pct_tobacco_use_women` |
| `102. Men age 15 years and above who use any kind of tobacco (%)` | Tobacco (men) | `pct_tobacco_use_men` |

> [!IMPORTANT]
> Indicators 92-94 are women's blood pressure. Indicators 95-97 are men's blood pressure. The numbering repeats for men/women — be careful during pivot.

**Coverage:** 341 districts across 21 states. Not all-India (NFHS-5 was released in phases). This is fine for the demo — document it.

### Census Data — Not Downloaded

Census 2011 district CSV was not successfully downloaded (GitHub 404). OpenCode has two options:

1. **Download from Kaggle:** `india-census-2011` dataset → `india-districts-census-2011.csv` (has population, male/female, literacy, urbanization)
2. **Generate synthetic from NFHS district list:** Use the 341 NFHS districts as the district spine and add Census-derived columns from known state averages

**Recommendation:** Use option 1 (Kaggle CSV) if possible. If not, generate a 341-row synthetic demographics table with realistic population, age 50+%, male%, urban% values calibrated to known state-level Census data.

### Data Join Strategy

```
health_survey.district + health_survey.state
  → demographics.district + demographics.state     (exact match)
  → air_quality.district + air_quality.state        (fuzzy — only 50 districts have AQI)
  → awareness_signals.state                         (state-level only, LEFT JOIN)
```

**Key decision:** Use LEFT JOINs everywhere. Districts without AQI data get NULL pm25 (treated as 0 in risk scoring). Districts without Census match get NULL age/gender (treated as 0). This is defensible — we document the coverage and acknowledge gaps.

---

## Risk Scoring Model (Final)

```sql
risk_score = 
    0.25 × hypertension_normalized +    -- NFHS-5
    0.25 × obesity_normalized +          -- NFHS-5
    0.15 × age_50plus_normalized +       -- Census
    0.10 × male_pct_normalized +         -- Census
    0.25 × pm25_normalized              -- AQI

awareness_gap = risk_score × (1 - awareness_normalized)
```

Where `awareness_normalized` = `(0.5 × sleep_apnea_interest + 0.3 × snoring_interest + 0.2 × cpap_interest) / 100`

**Awareness deserts** = `risk_score > 0.5 AND awareness_normalized < 0.3`

**Estimated undiagnosed** = `population × 0.096 × (1 - awareness_normalized)` (using India's ~9.6% OSA prevalence from Sharma et al., Lancet Respiratory Medicine)

All normalization is min-max across available districts (0-1 scale). Full SQL is in `backend/bq/schema.sql`.

---

## API Spec

FastAPI on Cloud Run. Single container.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Serve the SPA frontend |
| `/api/summary` | GET | National-level KPIs: total districts, high-risk count, top awareness desert, avg risk |
| `/api/districts` | GET | Paginated district list with risk scores. Query params: `?state=`, `?risk_category=`, `?limit=`, `?sort_by=` |
| `/api/states` | GET | State-level summary (from `state_summary` view) |
| `/api/ask` | POST | Agent chat. Body: `{"question": "..."}`. Returns Vertex AI (Gemini 2.5 Flash) response with BQ-grounded reasoning |
| `/api/analyze-image` | POST | Multimodal. Body: multipart with image file. Vertex AI Vision extracts location → agent looks up district risk |
| `/health` | GET | Cloud Run health check |

**Local fallback:** If BigQuery credentials aren't available during dev, the `/api/districts` and `/api/summary` endpoints should fall back to reading the processed CSV directly. The agent endpoints need Vertex AI auth (ADC) or fall back to the deterministic composer.

---

## ADK Agent Design

3 tools minimum:

### Tool 1: `query_district_risk`
- Runs parameterized SQL against `breathesafe.district_risk_scores`
- Accepts: state filter, risk category filter, top-N limit
- Returns: structured district rows with risk scores and reasoning columns

### Tool 2: `lookup_guidelines`
- RAG over a small curated corpus (not full Vector Search — too risky for 7 days)
- Corpus: 5-10 key passages from WHO/ICMR/AASM on OSA screening, STOP-BANG validation, air pollution + OSA link
- Implementation: Embed passages in a JSON file, use Vertex AI text embeddings for similarity, or just include as system prompt context
- Must cite source in response

### Tool 3: `analyze_image`
- Accepts image bytes
- Vertex AI Vision extracts: location name, environmental issue, any health-relevant signal
- Returns: extracted context for the agent to cross-reference with BQ data

**System prompt guidance:**
```
You are BreatheSafe, a public health intelligence agent for sleep apnea awareness in India.
You help public health officers, NGOs, and wellness leaders identify districts where 
obstructive sleep apnea screening should be prioritized.

IMPORTANT: You are NOT a diagnostic tool. You do not diagnose individuals. You analyze 
population-level data to recommend where screening campaigns should be directed.

When answering, always:
1. Ground your response in the BigQuery district risk data
2. Explain which factors (obesity, hypertension, PM2.5, age, awareness) drive the risk
3. Include a responsible AI disclaimer when discussing health topics
4. Cite data sources (NFHS-5, Census 2011, CPCB, Google Trends)
```

---

## UI Layout

Single-page app. Sections top to bottom:

```
┌─────────────────────────────────────────────────────┐
│  🫁 BreatheSafe                    [Disclaimer]     │
│  "India's Sleep Apnea Awareness Intelligence"       │
├─────────────────────────────────────────────────────┤
│  ┌──────┐ ┌──────┐ ┌──────────┐ ┌───────────────┐  │
│  │ 341  │ │  XX  │ │ Top:     │ │ Avg Risk:     │  │
│  │Dists │ │ High │ │ [name]   │ │  0.XX         │  │
│  │Scored│ │ Risk │ │ Desert   │ │               │  │
│  └──────┘ └──────┘ └──────────┘ └───────────────┘  │
├─────────────────────────────────────────────────────┤
│  [State Filter ▾]  [Risk Category ▾]  [Search]      │
│                                                     │
│  District Risk Table                                │
│  ┌─────────┬──────┬──────┬─────┬──────┬──────────┐  │
│  │District │State │Risk  │PM2.5│Aware │Gap Score  │  │
│  │         │      │Score │     │      │           │  │
│  ├─────────┼──────┼──────┼─────┼──────┼──────────┤  │
│  │ ...     │ ...  │ ...  │ ... │ ...  │ ...       │  │
│  └─────────┴──────┴──────┴─────┴──────┴──────────┘  │
├─────────────────────────────────────────────────────┤
│  🤖 Ask BreatheSafe                                 │
│  ┌─────────────────────────────────────────────┐    │
│  │ [Text input]                          [Ask] │    │
│  └─────────────────────────────────────────────┘    │
│  Quick prompts:                                     │
│  [Top 5 UP districts] [Why Delhi NCR?]              │
│  [Awareness deserts]  [Draft awareness message]     │
│                                                     │
│  Agent Response Card                                │
│  ┌─────────────────────────────────────────────┐    │
│  │ Vertex AI (Gemini) response with data citations │    │
│  └─────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────┤
│  📷 Multimodal: Upload News Image                   │
│  [Drop image here]  →  [Risk Impact Card]           │
├─────────────────────────────────────────────────────┤
│  📊 Looker Dashboard  [Open ↗] or [iframe]          │
├─────────────────────────────────────────────────────┤
│  ⚕️ Responsible AI Disclaimer                       │
│  "BreatheSafe is a screening prioritization tool,   │
│   not a medical diagnostic system..."               │
└─────────────────────────────────────────────────────┘
```

**Design tone:** Public health / civic intelligence. Clean, dark background, data-dense. NOT a hospital app. NOT Sleep IQ colors. Think government data portal meets modern dashboard.

---

## Fixed Demo Prompts (wire these as buttons)

1. `Which 5 districts in Uttar Pradesh should get sleep apnea screening camps first?`
2. `Why is Delhi NCR a high priority for BreatheSafe?`
3. `Show me the top awareness deserts across India.`
4. `Draft a 100-word public awareness message for the highest-risk district.`

---

## Multimodal Demo Flow

1. User uploads a **newspaper screenshot** about Delhi air pollution
2. Vertex AI Vision extracts: location = "Delhi / NCR", topic = "air pollution / PM2.5"
3. Agent queries BQ: `SELECT * FROM district_risk_scores WHERE state = 'Delhi' ORDER BY awareness_gap_score DESC`
4. UI shows a **risk impact card**: "Delhi NCR districts have PM2.5 of 120-180 µg/m³. Combined with 25%+ obesity and 18%+ hypertension, the OSA risk score is 0.72 (HIGH). Awareness is at 0.38 — below the national metro average. Recommended: prioritize Ghaziabad and Noida for screening."

**Fallback:** If Vision isn't working, preload a demo image and return a cached response. Ship the UI path regardless.

---

## 7-Day Build Plan

| Day | Deliverable | Owner |
|-----|------------|-------|
| **Day 1 (done)** | Idea locked, data downloaded, BQ schema written, PRD locked | Antigravity + Codex |
| **Day 2** | Pivot NFHS CSV to wide format. Load all 5 tables into BigQuery. Validate `district_risk_scores` view returns ranked data. | OpenCode |
| **Day 3** | FastAPI backend: `/api/summary`, `/api/districts`, `/api/states`. Local CSV fallback. Serve static frontend. | OpenCode |
| **Day 4** | Frontend SPA: KPI strip, district table, filters, agent chat UI with prompt buttons. | OpenCode |
| **Day 5** | Vertex AI + ADK: wire `/api/ask` with BQ tool + guidelines tool. Wire `/api/analyze-image` with Vision. | OpenCode |
| **Day 6** | Looker Studio dashboard (choropleth + table). Dockerfile + Cloud Run deploy. Fill 10-slide deck. | OpenCode |
| **Day 7** | Record 2-min demo video. Polish. Submit. | Rahul |

---

## Demo Video Script (2 min)

| Time | Scene |
|------|-------|
| 0:00–0:15 | *"I have sleep apnea. I got diagnosed because I had access. 100 million Indians haven't been."* |
| 0:15–0:35 | Show Looker heatmap. Zoom into UP and Maharashtra. *"Red = high risk + low awareness."* |
| 0:35–1:00 | Click "Top 5 UP districts" button. Agent returns ranked list with BQ-backed reasoning. |
| 1:00–1:25 | Upload newspaper photo. Vertex AI Vision reads it → NCR risk card appears. |
| 1:25–1:45 | Show architecture slide: Cloud Storage → BigQuery → Vertex AI + ADK → Cloud Run + Looker. |
| 1:45–2:00 | *"5 public datasets. One warehouse. One question: where should India screen first? BreatheSafe."* |

---

## What NOT to Build

- ❌ Wearable data ingestion
- ❌ CPAP data analysis  
- ❌ Personal "your sleep score" features
- ❌ Individual medical diagnosis
- ❌ Login / auth
- ❌ Mobile app
- ❌ Full Vertex AI Vector Search setup (use simple RAG fallback)
- ❌ Anything that looks like Sleep IQ with a different name

---

## Submission Narrative

> *I live with sleep apnea. But this project is not about my device data. It is about the millions of Indians who may never get screened because the system doesn't know where awareness is missing. BreatheSafe joins public health, demographic, air quality, and awareness signals in BigQuery, then uses Vertex AI (Gemini) and ADK to help public health teams find their highest-impact screening locations.*

---

> [!TIP]
> **For OpenCode:** The hardest part is Day 2 — pivoting the NFHS CSV and getting the BQ view to return clean results. If that works, everything downstream (API, UI, agent) is mechanical. If the Census download fails, generate synthetic demographics for the 341 NFHS districts using known state averages. A clean 341-district demo beats a broken 766-district attempt.
