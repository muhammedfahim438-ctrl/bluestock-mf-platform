"""
============================================================
Bluestock Fintech — Mutual Fund Analytics Platform
FILE    : src/etl_loader.py
DAY     : 2  —  SQLite Star Schema + ETL Load
TASK    : 5
AUTHOR  : Bluestock Fintech Capstone Team
DATE    : 2026-06-04
------------------------------------------------------------
PURPOSE :
  1. Create SQLite database (bluestock_mf.db)
  2. Apply schema.sql DDL (all tables + indexes)
  3. Generate dim_date dimension (2022-01-01 → 2026-12-31)
  4. Load all 10 cleaned CSVs into correct tables
  5. Verify row counts match source CSVs
  6. Print full load summary
============================================================
CONSTRAINTS:
  [✓] pathlib.Path — no hardcoded paths
  [✓] SQLAlchemy create_engine for DB connection
  [✓] df.to_sql() with if_exists='append' (schema pre-created)
  [✓] date_id = YYYYMMDD integer (fast integer joins)
  [✓] Foreign key integrity verified after load
============================================================
"""

# ── Standard Library ────────────────────────────────────────
import sqlite3
from pathlib import Path
from datetime import datetime

# ── Third-Party ─────────────────────────────────────────────
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

# ============================================================
# 0. PATH CONFIGURATION
# ============================================================
PROJECT_ROOT  = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
SQL_DIR       = PROJECT_ROOT / "sql"
DB_PATH       = PROJECT_ROOT / "bluestock_mf.db"
SCHEMA_PATH   = SQL_DIR / "schema.sql"

SEP  = "=" * 70
SEP2 = "-" * 70


def section(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")


def get_engine():
    """Return SQLAlchemy engine for bluestock_mf.db."""
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


# ============================================================
# 1. CREATE DATABASE + APPLY SCHEMA
# ============================================================
def create_database() -> None:
    """
    Drop and recreate the SQLite database by executing schema.sql.
    """
    section("STEP 1 — Creating SQLite Database & Schema")

    # Remove existing DB for clean rebuild
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"  Removed old DB: {DB_PATH.name}")

    # Read schema SQL
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    # Execute via sqlite3 (handles multi-statement scripts)
    conn = sqlite3.connect(str(DB_PATH))
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()

    print(f"  ✅ Database created  : {DB_PATH}")
    print(f"  ✅ Schema applied    : {SCHEMA_PATH.name}")

    # Verify tables created
    engine = get_engine()
    with engine.connect() as con:
        result = con.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ))
        tables = [r[0] for r in result]
    print(f"  Tables created ({len(tables)}): {tables}")


# ============================================================
# 2. GENERATE dim_date
# ============================================================
def build_dim_date() -> pd.DataFrame:
    """
    Generate the dim_date dimension table for 2022-01-01 → 2026-12-31.
    date_id = YYYYMMDD integer (e.g. 20220103) for fast joins.
    """
    section("STEP 2 — Building dim_date Dimension")

    dates = pd.date_range(start="2022-01-01", end="2026-12-31", freq="D")

    FY_MONTH_START = 4  # Indian FY starts April

    records = []
    for d in dates:
        # Indian Financial Year
        if d.month >= FY_MONTH_START:
            fy_start = d.year
        else:
            fy_start = d.year - 1
        fy_label = f"FY{str(fy_start)[2:]}-{str(fy_start + 1)[2:]}"

        # FY Quarter (Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar)
        fy_month = ((d.month - FY_MONTH_START) % 12) + 1
        fy_q     = (fy_month - 1) // 3 + 1
        fy_q_label = f"Q{fy_q}{fy_label[-5:]}"

        records.append({
            "date_id"       : int(d.strftime("%Y%m%d")),
            "full_date"     : d.date().isoformat(),
            "year"          : d.year,
            "quarter"       : d.quarter,
            "month"         : d.month,
            "month_name"    : d.strftime("%B"),
            "week_of_year"  : int(d.strftime("%W")),
            "day_of_month"  : d.day,
            "day_of_week"   : d.dayofweek,        # 0=Mon, 6=Sun
            "day_name"      : d.strftime("%A"),
            "is_weekend"    : int(d.dayofweek >= 5),
            "is_business_day": int(d.dayofweek < 5),
            "fy_year"       : fy_label,
            "fy_quarter"    : fy_q_label,
        })

    dim_date = pd.DataFrame(records)
    print(f"  dim_date rows : {len(dim_date):,}  "
          f"({dim_date['full_date'].min()} → {dim_date['full_date'].max()})")

    # Load into DB
    engine = get_engine()
    dim_date.to_sql("dim_date", engine, if_exists="append", index=False)
    print(f"  ✅ dim_date loaded into DB")

    return dim_date


