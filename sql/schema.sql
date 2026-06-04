-- ============================================================
-- Bluestock Fintech — Mutual Fund Analytics Platform
-- FILE    : sql/schema.sql
-- DAY     : 2  —  SQLite Star Schema DDL
-- TASK    : 4
-- DATE    : 2026-06-04
-- ------------------------------------------------------------
-- DATABASE : bluestock_mf.db  (SQLite 3)
-- SCHEMA   : Star Schema
--            Dimensions : dim_fund, dim_date
--            Facts      : fact_nav, fact_transactions,
--                         fact_performance, fact_aum,
--                         fact_sip_industry, fact_portfolio
-- ------------------------------------------------------------
-- CONSTRAINTS:
--   [✓] All PKs defined
--   [✓] All FKs referencing dim_fund(amfi_code) or dim_date
--   [✓] NOT NULL on critical business columns
--   [✓] CHECK constraints for enum and range validation
--   [✓] Indexes on all FK columns for query performance
-- ============================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ============================================================
-- DROP ORDER: Facts first, then Dimensions
-- ============================================================
DROP TABLE IF EXISTS fact_portfolio;
DROP TABLE IF EXISTS fact_sip_industry;
DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

-- ============================================================
-- DIMENSION 1: dim_fund
-- Source      : 01_fund_master_clean.csv
-- Grain       : One row per mutual fund scheme (AMFI code)
-- PK          : amfi_code (AMFI-assigned 6-digit scheme code)
-- ============================================================
CREATE TABLE dim_fund (
    amfi_code           INTEGER     PRIMARY KEY,
    fund_house          TEXT        NOT NULL,
    scheme_name         TEXT        NOT NULL,
    category            TEXT        NOT NULL
                            CHECK(category IN ('Equity', 'Debt')),
    sub_category        TEXT        NOT NULL,
    plan                TEXT        NOT NULL
                            CHECK(plan IN ('Regular', 'Direct')),
    launch_date         DATE,
    benchmark           TEXT,
    expense_ratio_pct   REAL        NOT NULL
                            CHECK(expense_ratio_pct BETWEEN 0.1 AND 2.5),
    exit_load_pct       REAL        NOT NULL
                            CHECK(exit_load_pct >= 0.0),
    min_sip_amount      INTEGER     NOT NULL
                            CHECK(min_sip_amount > 0),
    min_lumpsum_amount  INTEGER     NOT NULL
                            CHECK(min_lumpsum_amount > 0),
    fund_manager        TEXT,
    risk_category       TEXT        NOT NULL
                            CHECK(risk_category IN (
                                'Low','Moderate','Moderately High',
                                'High','Very High'
                            )),
    sebi_category_code  TEXT
);

-- ============================================================
-- DIMENSION 2: dim_date
-- Source      : Generated (full calendar from 2022-01-01)
-- Grain       : One row per calendar date
-- PK          : date_id (YYYYMMDD integer format for fast joins)
-- ============================================================
CREATE TABLE dim_date (
    date_id         INTEGER     PRIMARY KEY,   -- e.g. 20220103
    full_date       DATE        NOT NULL UNIQUE,
    year            INTEGER     NOT NULL,
    quarter         INTEGER     NOT NULL CHECK(quarter BETWEEN 1 AND 4),
    month           INTEGER     NOT NULL CHECK(month BETWEEN 1 AND 12),
    month_name      TEXT        NOT NULL,
    week_of_year    INTEGER     NOT NULL,
    day_of_month    INTEGER     NOT NULL CHECK(day_of_month BETWEEN 1 AND 31),
    day_of_week     INTEGER     NOT NULL CHECK(day_of_week BETWEEN 0 AND 6),
    day_name        TEXT        NOT NULL,
    is_weekend      INTEGER     NOT NULL CHECK(is_weekend IN (0, 1)),
    is_business_day INTEGER     NOT NULL CHECK(is_business_day IN (0, 1)),
    fy_year         TEXT        NOT NULL,     -- e.g. 'FY2022-23'
    fy_quarter      TEXT        NOT NULL      -- e.g. 'Q1FY23'
);

-- ============================================================
-- FACT 1: fact_nav
-- Source  : 02_nav_history_clean.csv
-- Grain   : One row per fund per business day
-- ============================================================
CREATE TABLE fact_nav (
    nav_id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER     NOT NULL
                        REFERENCES dim_fund(amfi_code),
    date_id         INTEGER     NOT NULL
                        REFERENCES dim_date(date_id),
    nav             REAL        NOT NULL
                        CHECK(nav > 0),
    UNIQUE(amfi_code, date_id)
);

