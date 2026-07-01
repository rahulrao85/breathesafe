"""
BreatheSafe — Data Acquisition Script
Downloads and prepares all 5 data sources for BigQuery loading.

Data Sources:
1. NFHS-5 district-level health data (GitHub CSV)
2. Census 2011 district demographics (Kaggle CSV — pre-downloaded)
3. OpenAQ / CPCB air quality data (API or pre-downloaded CSV)
4. Google Trends awareness signals (pytrends)
5. STOP-BANG screening model weights (manual JSON)

Usage:
    python scripts/fetch_data.py --all
    python scripts/fetch_data.py --nfhs
    python scripts/fetch_data.py --trends
"""

import os
import json
import csv
import argparse
import urllib.request
import time
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent
RAW_DIR = BASE_DIR / "backend" / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "backend" / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# 1. NFHS-5 District Health Data
# ──────────────────────────────────────────────

NFHS5_URLS = {
    # PratapVardhan's widely-used NFHS-5 repo (district-level CSVs)
    "nfhs5_district": "https://raw.githubusercontent.com/PratapVardhan/NFHS-5/main/data/NFHS-5-district-data.csv",
    # SaiSiddhardhaKalla's repo (more complete, matched to Census codes)
    "nfhs5_indicators": "https://raw.githubusercontent.com/SaiSiddhardhaKalla/NFHS/main/NFHS5/NFHS5_District.csv",
}


