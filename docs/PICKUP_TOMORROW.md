# BreatheSafe — Pickup Tomorrow

**Status:** Build paused mid-Day 3. Backend + frontend done locally. Need: Dockerfile, deck, README, deploy, demo video.
**Date:** 29 Jun 2026
**Owner:** Rahul Rao
**Next session:** continue from "Resume here" section below

---

## What's done

### 1. Data processing (`scripts/process_data.py`)
- Pivots NFHS-5 long-format → wide format (7 risk indicators; indicator 80 men obesity missing from source, derived from women)
- Generates 365 synthetic Census 2011 demographic rows (calibrated to state aggregates)
- 24 demo-coverage synthetic districts added for UP, Delhi NCR, MP, TN, Bihar, Punjab, Haryana, Odisha, Jharkhand, Chhattisgarh, Rajasthan (so the demo prompts work)
- 50 AQI rows + 36 awareness states
- Min-max normalization + weighted sum risk score
- Percentile-based HIGH/MODERATE/LOW thresholds (P75/P25) — NOT absolute 0.6/0.3 (which were unreachable due to sparse AQI)
- Outputs: `backend/data/processed/district_risk_scores.csv` (365 rows) + `state_summary.csv` (31 states)

### 2. Backend (`backend/api/main.py`)
FastAPI on port 8080, single container. Endpoints:
- `GET /health` — ok
- `GET /api/summary` — national KPIs
- `GET /api/districts` — filterable list (`?state=`, `?risk_category=`, `?awareness_desert=`, `?sort_by=`, `?limit=`)
- `GET /api/states` — state rollup
- `GET /api/district/{state}/{district}` — single district
- `POST /api/ask` — agent chat
- `POST /api/analyze-image` — Vision (with mock fallback)
- `GET /` + `/static/*` — serves the SPA

### 3. Agent (`backend/agent/`)
- `agent.py` — ADK-style router, deterministic rules (state detection, intent classification)
- `tools.py` — 3 tools: `query_district_risk`, `lookup_guidelines`, `analyze_image`
- `rag_corpus.py` — 10 curated passages (STOP-BANG origin, India prevalence, PM2.5-OSA link, obesity/hypertension/age, ICMR/NHS guidance, screening camp design)
- Tool calls surface in the response: e.g. `tools_called: ["query_district_risk", "lookup_guidelines"]`
- All citations rendered as **Sources cited:** block

### 4. Frontend (`frontend/`)
- `index.html` — single-page app: header, narrative, KPI strip, filters+table, agent chat, multimodal upload, Looker placeholders, architecture diagram, disclaimer, footer
- `static/css/styles.css` — public health / civic intelligence palette (dark by default, with a light theme toggle; NOT hospital, NOT consumer-wearable)
- `static/js/app.js` — fetch, render Markdown (incl. tables), event bindings
- Served at `http://localhost:8080/`

### 5. Tested end-to-end
- `/api/summary` → 365 districts, 92 HIGH, 3 awareness deserts
- `/api/districts?state=Uttar%20Pradesh` → returns 6 UP districts, sorted by gap
- `/api/ask` with "Top 5 UP districts" → returns full ranked table + driving factors + RAG citations
- Frontend serves at `/`, `/static/css/styles.css`, `/static/js/app.js` (all 200)

### 6. Demo prompts wired (UI buttons)
1. Top 5 districts in Uttar Pradesh
2. Why Delhi NCR a high priority?
3. Awareness deserts across India
4. Draft a 100-word public awareness message for highest-risk district

---

## Resume here

### Day 4 (next session)
1. **Fill 10-slide PPT deck** — `Prototype Submission Deck _ Gen AI Academy APAC Edition.pptx` is the template; write slide-by-slide content
2. **README** + **architecture diagram** in `breathesafe/README.md`
3. **Dockerfile** + `requirements.txt` for Cloud Run
4. **Looker Studio spec** (link to view, embed placeholder is already in the SPA)

### Day 5
5. **Deploy to Cloud Run** (single container, BQ credentials via env)
6. **Record 2-min demo video** (script in `docs/OPENCODE_HANDOFF.md` — 7 segments)
7. **Final QA** + submit

---

## Key files

| File | Purpose |
|---|---|
| `breathesafe/docs/FINAL_HANDOFF.md` | Original merged spec (Antigravity + Codex) |
| `breathesafe/docs/PRD.md` | Locked product spec |
| `breathesafe/docs/OPENCODE_HANDOFF.md` | Codex's build instructions |
| `breathesafe/scripts/process_data.py` | Data processing pipeline |
| `breathesafe/scripts/fetch_data.py` | Data acquisition (data already downloaded) |
| `breathesafe/backend/api/main.py` | FastAPI app |
| `breathesafe/backend/agent/agent.py` | Agent router |
| `breathesafe/backend/agent/tools.py` | 3 tools |
| `breathesafe/backend/agent/rag_corpus.py` | 10 RAG passages |
| `breathesafe/backend/bq/schema.sql` | BigQuery schema (5 tables + 2 views) |
| `breathesafe/backend/data/processed/district_risk_scores.csv` | 365 joined districts |
| `breathesafe/backend/data/processed/state_summary.csv` | 31-state rollup |
| `breathesafe/frontend/index.html` | SPA entry |
| `breathesafe/frontend/static/css/styles.css` | Styles |
| `breathesafe/frontend/static/js/app.js` | Frontend logic |

---

## How to resume

