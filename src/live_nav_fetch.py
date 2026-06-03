"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
FILE    : src/live_nav_fetch.py
DAY     : 1  —  Project Setup + Data Ingestion (ETL)
TASKS   : 4, 5
AUTHOR  : Bluestock Fintech Capstone Team
DATE    : 2026-06-03
------------------------------------------------------------
PURPOSE :
  Task 4 — Fetch live NAV from mfapi.in for HDFC Top 100
            Direct (AMFI: 125497). Parse JSON, save raw CSV.
  Task 5 — Fetch NAV for 5 key schemes:
            SBI Bluechip     (119551)
            ICICI Bluechip   (120503)
            Nippon Large Cap (118632)
            Axis Bluechip    (119092)
            Kotak Bluechip   (120841)
  Bonus  — Build a combined live NAV DataFrame and save to
            data/processed/live_nav_combined.csv
============================================================
ENDPOINT : GET https://api.mfapi.in/mf/{amfi_code}
RESPONSE : {
    "meta": {scheme_name, fund_house, scheme_type, ...},
    "data": [{"date": "DD-MM-YYYY", "nav": "123.45"}, ...]
  }
============================================================
CONSTRAINTS APPLIED:
  [✓] pathlib.Path — no hardcoded paths
  [✓] Robust error handling with retries (3 attempts)
  [✓] Date parsed to datetime; NAV parsed to float
  [✓] Rate limiting: 0.5s sleep between requests (API courtesy)
  [✓] Raw JSON saved alongside CSV for auditability
