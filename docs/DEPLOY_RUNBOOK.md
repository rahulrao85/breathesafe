# BreatheSafe — Cloud Run Deploy Runbook

> Copy-paste sequence to take BreatheSafe from this repo to a public
> Cloud Run URL. Target account: `rahulrao85@gmail.com`. Estimated
> time: 20-30 minutes for a first-time deploy.

---

## 0. Prerequisites (one-time)

| What | Why |
|---|---|
| GCP account `rahulrao85@gmail.com` with **Owner** on a billing-enabled project | Cloud Run, Artifact Registry, BigQuery all need an active billing account |
| `gcloud` CLI installed (https://cloud.google.com/sdk/docs/install) | Drives every step below |
| `docker` installed and running | Builds the image (Cloud Build can do it instead, see alt section) |
| No API keys needed | Vertex AI authenticates via Workload Identity (Cloud Run default SA). `roles/aiplatform.user` must be granted to the SA on the project. |
| This repo cloned somewhere clean | The `breathesafe/` folder is what we ship |

Pick a project ID. We use `breathesafe-hackathon` in the examples —
swap to whatever you actually created.

```powershell
$env:GCP_PROJECT_ID = "breathesafe-hackathon"
$env:GCP_REGION     = "asia-south1"
$env:REPO           = "breathesafe"
$env:SERVICE        = "breathesafe-api"
$env:TAG            = "1.0.0"
```

---

## 1. Authenticate and select the project

```powershell
gcloud auth login rahulrao85@gmail.com
gcloud config set project $env:GCP_PROJECT_ID
gcloud config set run/region $env:GCP_REGION
gcloud auth configure-docker "$env:GCP_REGION-docker.pkg.dev"
```

---

## 2. Enable the required APIs

```powershell
gcloud services enable `
  run.googleapis.com `
  artifactregistry.googleapis.com `
  cloudbuild.googleapis.com `
  bigquery.googleapis.com `
  storage.googleapis.com `
  secretmanager.googleapis.com
```

---

## 3. Create the Artifact Registry repo

```powershell
gcloud artifacts repositories create $env:REPO `
  --repository-format=docker `
  --location=$env:GCP_REGION `
  --description="BreatheSafe API images"
```

---

## 4. (No secrets to put in Secret Manager)

Vertex AI is authenticated via Workload Identity — the Cloud Run default
service account is used automatically. The only required IAM grant is
`roles/aiplatform.user` on the project for the runtime SA:

```powershell
$env:PROJECT_NUMBER = (gcloud projects describe $env:GCP_PROJECT_ID --format="value(projectNumber)")
$env:RUNTIME_SA = "$env:PROJECT_NUMBER-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $env:GCP_PROJECT_ID `
  --member="serviceAccount:$env:RUNTIME_SA" `
  --role="roles/aiplatform.user"
```

If you skipped Workload Identity and are using a downloaded SA key,
the path still works the same — just set `GOOGLE_APPLICATION_CREDENTIALS`
to point at the key file. The Vertex AI SDK picks it up automatically.

---

## 5. Build the container

From the repo root (the parent of `breathesafe/`):

```powershell
cd "F:\AGENTIC WORLD\GEN AI APEC Cohort 2\breathesafe"

docker build `
  --tag "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:$env:TAG" `
  --tag "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:latest" `
  .
```

### Alt: build with Cloud Build (no local Docker)

```powershell
gcloud builds submit `
  --tag "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:$env:TAG" `
  .
```

---

## 6. Push the image

```powershell
docker push "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:$env:TAG"
docker push "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:latest"
```

(Cloud Build already pushes, so skip if you used the alt.)

---

## 7. Load the BigQuery dataset (one-time)

The image ships the processed CSVs and serves them locally — that is
the default demo path. If you also want the live BigQuery story for
the judges (and for Looker Studio), load the data:

```powershell
# Create the dataset
bq --location=$env:GCP_REGION mk --dataset --description "BreatheSafe unified data" $env:GCP_PROJECT_ID:breathesafe

# Load each raw CSV into its table
bq load --autodetect --source_format=CSV `
  $env:GCP_PROJECT_ID:breathesafe.health_survey `
  backend/data/raw/nfhs5_districts.csv

bq load --autodetect --source_format=CSV `
  $env:GCP_PROJECT_ID:breathesafe.awareness_signals `
  backend/data/raw/trends_awareness.csv

bq load --autodetect --source_format=CSV `
  $env:GCP_PROJECT_ID:breathesafe.air_quality `
  backend/data/raw/air_quality_districts.csv

# Apply the schema (creates demographics, screening_model, and the view)
bq query --use_legacy_sql=false < backend/bq/schema.sql
```

---

## 8. Deploy to Cloud Run

```powershell
gcloud run deploy $env:SERVICE `
  --image "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:$env:TAG" `
  --platform=managed `
  --region=$env:GCP_REGION `
  --allow-unauthenticated `
  --port=8080 `
  --memory=1Gi `
  --cpu=1 `
  --concurrency=40 `
  --timeout=300 `
  --min-instances=0 `
  --max-instances=2 `
  --set-env-vars="BQ_PROJECT_ID=$env:GCP_PROJECT_ID,GCP_PROJECT_ID=$env:GCP_PROJECT_ID,GCP_REGION=$env:GCP_REGION,USE_BIGQUERY=true,VERTEX_MODEL=gemini-2.5-flash"
```

Notes:
- `VERTEX_MODEL` defaults to `gemini-2.5-flash` (broadly available in
  `asia-south1`). Switch to `gemini-2.5-pro` only if your region
  supports it — `gemini-2.5-pro` is **not** available in `asia-south1`.
- No API keys are passed. Vertex AI authenticates via the Cloud Run
  default service account using Workload Identity.
- If you don't want live BigQuery, drop the `USE_BIGQUERY=true` flag
  and the app falls back to the processed CSVs shipped in the image.

Capture the URL it prints at the end — that is your public demo URL.

---

## 9. Smoke test the deployed service

```powershell
$env:URL = (gcloud run services describe $env:SERVICE --region=$env:GCP_REGION --format="value(status.url)")

# Health
Invoke-RestMethod "$env:URL/health"

# National summary
Invoke-RestMethod "$env:URL/api/summary"

# UP districts, top 5 by awareness gap
Invoke-RestMethod "$env:URL/api/districts?state=Uttar%20Pradesh&limit=5"

# Agent ask (Vertex AI path)
$body = '{"question":"Top 3 districts in Uttar Pradesh for OSA camps"}'
Invoke-RestMethod -Method Post -Uri "$env:URL/api/ask" -ContentType "application/json" -Body $body

# Multimodal (any small JPEG; the mock + cross-ref path will fire)
$img = [System.IO.File]::ReadAllBytes("some.jpg")
Invoke-RestMethod -Method Post -Uri "$env:URL/api/analyze-image" -InFile "some.jpg" -ContentType "image/jpeg"
```

Expected:
- `/health` → `{"status":"ok"}`
- `/api/summary` → 365 districts, 92 HIGH
- `/api/districts?state=Uttar Pradesh` → 6 rows
- `/api/ask` → Markdown answer with citations
- `/api/analyze-image` → JSON with `extracted.location_name` and a
  matched `cross_reference.district` if the location is in the data

---

## 10. Looker Studio

See [`docs/LOOKER_STUDIO.md`](LOOKER_STUDIO.md) for the dashboard
build. Connect to the BigQuery view `breathesafe.district_risk_scores`,
publish the report, and paste the link into the SPA's Looker card and
the submission form.

---

## 11. Tear-down / re-deploy

| Action | Command |
|---|---|
| Re-deploy after a code change | `gcloud builds submit --tag "$env:GCP_REGION-docker.pkg.dev/$env:GCP_PROJECT_ID/$env:REPO/api:$env:TAG" .` then re-run the `gcloud run deploy` from step 8 |
| Tail logs | `gcloud run services logs tail $env:SERVICE --region=$env:GCP_REGION` |
| Open the service in console | `gcloud run services describe $env:SERVICE --region=$env:GCP_REGION --format="value(status.url)"` |
| Delete the service | `gcloud run services delete $env:SERVICE --region=$env:GCP_REGION` |

---

## 12. Env-var reference

| Var | Required | Default | Notes |
|---|---|---|---|
| `PORT` | no | `8080` | Cloud Run sets this; uvicorn reads it |
| `BQ_PROJECT_ID` | yes (when `USE_BIGQUERY=true`) | — | Project that owns the `breathesafe` dataset |
| `GCP_PROJECT_ID` | yes (for Vertex AI) | — | Project that hosts the Vertex AI endpoint |
| `GCP_REGION` | yes | `asia-south1` | BigQuery + Vertex AI region |
| `USE_BIGQUERY` | no | `false` | When `false`, the app reads from the CSV shipped in the image |
| `VERTEX_MODEL` | no | `gemini-2.5-flash` | Vertex AI model name. Use `gemini-2.5-pro` only if your region supports it. |
| `GOOGLE_APPLICATION_CREDENTIALS` | no | unset | Path to SA key file (local dev). On Cloud Run, Workload Identity is used. |

---

## 13. Common failures and fixes

| Symptom | Fix |
|---|---|
| Deploy fails with "image not found" | Re-run `docker push` (or use Cloud Build) |
| `/api/ask` returns the deterministic composer after deploy | The Cloud Run runtime SA is missing `roles/aiplatform.user`. Re-run step 4. Also check `gcloud run services logs tail $env:SERVICE --region=$env:GCP_REGION`. |
| Vertex AI returns 404 NOT_FOUND on a model | The model isn't available in your region. Re-test model availability (step 13.5) and set `VERTEX_MODEL` to one that works. |
| `/api/summary` returns 0 rows | You enabled `USE_BIGQUERY=true` but did not load the dataset; either load it (step 7) or set `USE_BIGQUERY=false` |
| 401 from `/api/analyze-image` upload | The image is not multipart-encoded; the SPA handles this — re-test from the SPA, not `curl` |
| 8 MB rejection on upload | Hard cap; reduce image size or update the cap in `main.py` |
| Cold start > 5s on first request | Demo-time: set `--min-instances=1` (costs ~$0.05/hr while idle) |