```powershell
# 1. Start the backend
cd "F:\AGENTIC WORLD\GEN AI APEC Cohort 2\breathesafe"
python -X utf8 -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8080

# 2. Open in browser
#    http://127.0.0.1:8080/

# 3. Reprocess data if needed
python -X utf8 scripts/process_data.py
```

The data is committed (CSVs in `backend/data/processed/`). The 365-district processed file is what the API serves. To switch to live BigQuery, set `GOOGLE_APPLICATION_CREDENTIALS` and `BQ_PROJECT_ID` env vars; the same SQL in `backend/bq/schema.sql` defines the view.

---

## Known issues / notes

- The agent's RAG is keyword-overlap, not real embeddings. Same interface; swap in Vertex AI Vector Search by replacing the `search()` function in `rag_corpus.py`.
- The `analyze_image` endpoint uses a deterministic mock. Real Vertex AI Vision is wired (Gemini 2.5 Flash via `google-cloud-aiplatform`); the mock fires only when Vertex AI auth/network fails. On Cloud Run, ensure the runtime SA has `roles/aiplatform.user` on the project.
- "Awareness deserts" (3 districts: Nicobar, N District Sikkim, S District Sikkim) are the demo's punchline — high risk + near-zero awareness. The contrast with Delhi (high risk + high awareness) is the storytelling hook.
- All encoding kept ASCII-safe (used `ug/m3` instead of `µg/m³` to avoid Windows console issues) — frontend uses HTML entities if you want the real character.

---

*Pickup-friendly. Backend + frontend run with two commands. Slide deck is the next thing to do.*

---

# Pickup — 30 Jun 2026 (Day 4)

**Status:** End of day. Vertex AI migration + predictive forecast + Looker button shipped. **Looker Studio dashboard — PARKED.** Demo video — still pending.

## Done this session

1. **Vertex AI migration** — `google.generativeai` removed; `vertexai` SDK adopted. Both text composer (`backend/agent/agent.py`) and vision call (`backend/agent/tools.py`) now use `vertexai.init(project, location)` + `GenerativeModel(...).generate_content(...)` with automatic ADC auth on Cloud Run.
2. **🔮 6-Month Predictive Forecast** — added as rule 11 + format section in the system prompt (LLM-composed path) and as a heuristic data-derived section in the deterministic composer. Always present for any state/district analysis.
3. **Looker button** in `frontend/index.html` line 148-155 — placeholder URL with HTML comment reminder. `.btn-secondary` CSS updated to render the `<a>` as a button.
4. **BigQuery data loaded** — `breathesafe.district_risk_scores` (365 rows) and `breathesafe.state_summary` (31 rows) now populated. Loader script at `scripts/load_to_bigquery.ps1`.

## ⏸ PARKED — Looker Studio dashboard
- Tried to use a GCS template (https://datastudio.google.com/c/u/0/reporting/670eee3f-ad6d-45ea-a169-853ab023dc84) — wrong fit (cloud storage template, not public health).
- **Decision:** park for tomorrow. Fresh start, pick a Geographic or Scorecard template, OR build a `/dashboard` public route in the SPA (option B1/B2 from chat).

## Still pending for submission
- [ ] **Demo video** (~30 min) — script at `docs/DEMO_VIDEO_SCRIPT.md`; **biggest single remaining gap** (~5-7 pts).
- [ ] **Looker Studio dashboard URL** (parked — see above) — optional, ~3-4 pts.
- [ ] **Deploy** the Vertex AI + forecast changes from today to Cloud Run.

## Deploy command when ready
```powershell
$Project = "promptwars-mumbai-499305"
$Region  = "asia-south1"
$Repo    = "breathesafe"
$Service = "breathesafe-api"
$Tag     = "1.0.4"

cd "F:\AGENTIC WORLD\GEN AI APEC Cohort 2\breathesafe"
gcloud builds submit --tag "$Region-docker.pkg.dev/$Project/$Repo/api:$Tag" .
gcloud run deploy $Service `
  --image "$Region-docker.pkg.dev/$Project/$Repo/api:$Tag" `
  --region=$Region --platform=managed --allow-unauthenticated `
  --port=8080 --memory=1Gi --cpu=1 --concurrency=40 --timeout=300 --max-instances=2 `
  --set-env-vars="BQ_PROJECT_ID=$Project,GCP_PROJECT_ID=$Project,GCP_REGION=$Region,USE_BIGQUERY=true,VERTEX_MODEL=gemini-2.5-flash"
```

**Pre-req:** the Cloud Run default service account needs `roles/aiplatform.user` on the project:
```powershell
$SA = (gcloud run services describe breathesafe-api --region=asia-south1 --format="value(spec.template.spec.serviceAccountName)")
if ($SA -eq "") { $SA = "$Project-compute@developer.gserviceaccount.com" }
gcloud projects add-iam-policy-binding $Project --member="serviceAccount:$SA" --role="roles/aiplatform.user"
```

## Verification commands
```powershell
$Url = "https://breathesafe-api-513650706645.asia-south1.run.app"
curl "$Url/health"
curl "$Url/api/summary"
curl -X POST -H "Content-Type: application/json" -d '{"question":"Top 5 districts in Uttar Pradesh"}' "$Url/api/ask"
curl -X POST -H "Content-Type: application/json" -d '{"question":"What is OSA"}' "$Url/api/ask"
curl -X POST -F "file=@$env:USERPROFILE\Pictures\sample-aqi.jpg" "$Url/api/analyze-image"   # optional
gcloud run services logs tail breathesafe-api --region=asia-south1
```

