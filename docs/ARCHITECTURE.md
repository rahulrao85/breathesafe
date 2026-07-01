# BreatheSafe — Architecture (long form)

> Companion to the README diagram. Read this if you want the
> decision-level details: data contracts, agent contract, deploy
> contract.

---

## 1. Data flow

```
  +-----------------+        +-----------------+        +-------------------+
  |  Source CSVs    |        |  Cloud Storage  |        |  BigQuery         |
  |  (NFHS-5, AQI,  | -----> |  gs://breath... | -----> |  breathesafe.*    |
  |   Trends, ...)  |        |   /raw/*.csv    |        |  5 tables + 1 view|
  +-----------------+        +-----------------+        +---------+---------+
                                                                     |
                                                                     v
                                              +--------------------------------+
                                              |  district_risk_scores (VIEW)   |
                                              |  365 districts x 22 columns    |
                                              +-------------+------------------+
                                                            |
        +---------------------------------------------------+-------------------------+
        |                                                     |                       |
        v                                                     v                       v
+----------------+                              +----------------------+     +-------------------+
|  FastAPI app   |  <----- (LOCAL fallback)---- |  Processed CSV       |     |  Looker Studio    |
|  Cloud Run     |                              |  backend/data/...    |     |  dashboard        |
|  /api/*        |  <----- (LIVE) ------------> |  processed/district_ |     |  (external BI)    |
|  /api/ask      |                              |  risk_scores.csv     |     |                   |
|  /api/analyze- |                              +----------------------+     +-------------------+
|  image         |
+-------+--------+
        |
        v
+----------------+
|  ADK agent     |
|  - router      |
|  - 3 tools     |
|  - composer    |
+-------+--------+
        |
        v
+----------------+        +--------------------+
|  Vertex AI     |        |  RAG corpus        |
|  (Gemini 2.5   |        |  10 passages       |
|   Flash)       |        |  in repo           |
|  text + vision |        |                    |
+----------------+        +--------------------+
```

---

## 2. Data contract (BigQuery)

Dataset: `breathesafe`

| Table | Grain | Source | Key columns |
|---|---|---|---|
| `health_survey` | district x indicator | NFHS-5 (long format, pivoted) | `state_name`, `district_name`, `pct_women_overweight_obese`, `pct_men_overweight_obese`, `pct_women_hypertension`, `pct_men_hypertension`, `pct_women_high_blood_sugar`, `pct_men_high_blood_sugar` |
| `demographics` | district | Census 2011 + calibrated synthetic | `state_name`, `district_name`, `total_population`, `pct_age_50_plus`, `pct_male`, `pct_urban`, `latitude`, `longitude` |
| `air_quality` | district | CPCB / OpenAQ-style synthetic | `state_name`, `district_name`, `pm25_annual_mean`, `aqi_category` |
| `awareness_signals` | state | Google Trends synthetic | `state_name`, `sleep_apnea_interest`, `snoring_interest`, `cpap_interest`, `awareness_normalized` |
| `screening_model` | single row | STOP-BANG weights + citations | `factor`, `weight`, `proxy_source`, `citation` |
| `district_risk_scores` (VIEW) | district | join of all 5 above | `risk_score`, `risk_category`, `awareness_gap_score`, `estimated_undiagnosed`, `is_awareness_desert` |

DDL is in [`backend/bq/schema.sql`](../backend/bq/schema.sql).

---

## 3. Agent contract

The agent is a Python module with three registered tools and one
router. The router is deterministic today (keyword + state match);
production swaps in Vertex AI Gemini function-calling. The tool interface is
intentionally small so the swap is mechanical.

```python
TOOLS = {
    "query_district_risk": {
        "fn": query_district_risk,   # signature matches the spec
        "description": "...",
    },
    "lookup_guidelines":  { ... },
    "analyze_image":      { ... },
}
```

### Tool 1 — `query_district_risk(state?, risk_category?, awareness_desert?, sort_by, limit)`
- Reads from BigQuery when `GOOGLE_APPLICATION_CREDENTIALS` is set,
  otherwise from the processed CSV.