CREATE INDEX idx_fact_nav_amfi    ON fact_nav(amfi_code);
CREATE INDEX idx_fact_nav_date    ON fact_nav(date_id);
CREATE INDEX idx_fact_nav_both    ON fact_nav(amfi_code, date_id);

-- ============================================================
-- FACT 2: fact_transactions
-- Source  : 08_investor_transactions_clean.csv
-- Grain   : One row per investor transaction
-- ============================================================
CREATE TABLE fact_transactions (
    txn_id              INTEGER     PRIMARY KEY AUTOINCREMENT,
    investor_id         TEXT        NOT NULL,
    transaction_date    DATE        NOT NULL,
    date_id             INTEGER     NOT NULL
                            REFERENCES dim_date(date_id),
    amfi_code           INTEGER     NOT NULL
                            REFERENCES dim_fund(amfi_code),
    transaction_type    TEXT        NOT NULL
                            CHECK(transaction_type IN
                                ('SIP','Lumpsum','Redemption')),
    amount_inr          INTEGER     NOT NULL
                            CHECK(amount_inr > 0),
    state               TEXT        NOT NULL,
    city                TEXT        NOT NULL,
    city_tier           TEXT        NOT NULL
                            CHECK(city_tier IN ('T30','B30')),
    age_group           TEXT        NOT NULL
                            CHECK(age_group IN
                                ('18-25','26-35','36-45','46-55','56+')),
    gender              TEXT        NOT NULL
                            CHECK(gender IN ('Male','Female','Other')),
    annual_income_lakh  REAL,
    payment_mode        TEXT        NOT NULL,
    kyc_status          TEXT        NOT NULL
                            CHECK(kyc_status IN ('Verified','Pending','Unknown'))
);

CREATE INDEX idx_fact_txn_amfi    ON fact_transactions(amfi_code);
CREATE INDEX idx_fact_txn_date    ON fact_transactions(date_id);
CREATE INDEX idx_fact_txn_inv     ON fact_transactions(investor_id);
CREATE INDEX idx_fact_txn_type    ON fact_transactions(transaction_type);
CREATE INDEX idx_fact_txn_state   ON fact_transactions(state);

-- ============================================================
-- FACT 3: fact_performance
-- Source  : 07_scheme_performance_clean.csv
-- Grain   : One row per fund (point-in-time performance snapshot)
-- ============================================================
CREATE TABLE fact_performance (
    perf_id             INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code           INTEGER     NOT NULL UNIQUE
                            REFERENCES dim_fund(amfi_code),
    return_1yr_pct      REAL,
    return_3yr_pct      REAL,
    return_5yr_pct      REAL,
    benchmark_3yr_pct   REAL,
    alpha               REAL,
    beta                REAL,
    sharpe_ratio        REAL,
    sortino_ratio       REAL,
    std_dev_ann_pct     REAL,
    max_drawdown_pct    REAL,
    aum_crore           INTEGER,
    expense_ratio_pct   REAL,
    morningstar_rating  INTEGER     CHECK(morningstar_rating BETWEEN 1 AND 5),
    risk_grade          TEXT,
    anomaly_flag        TEXT        DEFAULT ''
);

CREATE INDEX idx_fact_perf_amfi ON fact_performance(amfi_code);

-- ============================================================
-- FACT 4: fact_aum
-- Source  : 03_aum_by_fund_house.csv (fund-house level AUM)
-- Grain   : One row per fund house per quarter
-- ============================================================
CREATE TABLE fact_aum (
    aum_id              INTEGER     PRIMARY KEY AUTOINCREMENT,
    date_id             INTEGER     NOT NULL
                            REFERENCES dim_date(date_id),
    report_date         DATE        NOT NULL,
    fund_house          TEXT        NOT NULL,
    aum_lakh_crore      REAL        NOT NULL CHECK(aum_lakh_crore > 0),
    aum_crore           INTEGER     NOT NULL CHECK(aum_crore > 0),
    num_schemes         INTEGER     NOT NULL CHECK(num_schemes > 0),
    UNIQUE(fund_house, report_date)
);

CREATE INDEX idx_fact_aum_date      ON fact_aum(date_id);
CREATE INDEX idx_fact_aum_house     ON fact_aum(fund_house);