def fetch_nfhs5():
    """Download NFHS-5 district-level data from GitHub."""
    print("\n📥 Fetching NFHS-5 data...")
    for name, url in NFHS5_URLS.items():
        outfile = RAW_DIR / f"{name}.csv"
        if outfile.exists():
            print(f"  ✅ {name}.csv already exists, skipping")
            continue
        try:
            print(f"  ⬇️  Downloading {name} from {url[:60]}...")
            urllib.request.urlretrieve(url, outfile)
            # Verify it's valid CSV
            with open(outfile, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                header = next(reader)
                row_count = sum(1 for _ in reader)
            print(f"  ✅ {name}.csv — {len(header)} columns, {row_count} rows")
        except Exception as e:
            print(f"  ❌ Failed to download {name}: {e}")
            print(f"     Manual download: {url}")
            print(f"     Save to: {outfile}")


# ──────────────────────────────────────────────
# 2. Census 2011 District Demographics
# ──────────────────────────────────────────────

CENSUS_URL = "https://raw.githubusercontent.com/deep-dive/data/master/dataset/population_india_census2011.csv"


def fetch_census():
    """Download Census 2011 district-level population data."""
    print("\n📥 Fetching Census 2011 data...")
    outfile = RAW_DIR / "census_2011_districts.csv"
    if outfile.exists():
        print(f"  ✅ census_2011_districts.csv already exists, skipping")
        return
    try:
        print(f"  ⬇️  Downloading from GitHub...")
        urllib.request.urlretrieve(CENSUS_URL, outfile)
        with open(outfile, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader)
            row_count = sum(1 for _ in reader)
        print(f"  ✅ census_2011_districts.csv — {len(header)} columns, {row_count} rows")
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        print(f"     Fallback: Download from Kaggle 'india-census-2011' dataset")
        print(f"     Save to: {outfile}")


# ──────────────────────────────────────────────
# 3. Air Quality (CPCB / OpenAQ)
# ──────────────────────────────────────────────

def generate_synthetic_aqi():
    """
    Generate synthetic but realistic AQI data for priority districts.
    Real OpenAQ API requires key + station-level aggregation.
    For the hackathon demo, we use synthetic data calibrated to
    known Indian AQI patterns (Delhi NCR high, South India lower).
    """
    print("\n📥 Generating synthetic AQI data (calibrated to real patterns)...")
    import random
    random.seed(42)

    # Known AQI patterns by region (annual PM2.5 mean, µg/m³)
    # Source: WHO Global Air Quality Database + CPCB annual reports
    region_baselines = {
        "Delhi NCR": (120, 180),  # Severely polluted
        "Indo-Gangetic Plain": (80, 140),  # Very high
        "Central India": (50, 90),
        "Western India": (40, 70),
        "South India": (25, 50),  # Relatively cleaner
        "Northeast India": (20, 40),
        "Hill States": (15, 35),
    }

    # 50 priority districts with known region mapping
    districts = [
        # Delhi NCR
        {"district": "New Delhi", "state": "Delhi", "region": "Delhi NCR", "lat": 28.6139, "lon": 77.2090},
        {"district": "Gurgaon", "state": "Haryana", "region": "Delhi NCR", "lat": 28.4595, "lon": 77.0266},
        {"district": "Noida (Gautam Buddha Nagar)", "state": "Uttar Pradesh", "region": "Delhi NCR", "lat": 28.5355, "lon": 77.3910},
        {"district": "Ghaziabad", "state": "Uttar Pradesh", "region": "Delhi NCR", "lat": 28.6692, "lon": 77.4538},
        {"district": "Faridabad", "state": "Haryana", "region": "Delhi NCR", "lat": 28.4089, "lon": 77.3178},
        # Indo-Gangetic Plain
        {"district": "Lucknow", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 26.8467, "lon": 80.9462},
        {"district": "Kanpur Nagar", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 26.4499, "lon": 80.3319},
        {"district": "Varanasi", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 25.3176, "lon": 83.0064},
        {"district": "Patna", "state": "Bihar", "region": "Indo-Gangetic Plain", "lat": 25.6093, "lon": 85.1376},
        {"district": "Muzaffarpur", "state": "Bihar", "region": "Indo-Gangetic Plain", "lat": 26.1209, "lon": 85.3647},
        {"district": "Agra", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 27.1767, "lon": 78.0081},
        {"district": "Allahabad (Prayagraj)", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 25.4358, "lon": 81.8463},
        {"district": "Gorakhpur", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 26.7606, "lon": 83.3732},
        {"district": "Bareilly", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 28.3670, "lon": 79.4304},
        {"district": "Moradabad", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 28.8386, "lon": 78.7733},
        # Western India
        {"district": "Mumbai", "state": "Maharashtra", "region": "Western India", "lat": 19.0760, "lon": 72.8777},
        {"district": "Pune", "state": "Maharashtra", "region": "Western India", "lat": 18.5204, "lon": 73.8567},
        {"district": "Ahmedabad", "state": "Gujarat", "region": "Western India", "lat": 23.0225, "lon": 72.5714},
        {"district": "Surat", "state": "Gujarat", "region": "Western India", "lat": 21.1702, "lon": 72.8311},
        {"district": "Nagpur", "state": "Maharashtra", "region": "Central India", "lat": 21.1458, "lon": 79.0882},
        {"district": "Thane", "state": "Maharashtra", "region": "Western India", "lat": 19.2183, "lon": 72.9781},
        {"district": "Nashik", "state": "Maharashtra", "region": "Western India", "lat": 19.9975, "lon": 73.7898},
        {"district": "Jaipur", "state": "Rajasthan", "region": "Western India", "lat": 26.9124, "lon": 75.7873},
        {"district": "Jodhpur", "state": "Rajasthan", "region": "Western India", "lat": 26.2389, "lon": 73.0243},
        # South India
        {"district": "Bengaluru Urban", "state": "Karnataka", "region": "South India", "lat": 12.9716, "lon": 77.5946},
        {"district": "Hyderabad", "state": "Telangana", "region": "South India", "lat": 17.3850, "lon": 78.4867},
        {"district": "Chennai", "state": "Tamil Nadu", "region": "South India", "lat": 13.0827, "lon": 80.2707},
        {"district": "Thiruvananthapuram", "state": "Kerala", "region": "South India", "lat": 8.5241, "lon": 76.9366},
        {"district": "Coimbatore", "state": "Tamil Nadu", "region": "South India", "lat": 11.0168, "lon": 76.9558},
        {"district": "Visakhapatnam", "state": "Andhra Pradesh", "region": "South India", "lat": 17.6868, "lon": 83.2185},
        {"district": "Kochi (Ernakulam)", "state": "Kerala", "region": "South India", "lat": 9.9312, "lon": 76.2673},
        {"district": "Mysuru", "state": "Karnataka", "region": "South India", "lat": 12.2958, "lon": 76.6394},
        # Central India
        {"district": "Bhopal", "state": "Madhya Pradesh", "region": "Central India", "lat": 23.2599, "lon": 77.4126},
        {"district": "Indore", "state": "Madhya Pradesh", "region": "Central India", "lat": 22.7196, "lon": 75.8577},
        {"district": "Raipur", "state": "Chhattisgarh", "region": "Central India", "lat": 21.2514, "lon": 81.6296},
        # East India
        {"district": "Kolkata", "state": "West Bengal", "region": "Indo-Gangetic Plain", "lat": 22.5726, "lon": 88.3639},
        {"district": "Howrah", "state": "West Bengal", "region": "Indo-Gangetic Plain", "lat": 22.5958, "lon": 88.2636},
        # Northeast
        {"district": "Guwahati (Kamrup Metropolitan)", "state": "Assam", "region": "Northeast India", "lat": 26.1445, "lon": 91.7362},
        {"district": "Imphal West", "state": "Manipur", "region": "Northeast India", "lat": 24.8170, "lon": 93.9368},
        # Hill States
        {"district": "Shimla", "state": "Himachal Pradesh", "region": "Hill States", "lat": 31.1048, "lon": 77.1734},
        {"district": "Dehradun", "state": "Uttarakhand", "region": "Hill States", "lat": 30.3165, "lon": 78.0322},
        # Punjab
        {"district": "Ludhiana", "state": "Punjab", "region": "Indo-Gangetic Plain", "lat": 30.9010, "lon": 75.8573},
        {"district": "Amritsar", "state": "Punjab", "region": "Indo-Gangetic Plain", "lat": 31.6340, "lon": 74.8723},
        # Additional UP (high population)
        {"district": "Meerut", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 28.9845, "lon": 77.7064},
        {"district": "Aligarh", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 27.8974, "lon": 78.0880},
        {"district": "Sultanpur", "state": "Uttar Pradesh", "region": "Indo-Gangetic Plain", "lat": 26.2648, "lon": 82.0727},
        # Additional Maharashtra
        {"district": "Aurangabad", "state": "Maharashtra", "region": "Central India", "lat": 19.8762, "lon": 75.3433},
        {"district": "Solapur", "state": "Maharashtra", "region": "Western India", "lat": 17.6599, "lon": 75.9064},
        # Odisha
        {"district": "Bhubaneswar (Khordha)", "state": "Odisha", "region": "Central India", "lat": 20.2961, "lon": 85.8245},
        # Jharkhand
        {"district": "Ranchi", "state": "Jharkhand", "region": "Central India", "lat": 23.3441, "lon": 85.3096},
    ]

    rows = []
    for d in districts:
        lo, hi = region_baselines[d["region"]]
        pm25 = round(random.uniform(lo, hi), 1)
        rows.append({
            "district": d["district"],
            "state": d["state"],
            "latitude": d["lat"],
            "longitude": d["lon"],
            "pm25_annual_mean": pm25,
            "aqi_category": (
                "Good" if pm25 < 30 else
                "Satisfactory" if pm25 < 60 else
                "Moderate" if pm25 < 90 else
                "Poor" if pm25 < 120 else
                "Very Poor" if pm25 < 250 else
                "Severe"
            ),
            "data_source": "synthetic_calibrated_to_cpcb",
            "year": 2024,
        })

    outfile = RAW_DIR / "air_quality_districts.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✅ air_quality_districts.csv — {len(rows)} districts")