- Returns: `{tool, count, rows, filters_applied}`.
- Used by the agent whenever the user names a state, asks for "top N",
  or asks for "awareness deserts".

### Tool 2 — `lookup_guidelines(query, top_k=3)`
- Keyword-overlap retrieval over a curated 10-passage corpus.
- Each passage carries a `citation`.
- Interface is identical to a future Vertex AI Vector Search call;
  swap the body of `rag_corpus.search()` to migrate.

### Tool 3 — `analyze_image(image_bytes, filename)`
- Real call: `vertexai.init(GCP_PROJECT_ID, GCP_REGION)` then
  `GenerativeModel(VERTEX_MODEL).generate_content([Part.from_data(image_bytes, mime_type), prompt])`
  with a vision prompt that extracts location, topic, headline text,
  and any health-relevant signal.
- Authenticates with Application Default Credentials (Workload Identity on
  Cloud Run). No API key needed.
- Default model: `gemini-2.5-flash` (broadly available in `asia-south1`).
  Override with `VERTEX_MODEL` env var.
- Mock fallback: deterministic Delhi-pollution extraction so the demo
  is identical every run.
- Cross-references the extracted location with `district_risk_scores`
  and returns a one-line "risk impact" card.

### System prompt (excerpt)

```
You are BreatheSafe, a public health intelligence agent for
obstructive sleep apnea (OSA) awareness in India.

RULES:
1. You are NOT a diagnostic tool. You do not diagnose individuals.
2. Analyze population-level data to recommend screening CAMPAIGNS.
3. Always ground in BigQuery district risk data.
4. Always cite data sources (NFHS-5, Census 2011, CPCB, Google Trends).
5. Include a responsible-AI disclaimer when discussing health topics.
6. Never invent numbers.
```

---

## 4. Deploy contract

Single Cloud Run service, single container.

| Property | Value |
|---|---|
| Service name | `breathesafe-api` |
| Region | `asia-south1` |
| Image | `asia-south1-docker.pkg.dev/<PROJECT>/breathesafe/api:1.0.0` |
| Port | `8080` (Cloud Run default) |
| Min instances | `0` (cost) |
| Max instances | `2` (demo) |
| Memory | `1 GiB` |
| CPU | `1` |
| Concurrency | `40` |
| Timeout | `300s` (Vertex AI calls) |
| Env vars | `BQ_PROJECT_ID`, `GCP_PROJECT_ID`, `GCP_REGION`, `VERTEX_MODEL` (optional, default `gemini-2.5-flash`), `USE_BIGQUERY` |
| Secrets | Workload Identity (Cloud Run default SA) — no API keys required |
| Public access | yes (allow-unauthenticated) for the demo |

The image is built from this repo's `Dockerfile`, which copies only
`backend/` and `frontend/` and excludes dev artefacts (`.git`, `docs/`,
`scripts/`, tests, the .pptx). See `.dockerignore`.

---

## 5. Failure modes and fallbacks

| Failure | Fallback |
|---|---|
| Vertex AI auth / network failure | `analyze_image` returns deterministic Delhi-pollution mock. The agent router still works (keyword-based). The text composer also falls back to a deterministic Markdown composer. |
| BigQuery credentials missing | `/api/districts` and `/api/summary` read from the processed CSV shipped inside the container. |
| Cold start latency | Cloud Run min-instances=0; first request ~3s. Demo recorded with warm instance. |
| `analyze_image` size limit | Hard-cap 8 MB; reject larger with 413. |
| No district matches a state name | API returns empty `rows`; agent suggests the user rephrase. |

---

## 6. What we deliberately did not build

- Wearable data ingestion (would dilute the public-health story)
- CPAP / personal data (out of scope; privacy risk)
- Login / user accounts (demo audience is judges, not patients)
- Production-grade medical compliance (screening-prioritization, not diagnosis)
- Vector Search setup (RAG corpus + keyword overlap is sufficient for 10 passages)
- Mobile app (single responsive SPA covers judges on phone and laptop)
