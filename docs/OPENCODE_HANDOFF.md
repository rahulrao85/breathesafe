# Handoff Context for OpenCode (BreatheSafe)

## 1. What was completed during this session:
- **Routing Fix:** The `backend/agent/agent.py` was updated to properly map city names (like Mumbai, Pune, Bengaluru) to their respective states so that the agent doesn't default to the National Top 5 when asked about a city.
- **BigQuery Setup:** The `promptwars-mumbai-499305` project was used to create the `breathesafe` BigQuery dataset. All raw CSV data (`health_survey`, `demographics`, `air_quality`, `awareness_signals`) was loaded, and the `schema.sql` views (`district_risk_scores`, `state_summary`) were successfully created.
- **Cloud Run Deployment:** The application (with the 8MB cap and city mapping fixes) was built using Cloud Build and deployed to Cloud Run at `https://breathesafe-api-513650706645.asia-south1.run.app`.

## 2. Issues to Fix Now:

### Issue A: Multimodal Vision always returning "Delhi NCR"
**Problem:** When uploading an image, the backend always returns a hardcoded "Delhi NCR" mock response instead of analyzing the image. 
**Root Cause:** In `backend/agent/tools.py`, the `analyze_image` function used `USE_REAL_GEMINI = bool(GEMINI_API_KEY)`. If the `GEMINI_API_KEY` was missing from the environment (or not loaded from `.env` in local development), it silently fell back to `_mock_vision_extraction`. If the Gemini API call failed (e.g., due to an incorrect model name or import error), it also caught the exception and fell back to the mock.
**Resolution (30 Jun 2026):** Migrated to Vertex AI (`google-cloud-aiplatform`). The `google.generativeai` SDK was removed. `analyze_image` now uses `vertexai.init(GCP_PROJECT_ID, GCP_REGION)` + `GenerativeModel(VERTEX_MODEL).generate_content(...)` with `Part.from_data(image_bytes, mime_type)` for multimodal. Authentication is via Application Default Credentials (Workload Identity on Cloud Run). No API key is required. Default model: `gemini-2.5-flash` (available in `asia-south1`; `gemini-2.5-pro` is **not**). The mock remains as a fallback when Vertex AI auth/network fails.

### Issue B: "Open in Looker" button doesn't open a new tab
**Problem:** In `frontend/index.html`, the Looker Studio button uses an `onclick="alert(...); return false;"` which prevents a new tab from opening. 
**Resolution (1 Jul 2026):** Button rewritten as a real `<a target="_blank" rel="noopener">` styled as a button via `.btn-secondary` CSS. Wired to the public Looker Studio URL: https://datastudio.google.com/reporting/e8879c34-66ef-427c-a8f5-9fb8ef09d20d

## 3. Next Steps:
1. Fix the Image Vision local environment/fallback bug.
2. Fix the Looker Studio button behavior in the HTML.
3. Help the user finalize the 10-slide PowerPoint deck and Demo Video script for their Gen AI Hackathon submission.
