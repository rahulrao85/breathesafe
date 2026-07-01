-- ============================================================
-- BreatheSafe — BigQuery Schema & Risk Scoring Pipeline
-- Dataset: breathesafe
-- ============================================================

-- 1. Create dataset
-- CREATE SCHEMA IF NOT EXISTS `breathesafe`
--   OPTIONS (location = 'asia-south1');  -- Mumbai region


-- ============================================================
-- TABLE 1: Health Survey (NFHS-5)
-- ============================================================
CREATE OR REPLACE TABLE `breathesafe.health_survey` (
  district_id       STRING NOT NULL,    -- Census 2011 district code
  district_name     STRING NOT NULL,
  state_name        STRING NOT NULL,
  -- OSA risk factors from NFHS-5
  pct_men_overweight_obese    FLOAT64,  -- Men BMI >= 25 (Asian threshold)
  pct_women_overweight_obese  FLOAT64,  -- Women BMI >= 25
  pct_adults_overweight_obese FLOAT64,  -- Average of men + women
  pct_men_hypertension        FLOAT64,  -- Men SBP >= 140 or DBP >= 90
  pct_women_hypertension      FLOAT64,
  pct_adults_hypertension     FLOAT64,  -- Average
  pct_men_high_blood_sugar    FLOAT64,  -- Diabetes comorbidity
  pct_women_high_blood_sugar  FLOAT64,
  pct_tobacco_use_men         FLOAT64,  -- Smoking = additional risk factor
  pct_tobacco_use_women       FLOAT64,
  -- Metadata
  survey_year       INT64 DEFAULT 2021,
  data_source       STRING DEFAULT 'NFHS-5',
  loaded_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================
-- TABLE 2: Demographics (Census 2011)
-- ============================================================
CREATE OR REPLACE TABLE `breathesafe.demographics` (
  district_id         STRING NOT NULL,
  district_name       STRING NOT NULL,
  state_name          STRING NOT NULL,
  total_population    INT64,
  male_population     INT64,
  female_population   INT64,
  pct_male            FLOAT64,
  pct_urban           FLOAT64,        -- Urbanization rate
  population_density  FLOAT64,        -- per sq km
  literacy_rate       FLOAT64,
  -- Age brackets (from Census age tables)
  pct_age_0_14        FLOAT64,
  pct_age_15_49       FLOAT64,
  pct_age_50_plus     FLOAT64,        -- Key OSA risk factor
  -- Geospatial
  latitude            FLOAT64,
  longitude           FLOAT64,
  geo_point           GEOGRAPHY,      -- ST_GEOGPOINT(longitude, latitude)
  -- Metadata
  census_year         INT64 DEFAULT 2011,
  data_source         STRING DEFAULT 'Census_2011',
  loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================
-- TABLE 3: Air Quality
-- ============================================================
CREATE OR REPLACE TABLE `breathesafe.air_quality` (
  district_name       STRING NOT NULL,
  state_name          STRING NOT NULL,
  latitude            FLOAT64,
  longitude           FLOAT64,
  pm25_annual_mean    FLOAT64,        -- µg/m³
  aqi_category        STRING,         -- Good/Satisfactory/Moderate/Poor/Very Poor/Severe
  data_year           INT64,
  data_source         STRING,
  loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================
-- TABLE 4: Awareness Signals (Google Trends)
-- ============================================================
CREATE OR REPLACE TABLE `breathesafe.awareness_signals` (
  state_name              STRING NOT NULL,
  sleep_apnea_interest    INT64,    -- 0-100 relative scale
  snoring_interest        INT64,
  cpap_interest           INT64,
  composite_awareness     FLOAT64,  -- Weighted average of all three
  data_source             STRING,
  period                  STRING,   -- e.g., "last_12_months"
  loaded_at               TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================
-- TABLE 5: Screening Model Parameters
-- ============================================================
CREATE OR REPLACE TABLE `breathesafe.screening_model` (
  factor_code     STRING NOT NULL,
  factor_name     STRING,
  proxy_column    STRING,
  source_table    STRING,
  weight          FLOAT64,
  rationale       STRING,
  loaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);


-- ============================================================
-- VIEW: District Risk Scores (THE MAIN JOIN)
-- This is where all 5 data sources come together.
-- ============================================================
CREATE OR REPLACE VIEW `breathesafe.district_risk_scores` AS
WITH

-- Step 1: Normalize each risk factor to 0-1 across all districts
health_normalized AS (
  SELECT
    district_id,
    district_name,
    state_name,
    pct_adults_overweight_obese,
    pct_adults_hypertension,
    -- Min-max normalize obesity
    (pct_adults_overweight_obese - MIN(pct_adults_overweight_obese) OVER()) /
      NULLIF(MAX(pct_adults_overweight_obese) OVER() - MIN(pct_adults_overweight_obese) OVER(), 0)
      AS obesity_normalized,
    -- Min-max normalize hypertension
    (pct_adults_hypertension - MIN(pct_adults_hypertension) OVER()) /
      NULLIF(MAX(pct_adults_hypertension) OVER() - MIN(pct_adults_hypertension) OVER(), 0)
      AS hypertension_normalized
  FROM `breathesafe.health_survey`
),

demo_normalized AS (
  SELECT
    district_id,
    district_name,
    state_name,
    total_population,
    pct_male,
    pct_age_50_plus,
    pct_urban,
    latitude,
    longitude,
    -- Normalize age 50+
    (pct_age_50_plus - MIN(pct_age_50_plus) OVER()) /
      NULLIF(MAX(pct_age_50_plus) OVER() - MIN(pct_age_50_plus) OVER(), 0)
      AS age50_normalized,
    -- Normalize male %
    (pct_male - MIN(pct_male) OVER()) /
      NULLIF(MAX(pct_male) OVER() - MIN(pct_male) OVER(), 0)
      AS male_normalized
  FROM `breathesafe.demographics`
),

aqi_normalized AS (
  SELECT
    district_name,
    state_name,
    pm25_annual_mean,
    (pm25_annual_mean - MIN(pm25_annual_mean) OVER()) /
      NULLIF(MAX(pm25_annual_mean) OVER() - MIN(pm25_annual_mean) OVER(), 0)
      AS pm25_normalized
  FROM `breathesafe.air_quality`
),

awareness AS (
  SELECT
    state_name,
    -- Composite awareness: weighted average of search terms
    (0.5 * sleep_apnea_interest + 0.3 * snoring_interest + 0.2 * cpap_interest) / 100.0
      AS awareness_normalized
  FROM `breathesafe.awareness_signals`
)

-- Step 2: The Big Join
SELECT
  h.district_id,
  h.district_name,
  h.state_name,
  d.total_population,
  d.pct_urban,
  d.latitude,
  d.longitude,

  -- Raw values for display
  h.pct_adults_overweight_obese,
  h.pct_adults_hypertension,
  d.pct_age_50_plus,
  d.pct_male,
  aq.pm25_annual_mean,
  a.awareness_normalized,

  -- STOP-BANG Population Risk Score (weighted sum of normalized factors)
  ROUND(
    (0.25 * COALESCE(h.hypertension_normalized, 0)) +
    (0.25 * COALESCE(h.obesity_normalized, 0)) +
    (0.15 * COALESCE(d.age50_normalized, 0)) +
    (0.10 * COALESCE(d.male_normalized, 0)) +
    (0.25 * COALESCE(aq.pm25_normalized, 0)),
    4
  ) AS risk_score,

  -- Risk category
  CASE
    WHEN (
      (0.25 * COALESCE(h.hypertension_normalized, 0)) +
      (0.25 * COALESCE(h.obesity_normalized, 0)) +
      (0.15 * COALESCE(d.age50_normalized, 0)) +
      (0.10 * COALESCE(d.male_normalized, 0)) +
      (0.25 * COALESCE(aq.pm25_normalized, 0))
    ) >= 0.6 THEN 'HIGH'
    WHEN (
      (0.25 * COALESCE(h.hypertension_normalized, 0)) +
      (0.25 * COALESCE(h.obesity_normalized, 0)) +
      (0.15 * COALESCE(d.age50_normalized, 0)) +
      (0.10 * COALESCE(d.male_normalized, 0)) +
      (0.25 * COALESCE(aq.pm25_normalized, 0))
    ) >= 0.3 THEN 'MODERATE'
    ELSE 'LOW'
  END AS risk_category,

  -- Awareness gap = high risk + low awareness = screening priority
  ROUND(
    (
      (0.25 * COALESCE(h.hypertension_normalized, 0)) +
      (0.25 * COALESCE(h.obesity_normalized, 0)) +
      (0.15 * COALESCE(d.age50_normalized, 0)) +
      (0.10 * COALESCE(d.male_normalized, 0)) +
      (0.25 * COALESCE(aq.pm25_normalized, 0))
    ) * (1 - COALESCE(a.awareness_normalized, 0)),
    4
  ) AS awareness_gap_score,

  -- Estimated undiagnosed cases (rough: population × prevalence estimate × (1 - awareness))
  -- Using 9.6% as India's estimated OSA prevalence (Sharma et al., Lancet Respiratory Medicine, 2019)
  ROUND(
    d.total_population * 0.096 * (1 - COALESCE(a.awareness_normalized, 0))
  ) AS estimated_undiagnosed,

  -- Is this an "awareness desert"?
  CASE
    WHEN (
      (0.25 * COALESCE(h.hypertension_normalized, 0)) +
      (0.25 * COALESCE(h.obesity_normalized, 0)) +
      (0.15 * COALESCE(d.age50_normalized, 0)) +
      (0.10 * COALESCE(d.male_normalized, 0)) +
      (0.25 * COALESCE(aq.pm25_normalized, 0))
    ) > 0.5
    AND COALESCE(a.awareness_normalized, 0) < 0.3
    THEN TRUE
    ELSE FALSE
  END AS is_awareness_desert

FROM health_normalized h
JOIN demo_normalized d ON h.district_id = d.district_id
LEFT JOIN aqi_normalized aq ON LOWER(TRIM(h.district_name)) = LOWER(TRIM(aq.district_name))
  AND LOWER(TRIM(h.state_name)) = LOWER(TRIM(aq.state_name))
LEFT JOIN awareness a ON LOWER(TRIM(h.state_name)) = LOWER(TRIM(a.state_name))

ORDER BY awareness_gap_score DESC;


-- ============================================================
-- VIEW: State-Level Summary (for Looker dashboard)
-- ============================================================
CREATE OR REPLACE VIEW `breathesafe.state_summary` AS
SELECT
  state_name,
  COUNT(*) AS district_count,
  ROUND(AVG(risk_score), 3) AS avg_risk_score,
  ROUND(AVG(awareness_gap_score), 3) AS avg_awareness_gap,
  SUM(estimated_undiagnosed) AS total_estimated_undiagnosed,
  COUNTIF(is_awareness_desert) AS awareness_desert_count,
  COUNTIF(risk_category = 'HIGH') AS high_risk_districts,
  COUNTIF(risk_category = 'MODERATE') AS moderate_risk_districts,
  COUNTIF(risk_category = 'LOW') AS low_risk_districts,
  ROUND(AVG(pm25_annual_mean), 1) AS avg_pm25,
  ROUND(AVG(pct_adults_hypertension), 1) AS avg_hypertension_pct,
  ROUND(AVG(pct_adults_overweight_obese), 1) AS avg_obesity_pct,
  ROUND(AVG(awareness_normalized), 3) AS avg_awareness
FROM `breathesafe.district_risk_scores`
GROUP BY state_name
ORDER BY avg_awareness_gap DESC;


-- ============================================================
-- QUERY: Top 20 Screening Camp Priorities
-- (This is what the ADK agent will call)
-- ============================================================
-- SELECT
--   district_name,
--   state_name,
--   risk_score,
--   awareness_gap_score,
--   estimated_undiagnosed,
--   risk_category,
--   is_awareness_desert,
--   pm25_annual_mean,
--   pct_adults_hypertension,
--   pct_adults_overweight_obese,
--   pct_age_50_plus,
--   awareness_normalized
-- FROM `breathesafe.district_risk_scores`
-- WHERE is_awareness_desert = TRUE
-- ORDER BY awareness_gap_score DESC
-- LIMIT 20;