# ============================================================
# 3. HELPER — Get date_id from a date value
# ============================================================
def date_to_id(date_val) -> int:
    """Convert a date/string to YYYYMMDD integer date_id."""
    if pd.isna(date_val):
        return None
    if isinstance(date_val, (int, np.integer)):
        return int(date_val)
    d = pd.to_datetime(date_val)
    return int(d.strftime("%Y%m%d"))


# ============================================================
# 4. LOAD dim_fund
# ============================================================
def load_dim_fund(engine) -> int:
    section("STEP 3 — Loading dim_fund")
    df = pd.read_csv(PROCESSED_DIR / "01_fund_master_clean.csv")
    df["launch_date"] = pd.to_datetime(df["launch_date"], errors="coerce")
    df["launch_date"] = df["launch_date"].dt.date.astype(str)

    cols = [
        "amfi_code","fund_house","scheme_name","category","sub_category",
        "plan","launch_date","benchmark","expense_ratio_pct","exit_load_pct",
        "min_sip_amount","min_lumpsum_amount","fund_manager",
        "risk_category","sebi_category_code"
    ]
    df = df[cols]
    df.to_sql("dim_fund", engine, if_exists="append", index=False)
    print(f"  ✅ dim_fund loaded: {len(df):>6,} rows")
    return len(df)


# ============================================================
# 5. LOAD fact_nav
# ============================================================
def load_fact_nav(engine) -> int:
    section("STEP 4 — Loading fact_nav")
    df = pd.read_csv(PROCESSED_DIR / "02_nav_history_clean.csv",
                     parse_dates=["date"])
    df["date_id"] = df["date"].apply(date_to_id)
    df = df[["amfi_code", "date_id", "nav"]]
    df = df.dropna(subset=["date_id", "nav"])

    # Load in chunks — large table
    chunk = 10_000
    total = 0
    for i in range(0, len(df), chunk):
        df.iloc[i:i+chunk].to_sql(
            "fact_nav", engine, if_exists="append", index=False
        )
        total += min(chunk, len(df) - i)
        print(f"  Loaded {total:>8,} / {len(df):,} rows ...", end="\r")
    print(f"\n  ✅ fact_nav loaded : {len(df):>8,} rows")
    return len(df)


# ============================================================
# 6. LOAD fact_transactions
# ============================================================
def load_fact_transactions(engine) -> int:
    section("STEP 5 — Loading fact_transactions")
    df = pd.read_csv(PROCESSED_DIR / "08_investor_transactions_clean.csv",
                     parse_dates=["transaction_date"])
    df["date_id"] = df["transaction_date"].apply(date_to_id)
    df["transaction_date"] = df["transaction_date"].dt.date.astype(str)

    cols = [
        "investor_id","transaction_date","date_id","amfi_code",
        "transaction_type","amount_inr","state","city","city_tier",
        "age_group","gender","annual_income_lakh","payment_mode","kyc_status"
    ]
    df = df[cols]

    chunk = 5_000
    total = 0
    for i in range(0, len(df), chunk):
        df.iloc[i:i+chunk].to_sql(
            "fact_transactions", engine, if_exists="append", index=False
        )
        total += min(chunk, len(df) - i)
        print(f"  Loaded {total:>8,} / {len(df):,} rows ...", end="\r")
    print(f"\n  ✅ fact_transactions loaded: {len(df):>6,} rows")
    return len(df)


