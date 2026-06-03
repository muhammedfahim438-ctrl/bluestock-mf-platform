"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
FILE    : src/data_ingestion.py
DAY     : 1  —  Project Setup + Data Ingestion (ETL)
TASKS   : 3, 6, 7
AUTHOR  : Bluestock Fintech Capstone Team
DATE    : 2026-06-03
------------------------------------------------------------
PURPOSE :
  1. Load all 10 raw CSV datasets using Pandas.
  2. Print .shape, .dtypes, .head() for each file.
  3. Flag anomalies and document data quality notes.
  4. Explore fund master (fund houses, categories, risk).
  5. Validate AMFI code referential integrity across files.
  6. Export a structured data quality report.
============================================================
"""

# ── Standard Library ────────────────────────────────────────
import sys
import os
from pathlib import Path
from datetime import datetime

# ── Third-Party ─────────────────────────────────────────────
import pandas as pd
import numpy as np

# ============================================================
# 0. PATH CONFIGURATION  (Never hardcode — always use pathlib)
# ============================================================
# Resolve project root as the parent of this file's directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR      = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR  = PROJECT_ROOT / "reports"

# Ensure output directories exist
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Separator helpers ────────────────────────────────────────
SEP  = "=" * 70
SEP2 = "-" * 70


def section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


# ============================================================
# 1. DATASET REGISTRY
#    Maps filename → friendly label + known anomaly hints
# ============================================================
DATASET_REGISTRY = {
    "01_fund_master.csv": {
        "label"    : "Fund Master (dim_fund candidate)",
        "pk"       : "amfi_code",
        "date_cols": ["launch_date"],
        "notes"    : "Master dimension — no nulls expected",
    },
    "02_nav_history.csv": {
        "label"    : "NAV History (fact_nav candidate)",
        "pk"       : None,
        "date_cols": ["date"],
        "notes"    : "Reindex + ffill required for weekends/holidays",
    },
    "03_aum_by_fund_house.csv": {
        "label"    : "AUM by Fund House (fact_aum candidate)",
        "pk"       : None,
        "date_cols": ["date"],
        "notes"    : "Quarterly snapshots; 9 periods × 10 AMCs = 90 rows",
    },
    "04_monthly_sip_inflows.csv": {
        "label"    : "Monthly SIP Inflows (fact_sip_industry candidate)",
        "pk"       : None,
        "date_cols": ["month"],
        "notes"    : "yoy_growth_pct: first 12 months intentionally NULL",
    },
    "05_category_inflows.csv": {
        "label"    : "Category Inflows",
        "pk"       : None,
        "date_cols": ["month"],
        "notes"    : "'Value/Contra' vs 'Value' naming — normalize on load",
    },
    "06_industry_folio_count.csv": {
        "label"    : "Industry Folio Count",
        "pk"       : None,
        "date_cols": ["month"],
        "notes"    : "Quarterly data; values in crore units",
    },
    "07_scheme_performance.csv": {
        "label"    : "Scheme Performance (fact_performance candidate)",
        "pk"       : "amfi_code",
        "date_cols": [],
        "notes"    : "Pre-computed metrics; validate Sharpe outlier >7",
    },
    "08_investor_transactions.csv": {
        "label"    : "Investor Transactions (fact_transactions candidate)",
        "pk"       : None,
        "date_cols": ["transaction_date"],
        "notes"    : "~32K rows; KYC 'Pending' records need flagging",
    },
    "09_portfolio_holdings.csv": {
        "label"    : "Portfolio Holdings (fact_portfolio candidate)",
        "pk"       : None,
        "date_cols": ["portfolio_date"],
        "notes"    : "34/40 funds present; debt/liquid funds expected absent",
    },
    "10_benchmark_indices.csv": {
        "label"    : "Benchmark Indices",
        "pk"       : None,
        "date_cols": ["date"],
        "notes"    : "7 indices; aligns with NAV dates for Alpha/Beta calc",
    },
}


# ============================================================
# 2. CORE LOADER
#    Loads a single CSV with date parsing and type inference
# ============================================================
def load_csv(filename: str, registry: dict = DATASET_REGISTRY) -> pd.DataFrame:
    """
    Load a CSV from RAW_DIR with automatic date parsing.

    Parameters
    ----------
    filename : str  e.g. '01_fund_master.csv'
    registry : dict  DATASET_REGISTRY for metadata lookup

    Returns
    -------
    pd.DataFrame  with date columns already parsed to datetime
    """
    fpath = RAW_DIR / filename
    if not fpath.exists():
        raise FileNotFoundError(f"[ERROR] File not found: {fpath}")

    meta       = registry.get(filename, {})
    date_cols  = meta.get("date_cols", [])

    df = pd.read_csv(fpath, parse_dates=date_cols, low_memory=False)
    return df


# ============================================================
# 3. PROFILE PRINTER
#    Prints shape, dtypes, head, nulls, numeric describe
# ============================================================
def profile_dataframe(df: pd.DataFrame, filename: str,
                      registry: dict = DATASET_REGISTRY) -> dict:
    """
    Print a structured profile of a DataFrame and return
    a summary dict for the data quality report.

    Returns
    -------
    dict  with keys: filename, label, shape, null_cols, anomalies
    """
    meta      = registry.get(filename, {})
    label     = meta.get("label", filename)
    notes     = meta.get("notes", "")
    anomalies = []

    section(f"{filename}  |  {label}")

    # ── Shape ────────────────────────────────────────────────
    print(f"\n  Shape       : {df.shape[0]:>8,} rows  ×  {df.shape[1]} columns")

    # ── Dtypes ───────────────────────────────────────────────
    print(f"\n  Dtypes:")
    for col, dtype in df.dtypes.items():
        print(f"    {col:<30}  {str(dtype)}")

    # ── Head (3 rows) ────────────────────────────────────────
    print(f"\n  Head (3 rows):")
    print(df.head(3).to_string(index=False))

    # ── Null Analysis ────────────────────────────────────────
    null_counts = df.isnull().sum()
    null_cols   = null_counts[null_counts > 0]
    print(f"\n  Null Columns:")
    if null_cols.empty:
        print("    None  ✓")
    else:
        for col, cnt in null_cols.items():
            pct = cnt / len(df) * 100
            flag = "⚠️ " if pct > 5 else "ℹ️ "
            print(f"    {flag} {col:<30}  {cnt:>6} nulls  ({pct:.1f}%)")
            anomalies.append(f"NULL — {col}: {cnt} rows ({pct:.1f}%)")

    # ── Numeric Describe ─────────────────────────────────────
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if num_cols:
        print(f"\n  Numeric Summary:")
        print(df[num_cols].describe().round(4).to_string())

    # ── Duplicate Check ──────────────────────────────────────
    pk = meta.get("pk")
    if pk and pk in df.columns:
        dupes = df[pk].duplicated().sum()
        if dupes > 0:
            print(f"\n  ⚠️  Duplicate PKs on '{pk}': {dupes}")
            anomalies.append(f"DUPLICATE PK — {pk}: {dupes} rows")
        else:
            print(f"\n  PK '{pk}' uniqueness : ✓ No duplicates")

    # ── Registered Notes ─────────────────────────────────────
    if notes:
        print(f"\n  📋 Notes: {notes}")

    return {
        "filename" : filename,
        "label"    : label,
        "rows"     : df.shape[0],
        "cols"     : df.shape[1],
        "null_cols": null_cols.to_dict(),
        "anomalies": anomalies,
        "notes"    : notes,
    }


# ============================================================
# 4. FUND MASTER EXPLORER
#    Task 6: Print unique fund houses, categories, risk grades
# ============================================================
def explore_fund_master(df: pd.DataFrame) -> None:
    """
    Task 6 — Deep exploration of the fund master dimension table.
    Prints unique values for all key categorical columns.
    Explains AMFI scheme code structure.
    """
    section("TASK 6 — Fund Master Exploration")

    # AMFI Code Structure
    codes = df["amfi_code"].sort_values().tolist()
    print(f"\n  AMFI Scheme Code Structure:")
    print(f"    Total Schemes : {len(codes)}")
    print(f"    Code Range    : {min(codes)} → {max(codes)}")
    print(f"    Format        : 6-digit numeric, assigned by AMFI in")
    print(f"                    chronological launch order")
    print(f"    Example       : 119551 = SBI Bluechip Fund Regular Growth")

    # Fund Houses
    houses = df["fund_house"].value_counts()
    print(f"\n  {'Fund Houses':} ({df['fund_house'].nunique()} AMCs):")
    for house, cnt in houses.items():
        print(f"    {house:<35}  {cnt:>2} schemes")

    # Categories & Sub-categories
    print(f"\n  Categories:")
    for cat in sorted(df["category"].unique()):
        subs = df[df["category"] == cat]["sub_category"].unique().tolist()
        print(f"    {cat}")
        for s in sorted(subs):
            cnt = len(df[(df["category"] == cat) & (df["sub_category"] == s)])
            print(f"      └─ {s:<25}  {cnt} schemes")

    # Plan Types
    plans = df["plan"].value_counts()
    print(f"\n  Plans:")
    for plan, cnt in plans.items():
        print(f"    {plan:<15}  {cnt} schemes")

    # Risk Categories
    risk_order = ["Low", "Moderate", "Moderately High", "High", "Very High"]
    print(f"\n  Risk Categories (Low → High):")
    for risk in risk_order:
        cnt = len(df[df["risk_category"] == risk])
        if cnt > 0:
            bar = "█" * cnt
            print(f"    {risk:<20}  {cnt:>2}  {bar}")

    # Expense Ratio Analysis
    print(f"\n  Expense Ratio Analysis:")
    for plan in ["Regular", "Direct"]:
        sub = df[df["plan"] == plan]["expense_ratio_pct"]
        print(f"    {plan:<10}  min={sub.min():.2f}%  "
              f"mean={sub.mean():.2f}%  max={sub.max():.2f}%")

    # Benchmark Distribution
    benchmarks = df["benchmark"].value_counts()
    print(f"\n  Benchmark Distribution ({df['benchmark'].nunique()} unique):")
    for bm, cnt in benchmarks.items():
        print(f"    {bm:<40}  {cnt} schemes")


# ============================================================
# 5. AMFI CODE VALIDATOR
#    Task 7: Cross-file referential integrity check
# ============================================================
def validate_amfi_codes(datasets: dict) -> dict:
    """
    Task 7 — Validate that every amfi_code in each fact file
    exists in the master dimension (01_fund_master.csv).

    Parameters
    ----------
    datasets : dict  {filename: DataFrame}

    Returns
    -------
    dict  validation_report with per-file pass/fail and orphan codes
    """
    section("TASK 7 — AMFI Code Referential Integrity Validation")

    master_codes = set(datasets["01_fund_master.csv"]["amfi_code"].unique())
    print(f"\n  Master (dim_fund) code count: {len(master_codes)}")
    print(f"  Codes: {sorted(master_codes)[:5]} ... (showing first 5)")

    FILES_WITH_AMFI = [
        "02_nav_history.csv",
        "07_scheme_performance.csv",
        "08_investor_transactions.csv",
        "09_portfolio_holdings.csv",
    ]

    validation_report = {}

    print(f"\n  {'File':<45} {'Codes':>6} {'In Master':>10} {'Orphans':>8}  Status")
    print(f"  {SEP2}")

    for fname in FILES_WITH_AMFI:
        df        = datasets[fname]
        file_codes = set(df["amfi_code"].unique())
        orphans   = file_codes - master_codes
        covered   = file_codes & master_codes
        status    = "✅ PASS" if len(orphans) == 0 else "❌ FAIL"

        print(f"  {fname:<45} {len(file_codes):>6} {len(covered):>10} "
              f"{len(orphans):>8}  {status}")

        validation_report[fname] = {
            "total_codes" : len(file_codes),
            "valid_codes" : len(covered),
            "orphan_codes": list(orphans),
            "status"      : "PASS" if not orphans else "FAIL",
        }

    # Portfolio: 34/40 — expected omissions (Debt/Liquid funds)
    port_codes    = set(datasets["09_portfolio_holdings.csv"]["amfi_code"].unique())
    missing_from_port = master_codes - port_codes
    print(f"\n  Funds in master NOT in portfolio (expected for Debt/Liquid):")
    for code in sorted(missing_from_port):
        name = datasets["01_fund_master.csv"].loc[
            datasets["01_fund_master.csv"]["amfi_code"] == code,
            "scheme_name"
        ].values[0]
        cat  = datasets["01_fund_master.csv"].loc[
            datasets["01_fund_master.csv"]["amfi_code"] == code,
            "sub_category"
        ].values[0]
        print(f"    {code}  {name[:55]:<55}  [{cat}]")

    return validation_report


# ============================================================
# 6. DATA QUALITY REPORT WRITER
# ============================================================
def write_quality_report(profiles: list, validation: dict) -> Path:
    """
    Write a structured text data quality report to reports/.

    Returns
    -------
    Path  of the written report file
    """
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = REPORTS_DIR / f"data_quality_report_day1_{ts}.txt"
    lines     = []

    lines.append("=" * 70)
    lines.append("  BLUESTOCK FINTECH — MUTUAL FUND ANALYTICS PLATFORM")
    lines.append("  DATA QUALITY REPORT  |  DAY 1: INGESTION")
    lines.append(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    lines.append("\n## DATASET SUMMARY\n")
    lines.append(f"  {'File':<45} {'Rows':>8} {'Cols':>6}  Anomalies")
    lines.append(f"  {'-'*68}")
    total_rows = 0
    for p in profiles:
        anom_flag = "⚠️ " if p["anomalies"] else "✓"
        lines.append(f"  {p['filename']:<45} {p['rows']:>8,} {p['cols']:>6}  "
                     f"{anom_flag} {len(p['anomalies'])} issue(s)")
        total_rows += p["rows"]
    lines.append(f"\n  Total rows ingested: {total_rows:,}")

    lines.append("\n## ANOMALIES DETECTED\n")
    found_any = False
    for p in profiles:
        if p["anomalies"]:
            found_any = True
            lines.append(f"  {p['filename']}:")
            for a in p["anomalies"]:
                lines.append(f"    ⚠️  {a}")
            lines.append(f"  📋 Note: {p['notes']}")
    if not found_any:
        lines.append("  None critical — see individual notes above.")

    lines.append("\n## KNOWN ACCEPTABLE NULL FIELDS\n")
    lines.append("  04_monthly_sip_inflows.csv | yoy_growth_pct | first 12 months")
    lines.append("  REASON: YoY requires a prior-year baseline; 2022 has none.")
    lines.append("  ACTION: Keep as NaN — do NOT ffill or impute.")

    lines.append("\n## AMFI CODE REFERENTIAL INTEGRITY\n")
    for fname, result in validation.items():
        lines.append(f"  {fname}:")
        lines.append(f"    Status  : {result['status']}")
        lines.append(f"    Valid   : {result['valid_codes']}/{result['total_codes']}")
        if result["orphan_codes"]:
            lines.append(f"    Orphans : {result['orphan_codes']}")

    lines.append("\n## CATEGORY NAMING INCONSISTENCY\n")
    lines.append("  05_category_inflows.csv uses 'Value/Contra'")
    lines.append("  01_fund_master.csv uses 'Value'")
    lines.append("  ACTION: Normalize to 'Value' during ETL load into SQLite.")

    lines.append("\n## ENGINEERING CONSTRAINTS VERIFIED\n")
    lines.append("  [✓] Paths use pathlib.Path — no hardcoded strings")
    lines.append("  [✓] Date columns parsed via parse_dates= at load time")
    lines.append("  [✓] NAV ffill strategy documented (apply Day 2 schema load)")
    lines.append("  [✓] 252 trading days annualization noted for metrics (Day 4)")
    lines.append("  [✓] Rf = 6.5% proxy for Sharpe calculation (Day 4)")

    lines.append("\n" + "=" * 70)
    lines.append("  END OF REPORT")
    lines.append("=" * 70)

    report_text = "\n".join(lines)
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


# ============================================================
# 7. MAIN ORCHESTRATOR
# ============================================================
def main() -> dict:
    """
    Run the full Day 1 data ingestion pipeline.

    Returns
    -------
    dict  {filename: DataFrame}  — all loaded datasets
    """
    print(f"\n{'#'*70}")
    print("  BLUESTOCK FINTECH — MUTUAL FUND ANALYTICS PLATFORM")
    print("  DAY 1: DATA INGESTION PIPELINE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")

    # ── Step 1: Load all CSVs ─────────────────────────────────
    section("STEP 1: LOADING ALL 10 RAW CSV FILES")
    datasets  = {}
    profiles  = []

    for filename in DATASET_REGISTRY.keys():
        print(f"\n  Loading: {filename} ...", end="", flush=True)
        try:
            df = load_csv(filename)
            datasets[filename] = df
            print(f"  ✓  {df.shape[0]:,} rows × {df.shape[1]} cols")
        except FileNotFoundError as e:
            print(f"\n  {e}")
            sys.exit(1)

    # ── Step 2: Profile each DataFrame ───────────────────────
    section("STEP 2: PROFILING ALL DATASETS")
    for filename, df in datasets.items():
        profile = profile_dataframe(df, filename)
        profiles.append(profile)

    # ── Step 3: Fund Master Exploration (Task 6) ──────────────
    explore_fund_master(datasets["01_fund_master.csv"])

    # ── Step 4: AMFI Code Validation (Task 7) ─────────────────
    validation_report = validate_amfi_codes(datasets)

    # ── Step 5: Write Quality Report ──────────────────────────
    section("STEP 5: WRITING DATA QUALITY REPORT")
    report_path = write_quality_report(profiles, validation_report)
    print(f"\n  ✅  Report saved → {report_path}")

    # ── Step 6: Final Summary ─────────────────────────────────
    section("INGESTION COMPLETE — SUMMARY")
    total_rows = sum(df.shape[0] for df in datasets.values())
    total_cols = sum(df.shape[1] for df in datasets.values())
    print(f"\n  Files loaded     : {len(datasets)}")
    print(f"  Total rows       : {total_rows:,}")
    print(f"  Total columns    : {total_cols}")
    print(f"  Raw data path    : {RAW_DIR}")
    print(f"  Quality report   : {report_path}")
    print(f"\n  ✅ Day 1 Task 3, 6, 7 — COMPLETE")
    print(f"  Next step        : Run live_nav_fetch.py (Tasks 4 & 5)")
    print(f"\n{'#'*70}\n")

    return datasets


# ── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    loaded_datasets = main()