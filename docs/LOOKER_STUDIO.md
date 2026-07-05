# BreatheSafe — Looker Studio Dashboard Spec

> Spec for the India district awareness-gap dashboard. Build this once
> after the BigQuery dataset is loaded. The Cloud Run SPA has a card
> linking to the published URL.

**Published URL:** https://datastudio.google.com/reporting/e8879c34-66ef-427c-a8f5-9fb8ef09d20d
*(live link — keep this in sync with the SPA's "Open in Looker ↗" button)*

---

## New: is_small_population field

The `district_risk_scores` view (and local CSV) now includes an
`is_small_population` boolean flag (`True` when population < 200K).
These districts have higher survey margin of error. Use this as a
filter or conditional formatting in Looker Studio.

The default sort is now by `estimated_undiagnosed` DESC (population-aware
impact ranking), not `awareness_gap_score`.

---

## 0. Connect a data source (if rebuilding from scratch)

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
|  365   |  92    |  3 deserts    |  0.306 avg risk               |
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
|  [TABLE — Top 30 districts by estimated_undiagnosed]           |
|   columns: district_name, state_name, risk_score,             |
|            awareness_gap_score, estimated_undiagnosed,         |
|            pm25_annual_mean, pct_adults_overweight_obese,      |
|            pct_adults_hypertension, is_small_population        |
|   sort: estimated_undiagnosed desc                              |
|   conditional formatting: is_small_population = True → grey bg  |
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
|   size: estimated_undiagnosed (was total_population)          |
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
| `awareness_gap_score` | `risk_score * (1 - awareness_normalized)` | 0-1 |
| `is_awareness_desert` | `risk_score > 0.5 AND awareness_normalized < 0.3` | boolean |
| `estimated_undiagnosed` | `total_population * 0.096 * (1 - awareness_normalized)` | anchored to Sharma et al. |
| `is_small_population` | `total_population < 200000` | boolean — filter out for more stable rankings |

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
- Set the report name to **"BreatheSafe — India OSA Screening Intelligence"**
- Paste the URL into the SPA's `Looker dashboard` card
  (`frontend/index.html`, section `#looker`) AND into the
  submission form.

---

## 6. Refresh

The view reads from BigQuery. After any re-run of
`scripts/process_data.py` + `bq load`, hit **Refresh data** in Looker
Studio. The Bubble Map re-renders within a few seconds.

---

## 7. Quick fix for existing report

If the report at the published URL exists but shows "Untitled Report":

1. Open the URL → click **Edit** (pencil icon)
2. Click the report title (top-left) → rename to
   **"BreatheSafe — India OSA Screening Intelligence"**
3. Click **File → Report settings** → verify data source is
   `breathesafe.district_risk_scores`
4. Click **Share → Enable link sharing → Anyone with the link can view**
5. Click **Done**