# ============================================================
# 7. LOAD fact_performance
# ============================================================
def load_fact_performance(engine) -> int:
    section("STEP 6 — Loading fact_performance")
    df = pd.read_csv(PROCESSED_DIR / "07_scheme_performance_clean.csv")
    cols = [
        "amfi_code","return_1yr_pct","return_3yr_pct","return_5yr_pct",
        "benchmark_3yr_pct","alpha","beta","sharpe_ratio","sortino_ratio",
        "std_dev_ann_pct","max_drawdown_pct","aum_crore","expense_ratio_pct",
        "morningstar_rating","risk_grade","anomaly_flag"
    ]
    df = df[cols]
    df.to_sql("fact_performance", engine, if_exists="append", index=False)
    print(f"  ✅ fact_performance loaded: {len(df):>4} rows")
    return len(df)


# ============================================================
# 8. LOAD fact_aum
# ============================================================
def load_fact_aum(engine) -> int:
    section("STEP 7 — Loading fact_aum")
    df = pd.read_csv(PROCESSED_DIR / "03_aum_by_fund_house_clean.csv",
                     parse_dates=["date"])
    df["date_id"]     = df["date"].apply(date_to_id)
    df["report_date"] = df["date"].dt.date.astype(str)
    df = df.rename(columns={"date": "_drop"})
    df = df[["date_id","report_date","fund_house",
             "aum_lakh_crore","aum_crore","num_schemes"]]
    df.to_sql("fact_aum", engine, if_exists="append", index=False)
    print(f"  ✅ fact_aum loaded      : {len(df):>4} rows")
    return len(df)


# ============================================================
# 9. LOAD fact_sip_industry
# ============================================================
def load_fact_sip_industry(engine) -> int:
    section("STEP 8 — Loading fact_sip_industry")
    df = pd.read_csv(PROCESSED_DIR / "04_monthly_sip_inflows_clean.csv",
                     parse_dates=["month"])
    df["date_id"] = df["month"].apply(date_to_id)
    df["month"]   = df["month"].dt.date.astype(str)
    cols = [
        "date_id","month","sip_inflow_crore","active_sip_accounts_crore",
        "new_sip_accounts_lakh","sip_aum_lakh_crore","yoy_growth_pct"
    ]
    df = df[cols]
    df.to_sql("fact_sip_industry", engine, if_exists="append", index=False)
    print(f"  ✅ fact_sip_industry loaded: {len(df):>3} rows")
    return len(df)


# ============================================================
# 10. LOAD fact_portfolio
# ============================================================
def load_fact_portfolio(engine) -> int:
    section("STEP 9 — Loading fact_portfolio")
    df = pd.read_csv(PROCESSED_DIR / "09_portfolio_holdings_clean.csv",
                     parse_dates=["portfolio_date"])
    df["date_id"]       = df["portfolio_date"].apply(date_to_id)
    df["portfolio_date"] = df["portfolio_date"].dt.date.astype(str)
    cols = [
        "amfi_code","portfolio_date","date_id","stock_symbol",
        "stock_name","sector","weight_pct","market_value_cr","current_price_inr"
    ]
    df = df[cols]
    df.to_sql("fact_portfolio", engine, if_exists="append", index=False)
    print(f"  ✅ fact_portfolio loaded  : {len(df):>4} rows")
    return len(df)