# ──────────────────────────────────────────────
# 4. Google Trends — Awareness Signals
# ──────────────────────────────────────────────

def fetch_trends():
    """
    Fetch Google Trends data for sleep apnea awareness.
    Falls back to synthetic data if pytrends is not installed.
    """
    print("\n📥 Fetching Google Trends awareness data...")

    try:
        from pytrends.request import TrendReq
        print("  📊 Using pytrends for real data...")
        pytrends = TrendReq(hl="en-US", tz=330)  # IST offset

        keywords = ["sleep apnea", "snoring", "CPAP"]
        pytrends.build_payload(keywords, timeframe="today 12-m", geo="IN")
        data = pytrends.interest_by_region(resolution="REGION", inc_low_vol=True)

        rows = []
        for state, row in data.iterrows():
            rows.append({
                "state": state,
                "sleep_apnea_interest": int(row.get("sleep apnea", 0)),
                "snoring_interest": int(row.get("snoring", 0)),
                "cpap_interest": int(row.get("CPAP", 0)),
                "data_source": "google_trends_api",
                "period": "last_12_months",
            })

        outfile = RAW_DIR / "trends_awareness.csv"
        with open(outfile, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        print(f"  ✅ trends_awareness.csv — {len(rows)} states (real Google Trends)")

    except ImportError:
        print("  ⚠️  pytrends not installed, generating calibrated synthetic data")
        _generate_synthetic_trends()
    except Exception as e:
        print(f"  ⚠️  pytrends failed ({e}), generating calibrated synthetic data")
        _generate_synthetic_trends()


def _generate_synthetic_trends():
    """
    Generate synthetic but realistic Google Trends data.
    Pattern: metros have higher awareness, rural/Hindi belt much lower.
    """
    import random
    random.seed(99)

    # Calibrated: metros search more for "sleep apnea", 
    # Hindi heartland barely searches at all
    states_data = {
        # (sleep_apnea_interest, snoring_interest, cpap_interest)
        # Scale: 0-100 (Google Trends relative scale)
        "Maharashtra": (72, 65, 55),
        "Karnataka": (85, 70, 68),
        "Delhi": (100, 80, 75),
        "Tamil Nadu": (68, 58, 50),
        "Telangana": (78, 62, 58),
        "Kerala": (65, 55, 45),
        "Gujarat": (45, 40, 30),
        "West Bengal": (40, 38, 25),
        "Rajasthan": (18, 22, 8),
        "Uttar Pradesh": (12, 20, 5),
        "Bihar": (8, 15, 3),
        "Madhya Pradesh": (15, 18, 6),
        "Andhra Pradesh": (55, 48, 38),
        "Punjab": (30, 35, 20),
        "Haryana": (35, 38, 22),
        "Odisha": (20, 22, 10),
        "Jharkhand": (10, 14, 4),
        "Chhattisgarh": (12, 16, 5),
        "Assam": (15, 18, 6),
        "Uttarakhand": (28, 30, 15),
        "Himachal Pradesh": (25, 28, 12),
        "Goa": (60, 55, 42),
        "Manipur": (8, 10, 2),
        "Meghalaya": (6, 8, 2),
        "Tripura": (7, 9, 2),
        "Mizoram": (5, 7, 1),
        "Nagaland": (5, 7, 1),
        "Arunachal Pradesh": (4, 6, 1),
        "Sikkim": (10, 12, 4),
        "Jammu and Kashmir": (18, 20, 8),
        "Ladakh": (5, 6, 2),
        "Puducherry": (45, 40, 30),
        "Chandigarh": (55, 50, 38),
        "Dadra and Nagar Haveli and Daman and Diu": (12, 14, 5),
        "Andaman and Nicobar Islands": (8, 10, 3),
        "Lakshadweep": (3, 4, 1),
    }

    rows = []
    for state, (sa, sn, cp) in states_data.items():
        # Add slight randomness
        rows.append({
            "state": state,
            "sleep_apnea_interest": sa + random.randint(-3, 3),
            "snoring_interest": sn + random.randint(-3, 3),
            "cpap_interest": cp + random.randint(-2, 2),
            "data_source": "synthetic_calibrated",
            "period": "last_12_months",
        })

    outfile = RAW_DIR / "trends_awareness.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  ✅ trends_awareness.csv — {len(rows)} states (synthetic calibrated)")