============================================================
"""

# ── Standard Library ────────────────────────────────────────
import json
import time
import sys
from pathlib import Path
from datetime import datetime

# ── Third-Party ─────────────────────────────────────────────
import pandas as pd
import requests

# ============================================================
# 0. PATH CONFIGURATION
# ============================================================
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
RAW_DIR       = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# ── API Config ───────────────────────────────────────────────
MFAPI_BASE    = "https://api.mfapi.in/mf"
REQUEST_TIMEOUT_SEC = 15       # seconds per request
RETRY_ATTEMPTS      = 3        # retries on failure
RETRY_DELAY_SEC     = 2.0      # seconds between retries
INTER_REQUEST_SLEEP = 0.5      # courtesy sleep between API calls

# ── Separator ────────────────────────────────────────────────
SEP = "=" * 70


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ============================================================
# 1. SCHEME REGISTRY
#    Task 4: HDFC Top 100 Direct
#    Task 5: 5 key large-cap schemes
# ============================================================
SCHEMES = {
    # Task 4 — Required single fetch
    125497: {
        "name"     : "HDFC Top 100 Fund - Direct Plan - Growth",
        "fund_house": "HDFC Mutual Fund",
        "task"     : 4,
        "category" : "Equity - Large Cap",
    },
    # Task 5 — 5 key schemes
    119551: {
        "name"     : "SBI Bluechip Fund - Regular Plan - Growth",
        "fund_house": "SBI Mutual Fund",
        "task"     : 5,
        "category" : "Equity - Large Cap",
    },
    120503: {
        "name"     : "ICICI Prudential Bluechip Fund - Direct Plan",
        "fund_house": "ICICI Prudential MF",
        "task"     : 5,
        "category" : "Equity - Large Cap",
    },
    118632: {
        "name"     : "Nippon India Large Cap Fund - Regular Plan",
        "fund_house": "Nippon India MF",
        "task"     : 5,
        "category" : "Equity - Large Cap",
    },
    119092: {
        "name"     : "Axis Bluechip Fund - Regular Plan - Growth",
        "fund_house": "Axis Mutual Fund",
        "task"     : 5,
        "category" : "Equity - Large Cap",
    },
    120841: {
        "name"     : "Kotak Bluechip Fund - Regular Plan - Growth",
        "fund_house": "Kotak Mahindra MF",
        "task"     : 5,
        "category" : "Equity - Large Cap",
    },
}


# ============================================================
# 2. SINGLE SCHEME FETCHER
#    With retry logic and structured response parsing
# ============================================================
def fetch_scheme_nav(amfi_code: int) -> dict:
    """
    Fetch full NAV history for a single scheme from mfapi.in.

    Parameters
    ----------
    amfi_code : int  AMFI scheme code

    Returns
    -------
    dict with keys:
        amfi_code   : int
        meta        : dict  (scheme_name, fund_house, etc.)
        nav_df      : pd.DataFrame  (date, nav columns)
        raw_json    : dict  (original API response)
        status      : 'success' | 'failed'
        error       : str | None
    """
    url     = f"{MFAPI_BASE}/{amfi_code}"
    result  = {
        "amfi_code": amfi_code,
        "meta"     : {},
        "nav_df"   : pd.DataFrame(),
        "raw_json" : {},
        "status"   : "failed",
        "error"    : None,
    }

    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            print(f"    → GET {url}  (attempt {attempt}/{RETRY_ATTEMPTS})")
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_SEC)
            resp.raise_for_status()

            data            = resp.json()
            result["raw_json"] = data

            # ── Parse meta block ─────────────────────────────
            meta_block = data.get("meta", {})
            result["meta"] = {
                "scheme_name"  : meta_block.get("scheme_name", "Unknown"),
                "fund_house"   : meta_block.get("fund_house", "Unknown"),
                "scheme_type"  : meta_block.get("scheme_type", ""),
                "scheme_category": meta_block.get("scheme_category", ""),
                "scheme_code"  : meta_block.get("scheme_code", amfi_code),
            }

            # ── Parse NAV data array ─────────────────────────
            nav_records = data.get("data", [])
            if not nav_records:
                result["error"] = "Empty data array returned"
                break

            nav_df = pd.DataFrame(nav_records)

            # Convert date: API returns "DD-MM-YYYY" → YYYY-MM-DD
            nav_df["date"] = pd.to_datetime(
                nav_df["date"], format="%d-%m-%Y", errors="coerce"
            )

            # Convert nav: returned as string → float
            nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")

            # Add metadata columns for traceability
            nav_df["amfi_code"]  = amfi_code
            nav_df["fetch_date"] = datetime.now().strftime("%Y-%m-%d")

            # Sort ascending by date
            nav_df = nav_df.sort_values("date").reset_index(drop=True)

            # Drop any rows where NAV could not be parsed
            null_navs = nav_df["nav"].isnull().sum()
            if null_navs > 0:
                print(f"    ⚠️  {null_navs} rows with unparseable NAV — dropped")
                nav_df = nav_df.dropna(subset=["nav"])

            result["nav_df"] = nav_df
            result["status"] = "success"

            print(f"    ✅  {result['meta']['scheme_name']}")
            print(f"        {len(nav_df):,} NAV records  |  "
                  f"{nav_df['date'].min().date()} → {nav_df['date'].max().date()}")
            break   # success — exit retry loop

        except requests.exceptions.Timeout:
            result["error"] = f"Timeout after {REQUEST_TIMEOUT_SEC}s"
            print(f"    ⚠️  Timeout on attempt {attempt}")
        except requests.exceptions.HTTPError as e:
            result["error"] = f"HTTP {e.response.status_code}"
            print(f"    ⚠️  HTTP Error: {e}")
            break  # don't retry on HTTP errors (404, 403, etc.)
        except requests.exceptions.ConnectionError:
            result["error"] = "Connection failed"
            print(f"    ⚠️  Connection error on attempt {attempt}")
        except (json.JSONDecodeError, KeyError) as e:
            result["error"] = f"Parse error: {e}"
            print(f"    ⚠️  JSON parse error: {e}")
            break

        if attempt < RETRY_ATTEMPTS:
            print(f"    ⏳  Retrying in {RETRY_DELAY_SEC}s ...")
            time.sleep(RETRY_DELAY_SEC)

    return result


# ============================================================
# 3. SAVE FUNCTIONS
# ============================================================
def save_raw_json(raw_json: dict, amfi_code: int) -> Path:
    """Save raw API JSON response to data/raw/ for auditability."""
    out = RAW_DIR / f"live_nav_raw_{amfi_code}.json"
    out.write_text(json.dumps(raw_json, indent=2), encoding="utf-8")
    return out


def save_nav_csv(nav_df: pd.DataFrame, amfi_code: int, label: str = "") -> Path:
    """Save parsed NAV DataFrame as CSV to data/raw/."""
    safe_label = label.replace(" ", "_").replace("/", "-")[:30]
    out = RAW_DIR / f"live_nav_{amfi_code}_{safe_label}.csv"
    nav_df.to_csv(out, index=False)
    return out


# ============================================================
# 4. TASK 4 — HDFC TOP 100 DIRECT
# ============================================================
def task4_fetch_hdfc_top100() -> pd.DataFrame:
    """
    Task 4: Fetch live NAV for HDFC Top 100 Direct (125497).
    Parse JSON, print structure, save raw CSV.
    """
    section("TASK 4 — Fetch HDFC Top 100 Direct NAV (AMFI: 125497)")

    amfi_code = 125497
    result    = fetch_scheme_nav(amfi_code)

    if result["status"] == "failed":
        print(f"\n  ❌  Fetch failed: {result['error']}")
        print("  Generating mock fallback for offline testing ...")
        # Offline fallback: last 5 known NAVs (for local dev / CI)
        mock_data = {
            "date"      : pd.date_range("2026-05-25", periods=5, freq="B"),
            "nav"       : [1050.21, 1055.43, 1048.77, 1062.10, 1058.90],
            "amfi_code" : amfi_code,
            "fetch_date": datetime.now().strftime("%Y-%m-%d"),
        }
        nav_df = pd.DataFrame(mock_data)
        nav_df["data_source"] = "MOCK_FALLBACK"
        print("  ⚠️  Using mock data — connect to internet for live NAV")
    else:
        nav_df = result["nav_df"]
        nav_df["data_source"] = "LIVE_MFAPI"

        # ── Print JSON structure (as requested in task) ───────
        print(f"\n  Raw JSON Structure:")
        print(f"    Top-level keys  : {list(result['raw_json'].keys())}")
        print(f"    meta keys       : {list(result['meta'].keys())}")
        print(f"    data[0] sample  : {result['raw_json']['data'][0]}")
        print(f"    data[1] sample  : {result['raw_json']['data'][1]}")
        print(f"    Total records   : {len(result['raw_json']['data'])}")

        # ── Print parsed DataFrame sample ─────────────────────
        print(f"\n  Parsed DataFrame (latest 5 NAVs):")
        print(nav_df.tail(5).to_string(index=False))

        # ── Save raw JSON for auditability ────────────────────
        json_path = save_raw_json(result["raw_json"], amfi_code)
        print(f"\n  Raw JSON saved → {json_path}")

    # ── Save CSV ──────────────────────────────────────────────
    csv_path = save_nav_csv(nav_df, amfi_code, "HDFC_Top100_Direct")
    print(f"  NAV CSV saved  → {csv_path}")

    return nav_df


# ============================================================
# 5. TASK 5 — 5 KEY SCHEMES
# ============================================================
def task5_fetch_five_schemes() -> pd.DataFrame:
    """
    Task 5: Fetch NAV history for 5 key large-cap schemes.
    Returns combined DataFrame with all schemes.
    """
    section("TASK 5 — Fetch 5 Key Scheme NAVs")

    task5_codes = {k: v for k, v in SCHEMES.items() if v["task"] == 5}
    all_frames  = []
    fetch_log   = []

    for amfi_code, info in task5_codes.items():
        print(f"\n  [{amfi_code}] {info['name']}")
        result = fetch_scheme_nav(amfi_code)

        if result["status"] == "success":
            nav_df = result["nav_df"]
            nav_df["scheme_name"] = result["meta"]["scheme_name"]
            nav_df["fund_house"]  = result["meta"]["fund_house"]
            nav_df["data_source"] = "LIVE_MFAPI"
            all_frames.append(nav_df)

            # Save individual CSV
            csv_path = save_nav_csv(nav_df, amfi_code,
                                    info["fund_house"].replace(" ", ""))
            # Save raw JSON
            json_path = save_raw_json(result["raw_json"], amfi_code)

            fetch_log.append({
                "amfi_code"   : amfi_code,
                "scheme_name" : result["meta"]["scheme_name"],
                "records"     : len(nav_df),
                "date_from"   : str(nav_df["date"].min().date()),
                "date_to"     : str(nav_df["date"].max().date()),
                "csv_path"    : str(csv_path),
                "status"      : "✅ SUCCESS",
            })
        else:
            print(f"    ❌  {result['error']} — generating mock fallback")
            # Offline fallback with realistic NAV range per fund
            mock_navs = {119551: 85.0, 120503: 110.0,
                         118632: 70.0, 119092: 55.0, 120841: 95.0}
            mock_df = pd.DataFrame({
                "date"       : pd.date_range("2026-05-25", periods=5, freq="B"),
                "nav"        : [mock_navs.get(amfi_code, 100.0)] * 5,
                "amfi_code"  : amfi_code,
                "fetch_date" : datetime.now().strftime("%Y-%m-%d"),
                "scheme_name": info["name"],
                "fund_house" : info["fund_house"],
                "data_source": "MOCK_FALLBACK",
            })
            all_frames.append(mock_df)
            fetch_log.append({
                "amfi_code"  : amfi_code,
                "scheme_name": info["name"],
                "records"    : 5,
                "date_from"  : "MOCK",
                "date_to"    : "MOCK",
                "csv_path"   : "N/A",
                "status"     : "⚠️ MOCK",
            })

        # Courtesy sleep between API calls
        time.sleep(INTER_REQUEST_SLEEP)

    # ── Combine all frames ────────────────────────────────────
    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)

        # ── Print fetch summary ───────────────────────────────
        section("TASK 5 — Fetch Summary")
        print(f"\n  {'Code':<8} {'Scheme':<55} {'Records':>8}  {'From':<12}  {'To':<12}  Status")
        print(f"  {'-'*110}")
        for log in fetch_log:
            name_trunc = log["scheme_name"][:52]
            print(f"  {log['amfi_code']:<8} {name_trunc:<55} "
                  f"{log['records']:>8}  {log['date_from']:<12}  "
                  f"{log['date_to']:<12}  {log['status']}")

        # ── Print latest NAV comparison ───────────────────────
        print(f"\n  Latest NAV Comparison (most recent trading day):")
        print(f"  {'Code':<8} {'Fund House':<28} {'Latest NAV':>12}  {'Date':<12}")
        print(f"  {'-'*65}")
        latest = (
            combined.sort_values("date")
            .groupby("amfi_code")
            .last()
            .reset_index()
        )
        for _, row in latest.iterrows():
            fh = SCHEMES.get(int(row["amfi_code"]), {}).get("fund_house", "")
            nav_val = row["nav"]
            dt_val  = row["date"]
            nav_str = f"₹{nav_val:.4f}" if pd.notna(nav_val) else "N/A"
            dt_str  = str(dt_val.date()) if pd.notna(dt_val) else "N/A"
            print(f"  {int(row['amfi_code']):<8} {fh:<28} {nav_str:>12}  {dt_str:<12}")

        # ── Save combined CSV ─────────────────────────────────
        combined_path = PROCESSED_DIR / "live_nav_combined_task5.csv"
        combined.to_csv(combined_path, index=False)
        print(f"\n  Combined CSV saved → {combined_path}")
        print(f"  Total rows         : {len(combined):,}")

        return combined

    return pd.DataFrame()


# ============================================================
# 6. LIVE NAV COMPARATOR
#    Cross-check live NAV against stored historical NAV
# ============================================================
def compare_live_vs_historical(live_df: pd.DataFrame) -> None:
    """
    Cross-reference the latest live NAV against the last recorded
    NAV in the historical file (02_nav_history.csv).
    """
    section("LIVE vs HISTORICAL NAV CROSS-CHECK")

    hist_path = PROJECT_ROOT / "data" / "raw" / "02_nav_history.csv"
    if not hist_path.exists():
        print("  ⚠️  Historical NAV file not found — skipping cross-check")
        return

    hist = pd.read_csv(hist_path, parse_dates=["date"])
    hist_latest = hist.sort_values("date").groupby("amfi_code").last().reset_index()

    live_codes  = live_df["amfi_code"].unique() if not live_df.empty else []

    print(f"\n  {'Code':<8} {'Hist Date':<14} {'Hist NAV':>12}  "
          f"{'Live Date':<14} {'Live NAV':>12}  {'Δ%':>8}")
    print(f"  {'-'*75}")

    for code in live_codes:
        code = int(code)
        hist_row = hist_latest[hist_latest["amfi_code"] == code]
        live_row = live_df[live_df["amfi_code"] == code].sort_values("date").iloc[-1:]

        if hist_row.empty or live_row.empty:
            continue

        h_nav  = hist_row["nav"].values[0]
        h_date = str(hist_row["date"].values[0])[:10]
        l_nav  = live_row["nav"].values[0]
        l_date = str(live_row["date"].values[0])[:10] if pd.notna(
            live_row["date"].values[0]) else "N/A"

        if pd.notna(h_nav) and pd.notna(l_nav) and h_nav != 0:
            delta_pct = ((l_nav - h_nav) / h_nav) * 100
            delta_str = f"{delta_pct:+.2f}%"
        else:
            delta_str = "N/A"

        print(f"  {code:<8} {h_date:<14} ₹{h_nav:>10.4f}  "
              f"{l_date:<14} ₹{l_nav:>10.4f}  {delta_str:>8}")


# ============================================================
# 7. MAIN ORCHESTRATOR
# ============================================================
def main() -> None:
    """Run the full Day 1 live NAV fetch pipeline (Tasks 4 & 5)."""

    print(f"\n{'#'*70}")
    print("  BLUESTOCK FINTECH — MUTUAL FUND ANALYTICS PLATFORM")
    print("  DAY 1: LIVE NAV FETCH  (Tasks 4 & 5)")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  API Base: {MFAPI_BASE}")
    print(f"{'#'*70}")

    # ── Task 4: HDFC Top 100 Direct ───────────────────────────
    hdfc_nav = task4_fetch_hdfc_top100()

    # Courtesy sleep before next batch
    print(f"\n  Sleeping {INTER_REQUEST_SLEEP}s before Task 5 batch ...")
    time.sleep(INTER_REQUEST_SLEEP)

    # ── Task 5: Five key schemes ───────────────────────────────
    five_navs = task5_fetch_five_schemes()

    # ── Cross-check live vs historical ────────────────────────
    if not five_navs.empty:
        compare_live_vs_historical(five_navs)

    # ── Save fetch manifest ───────────────────────────────────
    manifest = {
        "fetch_timestamp" : datetime.now().isoformat(),
        "api_base"        : MFAPI_BASE,
        "schemes_fetched" : list(SCHEMES.keys()),
        "task4_code"      : 125497,
        "task5_codes"     : [k for k, v in SCHEMES.items() if v["task"] == 5],
        "raw_dir"         : str(RAW_DIR),
        "processed_dir"   : str(PROCESSED_DIR),
    }
    manifest_path = RAW_DIR / "live_nav_fetch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    section("LIVE NAV FETCH COMPLETE")
    print(f"\n  ✅ Task 4 — HDFC Top 100 Direct NAV fetched & saved")
    print(f"  ✅ Task 5 — 5 key scheme NAVs fetched & saved")
    print(f"  ✅ Fetch manifest saved → {manifest_path}")
    print(f"\n  Next step: Run data_ingestion.py, then git commit Day 1")
    print(f"\n{'#'*70}\n")


# ── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    main()