-- ============================================================
-- FACT 5: fact_sip_industry
-- Source  : 04_monthly_sip_inflows_clean.csv
-- Grain   : One row per month (industry-level SIP data)
-- ============================================================
CREATE TABLE fact_sip_industry (
    sip_id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
    date_id                     INTEGER  NOT NULL
                                    REFERENCES dim_date(date_id),
    month                       DATE     NOT NULL UNIQUE,
    sip_inflow_crore            INTEGER  NOT NULL,
    active_sip_accounts_crore   REAL     NOT NULL,
    new_sip_accounts_lakh       REAL     NOT NULL,
    sip_aum_lakh_crore          REAL     NOT NULL,
    yoy_growth_pct              REAL     -- NULL for first 12 months
);

CREATE INDEX idx_fact_sip_date ON fact_sip_industry(date_id);

-- ============================================================
-- FACT 6: fact_portfolio
-- Source  : 09_portfolio_holdings_clean.csv
-- Grain   : One row per fund per stock holding
-- ============================================================
CREATE TABLE fact_portfolio (
    holding_id          INTEGER     PRIMARY KEY AUTOINCREMENT,
    amfi_code           INTEGER     NOT NULL
                            REFERENCES dim_fund(amfi_code),
    portfolio_date      DATE        NOT NULL,
    date_id             INTEGER     NOT NULL
                            REFERENCES dim_date(date_id),
    stock_symbol        TEXT        NOT NULL,
    stock_name          TEXT        NOT NULL,
    sector              TEXT        NOT NULL,
    weight_pct          REAL        NOT NULL CHECK(weight_pct > 0),
    market_value_cr     REAL        NOT NULL CHECK(market_value_cr > 0),
    current_price_inr   REAL        NOT NULL CHECK(current_price_inr > 0),
    UNIQUE(amfi_code, stock_symbol, portfolio_date)
);

CREATE INDEX idx_fact_port_amfi     ON fact_portfolio(amfi_code);
CREATE INDEX idx_fact_port_date     ON fact_portfolio(date_id);
CREATE INDEX idx_fact_port_sector   ON fact_portfolio(sector);

-- ============================================================
-- SUPPLEMENTARY: category_inflows
-- Source  : 05_category_inflows_clean.csv
-- Not a strict star-schema table but useful for BI queries
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_category_inflows (
    inflow_id           INTEGER     PRIMARY KEY AUTOINCREMENT,
    date_id             INTEGER     NOT NULL
                            REFERENCES dim_date(date_id),
    month               DATE        NOT NULL,
    category            TEXT        NOT NULL,
    net_inflow_crore    REAL        NOT NULL,
    UNIQUE(month, category)
);

CREATE INDEX idx_cat_inflow_date ON fact_category_inflows(date_id);

-- ============================================================
-- SUPPLEMENTARY: industry_folio_count
-- Source  : 06_industry_folio_count_clean.csv
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_folio_count (
    folio_id                INTEGER     PRIMARY KEY AUTOINCREMENT,
    date_id                 INTEGER     NOT NULL
                                REFERENCES dim_date(date_id),
    month                   DATE        NOT NULL UNIQUE,
    total_folios_crore      REAL        NOT NULL,
    equity_folios_crore     REAL        NOT NULL,
    debt_folios_crore       REAL        NOT NULL,
    hybrid_folios_crore     REAL        NOT NULL,
    others_folios_crore     REAL        NOT NULL
);

CREATE INDEX idx_folio_date ON fact_folio_count(date_id);

-- ============================================================
-- SUPPLEMENTARY: benchmark_indices
-- Source  : 10_benchmark_indices_clean.csv
-- ============================================================
CREATE TABLE IF NOT EXISTS fact_benchmark (
    benchmark_id    INTEGER     PRIMARY KEY AUTOINCREMENT,
    date_id         INTEGER     NOT NULL
                        REFERENCES dim_date(date_id),
    trade_date      DATE        NOT NULL,
    index_name      TEXT        NOT NULL,
    close_value     REAL        NOT NULL CHECK(close_value > 0),
    UNIQUE(trade_date, index_name)
);

CREATE INDEX idx_bench_date  ON fact_benchmark(date_id);
CREATE INDEX idx_bench_index ON fact_benchmark(index_name);

-- ============================================================
-- SCHEMA VERIFICATION QUERY (run after loading)
-- ============================================================
-- SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;