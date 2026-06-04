"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
FILE    : src/data_cleaning.py
DAY     : 2  —  Data Cleaning + SQLite DB
TASKS   : 1, 2, 3
AUTHOR  : Bluestock Fintech Capstone Team
DATE    : 2026-06-04
------------------------------------------------------------
PURPOSE :
  Task 1 — Clean nav_history.csv
            - Parse dates to datetime
            - Sort by amfi_code + date
            - Forward-fill missing NAV (weekends/holidays)
            - Remove duplicates
            - Validate NAV > 0

  Task 2 — Clean investor_transactions.csv
            - Standardise transaction_type values
            - Validate amount > 0
            - Fix date formats
            - Check KYC status enum values

  Task 3 — Clean scheme_performance.csv
            - Validate all return values are numeric
            - Flag Sharpe ratio anomalies
            - Check expense_ratio range (0.1% – 2.5%)

  BONUS  — Clean all remaining 7 CSVs for DB loading
============================================================
CONSTRAINTS APPLIED:
  [✓] pathlib.Path — no hardcoded paths
  [✓] ffill after reindex on full business day range (NAV)
  [✓] All dates → datetime64
  [✓] Cleaned CSVs saved to data/processed/
  [✓] Full cleaning log printed + saved
============================================================
"""

# ── Standard Library ────────────────────────────────────────
import sys
from pathlib import Path
from datetime import datetime

# ── Third-Party ─────────────────────────────────────────────
import pandas as pd
import numpy as np

# ============================================================
# 0. PATH CONFIGURATION
# ============================================================
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
RAW_DIR       = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR   = PROJECT_ROOT / "reports"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

SEP  = "=" * 70
SEP2 = "-" * 70

# Cleaning log — accumulated during run
CLEANING_LOG = []


def log(msg: str) -> None:
    """Print and record a cleaning log message."""
    print(f"  {msg}")
    CLEANING_LOG.append(msg)


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


# ============================================================
# 1. TASK 1 — CLEAN NAV HISTORY
# ============================================================
def clean_nav_history() -> pd.DataFrame:
    """
    Task 1: Clean 02_nav_history.csv
    - Parse dates
    - Sort by amfi_code + date
    - Reindex to full business day calendar per fund → ffill gaps
    - Remove duplicates
    - Validate NAV > 0
    """
    section("TASK 1 — Cleaning: 02_nav_history.csv")

    df = pd.read_csv(RAW_DIR / "02_nav_history.csv")
    log(f"Raw shape          : {df.shape[0]:,} rows × {df.shape[1]} cols")

    # ── Step 1: Parse dates ──────────────────────────────────
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    unparsed = df["date"].isnull().sum()
    if unparsed:
        log(f"⚠️  Unparseable dates : {unparsed} — dropping")
        df = df.dropna(subset=["date"])
    else:
        log(f"Date parsing       : ✓ All dates valid")

    # ── Step 2: Remove duplicates ────────────────────────────
    before = len(df)
    df = df.drop_duplicates(subset=["amfi_code", "date"])
    dupes = before - len(df)
    log(f"Duplicates removed : {dupes}")

    # ── Step 3: Validate NAV > 0 ────────────────────────────
    invalid_nav = df[df["nav"] <= 0]
    if len(invalid_nav) > 0:
        log(f"⚠️  NAV <= 0 rows    : {len(invalid_nav)} — dropping")
        df = df[df["nav"] > 0]
    else:
        log(f"NAV > 0 check      : ✓ All NAVs positive")

    # ── Step 4: Sort by amfi_code + date ────────────────────
    df = df.sort_values(["amfi_code", "date"]).reset_index(drop=True)
    log(f"Sorted             : amfi_code + date ✓")

    # ── Step 5: Reindex to business days + ffill per fund ───
    # This fills weekends and market holidays with last known NAV
    date_min = df["date"].min()
    date_max = df["date"].max()
    bday_range = pd.bdate_range(start=date_min, end=date_max)
    log(f"Business day range : {date_min.date()} → {date_max.date()}")
    log(f"Expected bdays     : {len(bday_range):,} per fund")

    filled_frames = []
    funds = df["amfi_code"].unique()

    for code in funds:
        fund_df = df[df["amfi_code"] == code].set_index("date")
        # Reindex to full business day calendar
        fund_df = fund_df.reindex(bday_range)
        fund_df["amfi_code"] = code
        # Forward-fill NAV gaps (weekends / public holidays)
        fund_df["nav"] = fund_df["nav"].ffill()
        # Backward-fill any leading NaNs (fund launched mid-period)
        fund_df["nav"] = fund_df["nav"].bfill()
        fund_df.index.name = "date"
        filled_frames.append(fund_df.reset_index())

    df_filled = pd.concat(filled_frames, ignore_index=True)
    df_filled = df_filled.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    gaps_filled = len(df_filled) - before + dupes
    log(f"NAV gaps filled    : {gaps_filled:,} (ffill applied)")
    log(f"Final shape        : {df_filled.shape[0]:,} rows × {df_filled.shape[1]} cols")

    # ── Save cleaned CSV ─────────────────────────────────────
    out = PROCESSED_DIR / "02_nav_history_clean.csv"
    df_filled.to_csv(out, index=False)
    log(f"Saved              : {out.name} ✓")

    return df_filled


# ============================================================
# 2. TASK 2 — CLEAN INVESTOR TRANSACTIONS
# ============================================================
def clean_investor_transactions() -> pd.DataFrame:
    """
    Task 2: Clean 08_investor_transactions.csv
    - Standardise transaction_type: SIP / Lumpsum / Redemption
    - Validate amount_inr > 0
    - Parse transaction_date to datetime
    - Validate KYC enum: Verified / Pending
    - Validate city_tier enum: T30 / B30
    """
    section("TASK 2 — Cleaning: 08_investor_transactions.csv")

    df = pd.read_csv(RAW_DIR / "08_investor_transactions.csv")
    log(f"Raw shape              : {df.shape[0]:,} rows × {df.shape[1]} cols")

    # ── Step 1: Parse dates ──────────────────────────────────
    df["transaction_date"] = pd.to_datetime(
        df["transaction_date"], format="%Y-%m-%d", errors="coerce"
    )
    bad_dates = df["transaction_date"].isnull().sum()
    if bad_dates:
        log(f"⚠️  Bad dates          : {bad_dates} — dropping")
        df = df.dropna(subset=["transaction_date"])
    else:
        log(f"Date parsing           : ✓ All dates valid")

    # ── Step 2: Standardise transaction_type ────────────────
    VALID_TXN_TYPES = {"SIP", "Lumpsum", "Redemption"}
    # Normalise casing and strip whitespace
    df["transaction_type"] = (
        df["transaction_type"]
        .str.strip()
        .str.title()
        .replace({"Sip": "SIP", "LUMPSUM": "Lumpsum", "REDEMPTION": "Redemption",
                  "lumpsum": "Lumpsum", "sip": "SIP", "redemption": "Redemption"})
    )
    # Fix SIP specifically (title() makes it 'Sip')
    df["transaction_type"] = df["transaction_type"].replace({"Sip": "SIP"})

    invalid_txn = df[~df["transaction_type"].isin(VALID_TXN_TYPES)]
    if len(invalid_txn):
        log(f"⚠️  Invalid txn types  : {len(invalid_txn)} rows — dropping")
        log(f"   Values found        : {invalid_txn['transaction_type'].unique()}")
        df = df[df["transaction_type"].isin(VALID_TXN_TYPES)]
    else:
        log(f"Transaction types      : ✓ All valid {sorted(VALID_TXN_TYPES)}")

    # ── Step 3: Validate amount_inr > 0 ─────────────────────
    invalid_amt = df[df["amount_inr"] <= 0]
    if len(invalid_amt):
        log(f"⚠️  Amount <= 0        : {len(invalid_amt)} rows — dropping")
        df = df[df["amount_inr"] > 0]
    else:
        log(f"Amount > 0 check       : ✓ All amounts positive")

    # ── Step 4: Validate KYC status enum ────────────────────
    VALID_KYC = {"Verified", "Pending"}
    df["kyc_status"] = df["kyc_status"].str.strip().str.title()
    invalid_kyc = df[~df["kyc_status"].isin(VALID_KYC)]
    if len(invalid_kyc):
        log(f"⚠️  Invalid KYC values : {len(invalid_kyc)} — flagging")
        df.loc[~df["kyc_status"].isin(VALID_KYC), "kyc_status"] = "Unknown"
    else:
        log(f"KYC status             : ✓ All valid {sorted(VALID_KYC)}")

    # ── Step 5: Validate city_tier enum ─────────────────────
    VALID_TIERS = {"T30", "B30"}
    invalid_tier = df[~df["city_tier"].isin(VALID_TIERS)]
    if len(invalid_tier):
        log(f"⚠️  Invalid city_tier  : {len(invalid_tier)} rows")
    else:
        log(f"City tier              : ✓ All valid {sorted(VALID_TIERS)}")

    # ── Step 6: Validate age_group enum ─────────────────────
    VALID_AGE = {"18-25", "26-35", "36-45", "46-55", "56+"}
    invalid_age = df[~df["age_group"].isin(VALID_AGE)]
    if len(invalid_age):
        log(f"⚠️  Invalid age_group  : {len(invalid_age)} rows")
    else:
        log(f"Age groups             : ✓ All valid")

    # ── Step 7: Remove duplicates ────────────────────────────
    before = len(df)
    df = df.drop_duplicates()
    log(f"Duplicates removed     : {before - len(df)}")

    # ── Step 8: Summary stats ────────────────────────────────
    log(f"Transaction breakdown  :")
    for txn, cnt in df["transaction_type"].value_counts().items():
        log(f"   {txn:<15} {cnt:>6,} rows")
    log(f"KYC Verified           : {(df['kyc_status']=='Verified').sum():,}")
    log(f"KYC Pending            : {(df['kyc_status']=='Pending').sum():,}")
    log(f"Final shape            : {df.shape[0]:,} rows × {df.shape[1]} cols")

    # ── Save ─────────────────────────────────────────────────
    out = PROCESSED_DIR / "08_investor_transactions_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved                  : {out.name} ✓")

    return df


# ============================================================
# 3. TASK 3 — CLEAN SCHEME PERFORMANCE
# ============================================================
def clean_scheme_performance() -> pd.DataFrame:
    """
    Task 3: Clean 07_scheme_performance.csv
    - Validate all return columns are numeric
    - Flag Sharpe ratio anomalies (outlier > 5.0 is suspicious for equity)
    - Validate expense_ratio in range 0.1% – 2.5%
    - Validate beta > 0, std_dev > 0
    - Add anomaly_flag column for flagged records
    """
    section("TASK 3 — Cleaning: 07_scheme_performance.csv")

    df = pd.read_csv(RAW_DIR / "07_scheme_performance.csv")
    log(f"Raw shape              : {df.shape[0]:,} rows × {df.shape[1]} cols")

    # ── Step 1: Validate numeric return columns ──────────────
    return_cols = [
        "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
        "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio",
        "sortino_ratio", "std_dev_ann_pct", "max_drawdown_pct",
        "expense_ratio_pct"
    ]
    for col in return_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        nulls = df[col].isnull().sum()
        if nulls:
            log(f"⚠️  {col}: {nulls} non-numeric — set to NaN")
        else:
            log(f"Numeric check ✓        : {col}")

    # ── Step 2: Initialise anomaly flag column ───────────────
    df["anomaly_flag"] = ""

    # ── Step 3: Flag Sharpe ratio anomalies ─────────────────
    # Sharpe > 5.0 for equity funds is statistically unusual
    # (Debt/liquid funds can legitimately have high Sharpe)
    sharpe_threshold = 5.0
    high_sharpe = df["sharpe_ratio"] > sharpe_threshold
    df.loc[high_sharpe, "anomaly_flag"] += "HIGH_SHARPE;"
    log(f"Sharpe > {sharpe_threshold} flagged   : "
        f"{high_sharpe.sum()} funds")
    for _, row in df[high_sharpe].iterrows():
        log(f"   {row['amfi_code']} {row['scheme_name'][:45]} "
            f"Sharpe={row['sharpe_ratio']}")

    # ── Step 4: Validate expense_ratio range ────────────────
    EXP_MIN, EXP_MAX = 0.1, 2.5
    out_of_range = (
        (df["expense_ratio_pct"] < EXP_MIN) |
        (df["expense_ratio_pct"] > EXP_MAX)
    )
    if out_of_range.sum():
        df.loc[out_of_range, "anomaly_flag"] += "EXP_RATIO_OOR;"
        log(f"⚠️  Expense ratio OOR  : {out_of_range.sum()} funds")
        for _, row in df[out_of_range].iterrows():
            log(f"   {row['amfi_code']} expense={row['expense_ratio_pct']}%")
    else:
        log(f"Expense ratio range    : ✓ All in [{EXP_MIN}%, {EXP_MAX}%]")

    # ── Step 5: Validate beta > 0 ───────────────────────────
    neg_beta = df["beta"] < 0
    if neg_beta.sum():
        df.loc[neg_beta, "anomaly_flag"] += "NEGATIVE_BETA;"
        log(f"⚠️  Negative beta      : {neg_beta.sum()} funds")
    else:
        log(f"Beta > 0 check         : ✓ All positive")

    # ── Step 6: Validate std_dev > 0 ────────────────────────
    zero_std = df["std_dev_ann_pct"] <= 0
    if zero_std.sum():
        df.loc[zero_std, "anomaly_flag"] += "ZERO_STD;"
        log(f"⚠️  Std dev <= 0       : {zero_std.sum()} funds")
    else:
        log(f"Std dev > 0 check      : ✓ All positive")

    # ── Step 7: Validate max_drawdown <= 0 ──────────────────
    # Drawdown should always be negative (loss)
    pos_drawdown = df["max_drawdown_pct"] > 0
    if pos_drawdown.sum():
        df.loc[pos_drawdown, "anomaly_flag"] += "POSITIVE_DRAWDOWN;"
        log(f"⚠️  Positive drawdown  : {pos_drawdown.sum()} — suspicious")
    else:
        log(f"Drawdown <= 0 check    : ✓ All negative (correct)")

    # ── Step 8: Summary ──────────────────────────────────────
    flagged = df[df["anomaly_flag"] != ""]
    log(f"Total flagged records  : {len(flagged)}")
    log(f"Clean records          : {len(df) - len(flagged)}")
    log(f"Final shape            : {df.shape[0]:,} rows × {df.shape[1]} cols")

    # ── Save ─────────────────────────────────────────────────
    out = PROCESSED_DIR / "07_scheme_performance_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved                  : {out.name} ✓")

    return df


# ============================================================
# 4. CLEAN REMAINING 7 CSVs (standardise dates + basic QC)
# ============================================================
def clean_fund_master() -> pd.DataFrame:
    section("Cleaning: 01_fund_master.csv")
    df = pd.read_csv(RAW_DIR / "01_fund_master.csv")
    df["launch_date"] = pd.to_datetime(df["launch_date"], errors="coerce")
    df["fund_house"]  = df["fund_house"].str.strip()
    df["category"]    = df["category"].str.strip()
    # Normalise category name
    df["sub_category"] = df["sub_category"].str.strip()
    log(f"fund_master: {df.shape} | nulls={df.isnull().sum().sum()} ✓")
    out = PROCESSED_DIR / "01_fund_master_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_aum_by_fund_house() -> pd.DataFrame:
    section("Cleaning: 03_aum_by_fund_house.csv")
    df = pd.read_csv(RAW_DIR / "03_aum_by_fund_house.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["fund_house"] = df["fund_house"].str.strip()
    df = df.drop_duplicates()
    log(f"aum_by_fund_house: {df.shape} | nulls={df.isnull().sum().sum()} ✓")
    out = PROCESSED_DIR / "03_aum_by_fund_house_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_monthly_sip_inflows() -> pd.DataFrame:
    section("Cleaning: 04_monthly_sip_inflows.csv")
    df = pd.read_csv(RAW_DIR / "04_monthly_sip_inflows.csv")
    # month format: "2022-01" → parse as first day of month
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    # yoy_growth_pct: first 12 months are intentionally NULL — keep as NaN
    nulls = df["yoy_growth_pct"].isnull().sum()
    log(f"sip_inflows: yoy_growth_pct NULLs={nulls} (first 12 months — expected)")
    log(f"monthly_sip_inflows: {df.shape} ✓")
    out = PROCESSED_DIR / "04_monthly_sip_inflows_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_category_inflows() -> pd.DataFrame:
    section("Cleaning: 05_category_inflows.csv")
    df = pd.read_csv(RAW_DIR / "05_category_inflows.csv")
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    # Normalise 'Value/Contra' → 'Value' to match fund_master
    df["category"] = df["category"].str.strip()
    df["category"] = df["category"].replace({"Value/Contra": "Value"})
    log(f"category_inflows: 'Value/Contra' normalised to 'Value' ✓")
    log(f"category_inflows: {df.shape} ✓")
    out = PROCESSED_DIR / "05_category_inflows_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_industry_folio_count() -> pd.DataFrame:
    section("Cleaning: 06_industry_folio_count.csv")
    df = pd.read_csv(RAW_DIR / "06_industry_folio_count.csv")
    df["month"] = pd.to_datetime(df["month"], format="%Y-%m", errors="coerce")
    log(f"industry_folio_count: {df.shape} | nulls={df.isnull().sum().sum()} ✓")
    out = PROCESSED_DIR / "06_industry_folio_count_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_portfolio_holdings() -> pd.DataFrame:
    section("Cleaning: 09_portfolio_holdings.csv")
    df = pd.read_csv(RAW_DIR / "09_portfolio_holdings.csv")
    df["portfolio_date"] = pd.to_datetime(df["portfolio_date"], errors="coerce")
    df["sector"] = df["sector"].str.strip()
    df["stock_symbol"] = df["stock_symbol"].str.strip().str.upper()
    # Validate weight_pct > 0
    invalid_wt = df[df["weight_pct"] <= 0]
    if len(invalid_wt):
        log(f"⚠️  weight_pct <= 0: {len(invalid_wt)} — dropping")
        df = df[df["weight_pct"] > 0]
    log(f"portfolio_holdings: {df.shape} ✓")
    out = PROCESSED_DIR / "09_portfolio_holdings_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


def clean_benchmark_indices() -> pd.DataFrame:
    section("Cleaning: 10_benchmark_indices.csv")
    df = pd.read_csv(RAW_DIR / "10_benchmark_indices.csv")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["index_name"] = df["index_name"].str.strip()
    df = df.sort_values(["index_name", "date"]).reset_index(drop=True)
    df = df.drop_duplicates(subset=["date", "index_name"])
    # Validate close_value > 0
    invalid = df[df["close_value"] <= 0]
    if len(invalid):
        log(f"⚠️  close_value <= 0: {len(invalid)} — dropping")
        df = df[df["close_value"] > 0]
    log(f"benchmark_indices: {df.shape} ✓")
    out = PROCESSED_DIR / "10_benchmark_indices_clean.csv"
    df.to_csv(out, index=False)
    log(f"Saved: {out.name} ✓")
    return df


# ============================================================
# 5. WRITE CLEANING REPORT
# ============================================================
def write_cleaning_report(datasets: dict) -> Path:
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = REPORTS_DIR / f"cleaning_report_day2_{ts}.txt"
    lines    = []

    lines.append("=" * 70)
    lines.append("  BLUESTOCK FINTECH — DATA CLEANING REPORT  |  DAY 2")
    lines.append(f"  Generated : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)

    lines.append("\n## CLEANED FILES\n")
    total = 0
    for fname, df in datasets.items():
        lines.append(f"  {fname:<45}  {df.shape[0]:>8,} rows  {df.shape[1]:>3} cols")
        total += df.shape[0]
    lines.append(f"\n  Total rows in processed/ : {total:,}")

    lines.append("\n## CLEANING ACTIONS LOG\n")
    for entry in CLEANING_LOG:
        lines.append(f"  {entry}")

    lines.append("\n## KEY DECISIONS\n")
    lines.append("  NAV ffill  : Reindexed to business days, ffill gaps (weekends/holidays)")
    lines.append("  yoy_growth : First 12 NULLs kept as NaN — mathematically correct")
    lines.append("  Value/Contra → Value : Normalised in category_inflows")
    lines.append("  Sharpe > 5 : Flagged in anomaly_flag (not dropped — debt funds OK)")
    lines.append("  KYC Pending: Kept — valid business state, used in segmentation")

    lines.append("\n" + "=" * 70)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


# ============================================================
# 6. MAIN
# ============================================================
def main() -> dict:
    print(f"\n{'#'*70}")
    print("  BLUESTOCK FINTECH — DAY 2: DATA CLEANING PIPELINE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#'*70}")

    datasets = {}

    # Priority cleans (Tasks 1–3)
    datasets["02_nav_history_clean.csv"]           = clean_nav_history()
    datasets["08_investor_transactions_clean.csv"] = clean_investor_transactions()
    datasets["07_scheme_performance_clean.csv"]    = clean_scheme_performance()

    # Remaining 7 CSVs
    datasets["01_fund_master_clean.csv"]           = clean_fund_master()
    datasets["03_aum_by_fund_house_clean.csv"]     = clean_aum_by_fund_house()
    datasets["04_monthly_sip_inflows_clean.csv"]   = clean_monthly_sip_inflows()
    datasets["05_category_inflows_clean.csv"]      = clean_category_inflows()
    datasets["06_industry_folio_count_clean.csv"]  = clean_industry_folio_count()
    datasets["09_portfolio_holdings_clean.csv"]    = clean_portfolio_holdings()
    datasets["10_benchmark_indices_clean.csv"]     = clean_benchmark_indices()

    # Report
    section("WRITING CLEANING REPORT")
    report = write_cleaning_report(datasets)
    print(f"\n  ✅ Report saved → {report}")

    # Summary
    section("CLEANING COMPLETE")
    total = sum(df.shape[0] for df in datasets.values())
    print(f"\n  Files cleaned    : {len(datasets)}")
    print(f"  Total rows       : {total:,}")
    print(f"  Saved to         : {PROCESSED_DIR}")
    print(f"\n  ✅ Day 2 Tasks 1, 2, 3 — COMPLETE")
    print(f"  Next             : Run db_schema.py → etl_loader.py")
    print(f"\n{'#'*70}\n")

    return datasets


if __name__ == "__main__":
    main()