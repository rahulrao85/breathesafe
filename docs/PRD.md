# BreatheSafe - 1-Page PRD

**Hackathon:** Google Cloud Gen AI Academy APAC 2026 - Cohort 2  
**Theme:** Unified Data Analytics & Intelligence  
**Owner:** Rahul Rao  
**Created:** 29 Jun 2026  
**Status:** LOCKED - build this, not PulseCare

---

## 1. Problem

India has a massive under-diagnosis problem for obstructive sleep apnea (OSA). Most people who snore, feel fatigued, have obesity or hypertension, or live in polluted cities will never proactively visit a sleep clinic.

The issue is not just individual diagnosis. Public health officers, NGOs, corporate wellness teams, and awareness advocates do not know where to focus scarce screening and awareness capacity.

Today, the relevant signals are fragmented:

- NFHS health risk indicators sit in survey datasets.
- Census demographic risk factors sit elsewhere.
- Air pollution data sits in CPCB/OpenAQ-style datasets.
- Search awareness signals sit in Google Trends.
- Clinical screening logic sits in STOP-BANG and medical guidelines.

BreatheSafe joins these signals into a single district-level intelligence layer and identifies "awareness deserts": places where estimated OSA risk is high but awareness is low.

## 2. Users & Decisions

| Persona | Decision BreatheSafe supports |
|---|---|
| Public health officer | Which districts should receive OSA screening camps first? |
| NGO / health foundation | Where should awareness drives be launched this quarter? |
| Corporate wellness lead | Should a campus offer sleep-health screening based on local risk? |
| Journalist / advocate | Which Indian districts show high sleep-apnea risk but low awareness? |

## 3. One-Line Solution

A population-level sleep-apnea screening-awareness engine that joins public health, demographic, pollution, and awareness data in BigQuery, scores district risk using a STOP-BANG-derived model, and exposes Looker dashboards plus a Vertex AI (Gemini) + ADK agent on Cloud Run.

## 4. Unified Data Angle

| Source | What it provides | Destination |
|---|---|---|
| NFHS-5 district health data | Obesity, hypertension, blood sugar, tobacco proxies | `breathesafe.health_survey` |
| Census 2011 demographics | Population, age, sex ratio, urbanization, district coordinates | `breathesafe.demographics` |
| CPCB/OpenAQ-style air quality | PM2.5 annual mean and AQI category | `breathesafe.air_quality` |
| Google Trends awareness data | Search interest for sleep apnea, snoring, CPAP | `breathesafe.awareness_signals` |
| STOP-BANG model weights | Explainable screening risk logic | `breathesafe.screening_model` |
| WHO/ICMR/NHS/AASM guidance | RAG corpus for grounded explanations | Cloud Storage + Vertex AI Vector Search |

The core BigQuery view is `breathesafe.district_risk_scores`, where these datasets are joined and converted into:

- `risk_score`
- `risk_category`
- `awareness_gap`
- priority ranking for screening/awareness campaigns

## 5. Scope boundaries

BreatheSafe does not ingest wearable data, CPAP data, or personal health files. It does not diagnose an individual. It is a public-health awareness and screening-prioritization system built entirely on population-level datasets.

The system answers one question: **"Where in India should sleep-apnea screening camps and awareness drives be launched first?"**

## 6. Risk Model

Individual STOP-BANG has 8 factors. BreatheSafe adapts only the factors that can be responsibly approximated at population level.

| STOP-BANG factor | Population proxy | Source |
|---|---|---|
| Snoring | Search interest in "snoring" and low OSA awareness | Google Trends |
| Pressure | Hypertension percentage | NFHS-5 |
| BMI | Overweight/obesity percentage | NFHS-5 |
| Age | Percentage of population age 50+ | Census |
| Gender | Male population percentage | Census |
| Environmental amplifier | PM2.5 annual mean | Air quality data |

Conservative omissions: tiredness, observed apnea, and neck circumference are not included because they do not have reliable population-level proxies in the demo data.

