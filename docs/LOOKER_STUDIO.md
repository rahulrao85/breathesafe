# BreatheSafe — Looker Studio Dashboard Spec

> Spec for the India district awareness-gap dashboard. Build this once
> after the BigQuery dataset is loaded. The Cloud Run SPA has a card
> linking to the published URL.

**Published URL:** https://datastudio.google.com/reporting/e8879c34-66ef-427c-a8f5-9fb8ef09d20d
*(live link — keep this in sync with the SPA's "Open in Looker ↗" button)*

---

## 0. Connect a data source

1. Open https://lookerstudio.google.com → **Blank Report**.
2. **Add data → BigQuery**.
3. Authorize with the project that owns `breathesafe` (account
   `rahulrao85@gmail.com`).
4. Pick the project → dataset `breathesafe` → table
   `district_risk_scores`.
5. Click **Add** → Looker Studio creates the report bound to that
   view. The view will refresh whenever `process_data.py` is re-run and
   the table is reloaded.

---

## 1. Dashboard layout (top to bottom)

```
+----------------------------------------------------------------+
|  Header: BreatheSafe — India OSA Screening Intelligence         |
|  Sub:  Source: breathesafe.district_risk_scores  |  As of ...  |
+----------------+-----------------------------------------------+
|  KPI  |  KPI   |  KPI          |  KPI                          |
| 365   |  92    |  3 deserts    |  0.306 avg risk               |
| Dists |  HIGH  |  Awareness    |                               |
| Scored|  Risk  |  Deserts      |                               |
+----------------+-----------------------------------------------+
|                                                                |
|  [INDIA HEATMAP — bubble map, bubble = awareness_gap_score]    |
|   - color: risk_category (HIGH red, MOD amber, LOW teal)       |
|   - size: estimated_undiagnosed                                |
|   - filter chips: state, risk_category, awareness_desert       |
|                                                                |
+----------------------------------------------------------------+
|                                                                |
|  [TABLE — Top 30 districts by awareness_gap_score]             |
|   columns: district_name, state_name, risk_score,             |
|            awareness_gap_score, estimated_undiagnosed,         |
|            pm25_annual_mean, pct_adults_overweight_obese,      |
|            pct_adults_hypertension                             |
|   sort: awareness_gap_score desc                               |
|   conditional formatting: risk_score > 0.5  → red bar          |
|                                                                |
+----------------------------------------------------------------+
|                                                                |
|  [BAR — Top 10 awareness deserts]                              |
|   x: district_name   y: awareness_gap_score                    |
|   color: estimated_undiagnosed (gradient)                      |
|                                                                |
+----------------------------------------------------------------+
|                                                                |
|  [SCATTER — Risk vs Awareness, one dot per district]           |
|   x: awareness_normalized   y: risk_score                     |
|   color: risk_category                                        |
|   size: total_population                                      |
|   quadrant annotations: HIGH risk + LOW awareness = "Desert"  |
|                                                                |
+----------------------------------------------------------------+
|  Footer: "BreatheSafe — screening-prioritization, not          |
|   diagnosis. Population estimates from NFHS-5 + Census 2011."  |
+----------------------------------------------------------------+
```

---

## 2. Pages

| Page | Audience | Focus |
|---|---|---|
| **1. India Overview** | Judges, journalists | Heatmap + top-30 table + KPIs |
| **2. State Deep-dive** | Public health officers | One state filter, all districts, scatter |
| **3. Awareness Deserts** | NGO / campaign planners | Bar of top 10 deserts, supporting map |
| **4. Risk Factors** | Researchers | Small multiples: obesity, hypertension, PM2.5 side by side |

Page 1 is the headline. Pages 2-4 are drill-downs.

---

## 3. Calculated fields (BigQuery view)

Already exposed by `backend/bq/schema.sql`. Documented here for the
Looker builder:

| Field | Formula | Notes |
|---|---|---|
| `risk_score` | `0.25*htn_norm + 0.25*obesity_norm + 0.15*age50_norm + 0.10*male_norm + 0.25*pm25_norm` | 0-1, min-max normalized |
| `risk_category` | `CASE WHEN risk_score >= P75 THEN 'HIGH' WHEN risk_score >= P25 THEN 'MODERATE' ELSE 'LOW' END` | thresholds computed in the view |
| `awareness_gap_score` | `risk_score * (1 - awareness_normalized)` | 0-1, the headline metric |
| `is_awareness_desert` | `risk_score > 0.5 AND awareness_normalized < 0.3` | boolean |
| `estimated_undiagnosed` | `total_population * 0.096 * (1 - awareness_normalized)` | anchored to Sharma et al. |

---

## 4. Style guide

- Palette: dark navy background (`#0E1424`), cyan accents (`#4FD1C5`),
  amber for moderate (`#F6AD55`), red for high risk (`#FC8181`).
- Typography: Google Sans / Roboto, 12pt body, 28pt section headers.
- Footer: "BreatheSafe — screening-prioritization, not medical
  diagnosis" must appear on every page.

---

## 5. Sharing

- Publish the report (`Share → Anyone with the link can view`).
- Paste the URL into the SPA's `Looker dashboard` card
  (`frontend/index.html`, section `#looker`) AND into the
  submission form.

---

## 6. Refresh

The view reads from BigQuery. After any re-run of
`scripts/process_data.py` + `bq load`, hit **Refresh data** in Looker
Studio. The Bubble Map re-renders within a few seconds.