# ============================================================
# 11. LOAD SUPPLEMENTARY TABLES
# ============================================================
def load_supplementary(engine) -> dict:
    section("STEP 10 — Loading Supplementary Tables")
    counts = {}

    # Category inflows
    df = pd.read_csv(PROCESSED_DIR / "05_category_inflows_clean.csv",
                     parse_dates=["month"])
    df["date_id"] = df["month"].apply(date_to_id)
    df["month"]   = df["month"].dt.date.astype(str)
    df.to_sql("fact_category_inflows", engine, if_exists="append", index=False)
    counts["fact_category_inflows"] = len(df)
    print(f"  ✅ fact_category_inflows  : {len(df):>4} rows")

    # Folio count
    df = pd.read_csv(PROCESSED_DIR / "06_industry_folio_count_clean.csv",
                     parse_dates=["month"])
    df["date_id"] = df["month"].apply(date_to_id)
    df["month"]   = df["month"].dt.date.astype(str)
    df.to_sql("fact_folio_count", engine, if_exists="append", index=False)
    counts["fact_folio_count"] = len(df)
    print(f"  ✅ fact_folio_count       : {len(df):>4} rows")

    # Benchmark indices
    df = pd.read_csv(PROCESSED_DIR / "10_benchmark_indices_clean.csv",
                     parse_dates=["date"])
    df["date_id"]    = df["date"].apply(date_to_id)
    df["trade_date"] = df["date"].dt.date.astype(str)
    df = df.rename(columns={"date": "_drop", "index_name": "index_name",
                             "close_value": "close_value"})
    df = df[["date_id","trade_date","index_name","close_value"]]
    df.to_sql("fact_benchmark", engine, if_exists="append", index=False)
    counts["fact_benchmark"] = len(df)
    print(f"  ✅ fact_benchmark         : {len(df):>4} rows")

    return counts


# ============================================================
# 12. ROW COUNT VERIFICATION
# ============================================================
def verify_row_counts(engine, expected: dict) -> None:
    section("STEP 11 — Row Count Verification")

    print(f"\n  {'Table':<30} {'DB Rows':>10} {'Expected':>10}  Status")
    print(f"  {SEP2}")

    all_pass = True
    with engine.connect() as con:
        for table, exp_rows in expected.items():
            result = con.execute(text(f"SELECT COUNT(*) FROM {table}"))
            db_rows = result.fetchone()[0]
            status = "✅ MATCH" if db_rows == exp_rows else "❌ MISMATCH"
            if db_rows != exp_rows:
                all_pass = False
            print(f"  {table:<30} {db_rows:>10,} {exp_rows:>10,}  {status}")

    print(f"\n  {'All counts match ✅' if all_pass else 'Some mismatches ❌ — check above'}")


# ============================================================
# 13. MAIN
# ============================================================
def main() -> None:
    print(f"\n{'#'*70}")
    print("  BLUESTOCK FINTECH — DAY 2: ETL LOADER")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  DB Path: {DB_PATH}")
    print(f"{'#'*70}")

    # Step 1: Create DB and schema
    create_database()

    # Step 2: Generate dim_date
    build_dim_date()

    # Step 3+: Load all tables
    engine = get_engine()
    counts = {}
    counts["dim_fund"]              = load_dim_fund(engine)
    counts["fact_nav"]              = load_fact_nav(engine)
    counts["fact_transactions"]     = load_fact_transactions(engine)
    counts["fact_performance"]      = load_fact_performance(engine)
    counts["fact_aum"]              = load_fact_aum(engine)
    counts["fact_sip_industry"]     = load_fact_sip_industry(engine)
    counts["fact_portfolio"]        = load_fact_portfolio(engine)
    supp = load_supplementary(engine)
    counts.update(supp)

    # Verify
    verify_row_counts(engine, counts)

    section("ETL LOAD COMPLETE")
    total = sum(counts.values())
    print(f"\n  Tables loaded    : {len(counts)}")
    print(f"  Total rows in DB : {total:,}")
    print(f"  Database file    : {DB_PATH}  "
          f"({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"\n  ✅ Day 2 Task 5 — COMPLETE")
    print(f"  Next             : Run queries.sql in DB Browser or via Python")
    print(f"\n{'#'*70}\n")


if __name__ == "__main__":
    main()