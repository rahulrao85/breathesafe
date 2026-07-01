# BreatheSafe - Final QA & Submission Checklist

## 1. Local QA Checklist (Pre-Deployment)
- [x] **Backend API**: The FastAPI server starts successfully on port 8080 (`http://127.0.0.1:8080/health` returns `status: ok`).
- [x] **Image Upload / Multimodal**: The 8MB cap logic is successfully enforced in `backend/api/main.py`.
- [x] **Agent Routing**: The ADK-style agent correctly routes questions between `query_district_risk`, `lookup_guidelines`, and `analyze_image`.
- [x] **Frontend UI (SPA)**: The HTML/CSS/JS loads without 404s. District filtering and dashboard work accurately.
- [x] **Responsible AI Compliance**: Disclaimers are clearly visible in the UI footer and appended to agent chat outputs.
- [x] **Environment Variables**: `.env.example` is the source of truth. No API keys required (Vertex AI uses Workload Identity).

## 2. Cloud Run Deployment Checklist
- [ ] **Docker Build**: The `Dockerfile` successfully builds the image locally (`docker build -t breathesafe .`).
- [ ] **Artifact Registry**: Image is successfully pushed to Google Cloud Artifact Registry.
- [ ] **Cloud Run Service**: Container is deployed and listening on the designated Cloud Run URL.
- [ ] **IAM / Env Vars (GCP)**: `BQ_PROJECT_ID`, `GCP_PROJECT_ID`, `GCP_REGION`, `VERTEX_MODEL` are set as env vars. The Cloud Run runtime SA has `roles/aiplatform.user` on the project.
- [ ] **Production Sanity Check**: The live Cloud Run URL loads the SPA properly, and the agent responds to a test query with a real Vertex AI call (not just the deterministic composer).

## 3. Final Hackathon Submission Checklist (Gen AI Academy APAC)
- [ ] **Code Repository**: All code is committed and pushed to a **public** GitHub repo. `.env`, any SA keys, and the `.pptx` are excluded via `.gitignore`.
- [ ] **Architecture Diagram**: Added to `README.md` and `docs/ARCHITECTURE.md`.
- [ ] **Pitch Deck (10-Slide PPT)**: Completed and uploaded. Covers the problem, architecture, use of Vertex AI, and impact.
- [ ] **Demo Video (2-min Walkthrough)**: Recorded and uploaded. Demonstrates the core value proposition (screening prioritization) without pretending to be a medical diagnostic tool.
- [ ] **Looker Studio Dashboard**: Published with correct data source links (BigQuery view) and sharing permissions set to "Anyone with the link can view". The URL is wired into the SPA's "Open in Looker" button.
- [ ] **README Polish**: The `README.md` clearly explains the architecture, the "Why", and how to run it locally.
