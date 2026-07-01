# One-shot loader: push the processed CSVs to BigQuery so Looker Studio
# (and the existing views) have data to render.
#
# Run from PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\scripts\load_to_bigquery.ps1

$ErrorActionPreference = "Stop"
$Project = if ($env:BQ_PROJECT_ID) { $env:BQ_PROJECT_ID } else { "promptwars-mumbai-499305" }
$Dataset = if ($env:BQ_DATASET) { $env:BQ_DATASET } else { "breathesafe" }
$Proc    = Join-Path $PSScriptRoot "..\backend\data\processed"

$DistrictsCsv = Join-Path $Proc "district_risk_scores.csv"
$StatesCsv    = Join-Path $Proc "state_summary.csv"

Write-Host "`n=== BreatheSafe: Loading processed CSVs to BigQuery ===" -ForegroundColor Cyan
Write-Host "Project : $Project"
Write-Host "Dataset : $Dataset`n"

# 1) Drop the existing views (they reference empty source tables)
foreach ($v in @("district_risk_scores", "state_summary")) {
    $ref = "$Project`:$Dataset.$v"
    Write-Host "  dropping view  $ref" -NoNewline
    bq rm -f $ref 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Host "  OK" -ForegroundColor Green }
    else { Write-Host "  (not present or already dropped)" -ForegroundColor Yellow }
}

# 2) Load district_risk_scores.csv -> table
Write-Host "`n  loading district_risk_scores.csv ..." -NoNewline
bq load --autodetect --source_format=CSV --skip_leading_rows=1 `
        --replace `
        "${Project}:${Dataset}.district_risk_scores" `
        "$DistrictsCsv" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host " OK" -ForegroundColor Green }
else { Write-Host " FAILED" -ForegroundColor Red; exit 1 }

# 3) Load state_summary.csv -> table
Write-Host "  loading state_summary.csv ..." -NoNewline
bq load --autodetect --source_format=CSV --skip_leading_rows=1 `
        --replace `
        "${Project}:${Dataset}.state_summary" `
        "$StatesCsv" 2>&1 | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Host " OK" -ForegroundColor Green }
else { Write-Host " FAILED" -ForegroundColor Red; exit 1 }

# 4) Verify
Write-Host "`n  Verifying row counts:" -ForegroundColor Cyan
bq query --nouse_legacy_sql --format=pretty `
   "SELECT 'district_risk_scores' AS tbl, COUNT(*) AS n FROM `${Project}.${Dataset}.district_risk_scores
    UNION ALL
    SELECT 'state_summary', COUNT(*) FROM `${Project}.${Dataset}.state_summary" 2>&1

Write-Host "`nSample (top 3 by awareness_gap from state_summary):" -ForegroundColor Cyan
bq query --nouse_legacy_sql --format=pretty `
   "SELECT state_name, district_count, high_risk_districts,
           awareness_desert_count, avg_risk_score, avg_awareness_gap
    FROM `${Project}.${Dataset}.state_summary
    ORDER BY avg_awareness_gap DESC
    LIMIT 3" 2>&1

Write-Host "`nDone. In Looker Studio, reconnect to:" -ForegroundColor Green
Write-Host "   BigQuery project : $Project"
Write-Host "   Dataset          : $Dataset"
Write-Host "   Table            : state_summary         (31 rows - best for Looker)"
Write-Host "   Table            : district_risk_scores  (365 rows)"