# ──────────────────────────────────────────────
# 5. STOP-BANG Screening Model Weights
# ──────────────────────────────────────────────

def create_screening_model():
    """
    Create the STOP-BANG-derived population risk model weights.
    These weights are adapted from published literature for
    population-level proxy application.
    """
    print("\n📥 Creating STOP-BANG population risk model...")

    model = {
        "model_name": "STOP-BANG Population Risk Index (BreatheSafe)",
        "version": "1.0",
        "description": (
            "Adapted from the STOP-BANG clinical screening questionnaire "
            "(Chung et al., 2008) for population-level risk estimation. "
            "Uses district-level proxy indicators instead of individual measurements. "
            "NOT a diagnostic tool — designed for screening camp prioritization."
        ),
        "citation": "Chung F, et al. STOP questionnaire: a tool to screen patients for OSA. Anesthesiology. 2008;108(5):812-821.",
        "asian_adjustments": "BMI threshold lowered from 35 to 25 kg/m² per Asian population guidelines (WHO Expert Consultation, 2004).",
        "factors": [
            {
                "code": "P",
                "name": "Pressure (Hypertension)",
                "proxy": "pct_adults_hypertension",
                "source": "NFHS-5",
                "weight": 0.25,
                "normalization": "min-max across districts",
                "rationale": "Hypertension is the strongest STOP-BANG correlate with OSA at population level"
            },
            {
                "code": "B",
                "name": "BMI (Obesity)",
                "proxy": "pct_adults_overweight_obese",
                "source": "NFHS-5",
                "weight": 0.25,
                "normalization": "min-max across districts",
                "rationale": "Obesity (BMI ≥ 25 for Asian populations) is the #1 modifiable risk factor for OSA"
            },
            {
                "code": "A",
                "name": "Age > 50",
                "proxy": "pct_population_age_50plus",
                "source": "Census 2011",
                "weight": 0.15,
                "normalization": "min-max across districts",
                "rationale": "OSA prevalence increases significantly after age 50"
            },
            {
                "code": "G",
                "name": "Gender (Male)",
                "proxy": "pct_male",
                "source": "Census 2011",
                "weight": 0.10,
                "normalization": "min-max across districts",
                "rationale": "Male sex is an independent risk factor (2-3x higher prevalence)"
            },
            {
                "code": "AQ",
                "name": "Air Quality (PM2.5)",
                "proxy": "pm25_annual_mean",
                "source": "OpenAQ/CPCB",
                "weight": 0.25,
                "normalization": "min-max across districts",
                "rationale": "Chronic air pollution exposure aggravates upper airway inflammation and OSA severity (Billings et al., 2019)"
            }
        ],
        "omitted_factors": [
            {"code": "S", "name": "Snoring", "reason": "No population-level proxy; used as awareness signal instead"},
            {"code": "T", "name": "Tired", "reason": "No population-level proxy available in public datasets"},
            {"code": "O", "name": "Observed apnea", "reason": "No population-level proxy available"},
            {"code": "N", "name": "Neck circumference", "reason": "No population-level anthropometric data at district level"}
        ],
        "awareness_gap_formula": "awareness_gap = risk_score × (1 - awareness_normalized)",
        "awareness_source": "Google Trends search interest for 'sleep apnea' + 'snoring' + 'CPAP' by state",
        "interpretation": {
            "risk_score_range": [0.0, 1.0],
            "low_risk": [0.0, 0.3],
            "moderate_risk": [0.3, 0.6],
            "high_risk": [0.6, 1.0],
            "awareness_desert": "risk_score > 0.5 AND awareness_normalized < 0.3"
        }
    }

    outfile = RAW_DIR / "stopbang_model.json"
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=2)
    print(f"  ✅ stopbang_model.json — {len(model['factors'])} active factors, {len(model['omitted_factors'])} omitted")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BreatheSafe Data Acquisition")
    parser.add_argument("--all", action="store_true", help="Fetch all data sources")
    parser.add_argument("--nfhs", action="store_true", help="Fetch NFHS-5 data only")
    parser.add_argument("--census", action="store_true", help="Fetch Census data only")
    parser.add_argument("--aqi", action="store_true", help="Generate AQI data")
    parser.add_argument("--trends", action="store_true", help="Fetch Google Trends data")
    parser.add_argument("--model", action="store_true", help="Create screening model weights")
    args = parser.parse_args()

    if args.all or not any(vars(args).values()):
        args.nfhs = args.census = args.aqi = args.trends = args.model = True

    print("=" * 60)
    print("🫁 BreatheSafe — Data Acquisition Pipeline")
    print("=" * 60)

    if args.nfhs:
        fetch_nfhs5()
    if args.census:
        fetch_census()
    if args.aqi:
        generate_synthetic_aqi()
    if args.trends:
        fetch_trends()
    if args.model:
        create_screening_model()

    print("\n" + "=" * 60)
    print("✅ Data acquisition complete!")
    print(f"📁 Raw data saved to: {RAW_DIR}")
    print("=" * 60)
    print("\nNext step: python scripts/process_data.py")


if __name__ == "__main__":
    main()