Simplified formula:

```text
risk_score =
  0.25 * hypertension_normalized +
  0.25 * obesity_normalized +
  0.15 * age50_normalized +
  0.10 * male_normalized +
  0.25 * pm25_normalized

awareness_gap = risk_score * (1 - awareness_normalized)
```

High risk plus low awareness equals screening priority.

## 7. Required Google Stack Mapping

| Required service | Use in BreatheSafe |
|---|---|
| Vertex AI | Gemini 2.5 Flash (text + vision), embeddings, optional Vector Search grounding |
| Vertex AI (Gemini) | Agent reasoning, explanations, multimodal newspaper/photo analysis |
| BigQuery | Unified warehouse, joins, risk scoring views |
| Cloud Run | Single deployable app: FastAPI backend + web frontend |
| ADK | Agent with BigQuery, RAG, and Vision tools |
| Cloud Storage | Raw CSVs, reference PDFs, uploaded image inputs |
| Looker Studio | District heatmap, risk table, awareness gap dashboard |

## 8. Prototype Scope

Build a single Cloud Run web app with:

- Landing/dashboard page showing India district risk summary.
- Search/filter by state or district.
- Ranked "Top awareness deserts" table.
- Agent chat with 4 fixed demo prompts and free-text input.
- Image upload for the multimodal demo.
- Link/embed/screenshot path for Looker Studio dashboard.
- Responsible AI disclaimer: this is screening prioritization, not medical diagnosis.

Do not build:

- Login.
- Native mobile app.
- Real patient intake.
- Wearable/CPAP ingestion.
- Production-grade medical compliance.

## 9. Multimodal Demo Hook

The winning moment:

1. Upload a photo/screenshot of a newspaper headline about Delhi air pollution.
2. Vertex AI Vision extracts the place and issue.
3. The ADK agent queries BigQuery for NCR district risk.
4. The app returns: "Delhi NCR already has high PM2.5-linked OSA risk and low awareness; prioritize these districts for screening camps."

This proves the project is not just a dashboard or chatbot. It is multimodal intelligence over unified data.

## 10. Demo Script

| Time | Scene |
|---|---|
| 0:00-0:15 | "I have sleep apnea. I got diagnosed because I had access. Millions in India do not." |
| 0:15-0:35 | Show Looker heatmap: high-risk and low-awareness districts. |
| 0:35-1:00 | Ask: "Which 5 districts in Uttar Pradesh should get screening camps first?" |
| 1:00-1:25 | Agent returns ranked districts with BigQuery-backed reasoning. |
| 1:25-1:45 | Upload Delhi pollution headline image. Vertex AI Vision links it to NCR risk. |
| 1:45-2:00 | Show architecture: Cloud Storage -> BigQuery -> ADK + Vertex AI -> Cloud Run + Looker. |

## 11. Success Criteria

- Live Cloud Run URL.
- BigQuery dataset with at least 5 source tables and 1 joined scoring view.
- Looker Studio dashboard with heatmap/table.
- ADK agent with at least 3 tools: BigQuery query, RAG/context lookup, Vision/image analysis.
- Multimodal demo works with one pollution/news image.
- 10-slide deck completed.
- 2-minute demo video recorded.
- Responsible AI disclaimer visible in app and deck.

## 12. Build Priority

If time is tight, optimize in this order:

1. BigQuery scoring view and sample district data.
2. Cloud Run app with district table and agent prompts.
3. Looker dashboard.
4. Vertex AI (Gemini) + ADK BigQuery reasoning.
5. Multimodal image upload.
6. RAG citations over medical guidance.

RAG is useful, but the core judging story is unified data plus intelligence. Do not let Vector Search setup block the main demo.

---

*Final decision: Build BreatheSafe. A competing personal-tracker concept (PulseCare) was rejected during scoping because it would have duplicated personal-sleep-tracking territory rather than opening the public-health lane BreatheSafe occupies.*
