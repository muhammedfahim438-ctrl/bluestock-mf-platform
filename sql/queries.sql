-- ============================================================
-- Bluestock Fintech — Mutual Fund Analytics Platform
-- FILE    : sql/queries.sql
-- DAY     : 2  —  Analytical SQL Queries
-- TASK    : 6
-- DATE    : 2026-06-04
-- ------------------------------------------------------------
-- 10 Analytical Queries covering:
--   Q01 — Top 5 funds by AUM
--   Q02 — Average NAV per month (industry)
--   Q03 — SIP YoY growth trend
--   Q04 — Transactions by state
--   Q05 — Funds with expense_ratio < 1%
--   Q06 — Best performing funds (3-year return vs benchmark)
--   Q07 — Investor age group distribution by transaction value
--   Q08 — Sector concentration in portfolio holdings
--   Q09 — Monthly SIP inflow trend with running total
--   Q10 — Fund risk-adjusted return ranking (Sharpe ratio)
-- ============================================================

-- ============================================================
-- Q01: Top 5 Fund Houses by Latest AUM
-- Business use: Identify market leaders by assets managed
-- ============================================================
SELECT
    fa.fund_house,
    fa.report_date,
    ROUND(fa.aum_lakh_crore, 2)         AS aum_lakh_crore,
    fa.aum_crore,
    fa.num_schemes,
    RANK() OVER (
        ORDER BY fa.aum_crore DESC
    )                                   AS aum_rank
FROM fact_aum fa
WHERE fa.report_date = (
    SELECT MAX(report_date) FROM fact_aum
)
ORDER BY fa.aum_crore DESC
LIMIT 5;

-- ============================================================
-- Q02: Average Industry NAV Per Month (across all funds)
-- Business use: Track overall market direction monthly
-- ============================================================
SELECT
    dd.year,
    dd.month_name,
    dd.fy_quarter,
    ROUND(AVG(fn.nav), 4)               AS avg_nav,
    ROUND(MIN(fn.nav), 4)               AS min_nav,
    ROUND(MAX(fn.nav), 4)               AS max_nav,
    COUNT(DISTINCT fn.amfi_code)        AS num_funds
FROM fact_nav fn
JOIN dim_date dd ON fn.date_id = dd.date_id
WHERE dd.is_business_day = 1
  AND dd.day_of_month = 1   -- first business day of month as proxy
GROUP BY dd.year, dd.month
ORDER BY dd.year, dd.month;

-- ============================================================
-- Q03: SIP YoY Growth Trend
-- Business use: Track SIP industry growth year over year
-- ============================================================
SELECT
    dd.year,
    dd.month_name,
    fs.sip_inflow_crore,
    fs.active_sip_accounts_crore,
    fs.new_sip_accounts_lakh,
    ROUND(fs.yoy_growth_pct, 2)         AS yoy_growth_pct,
    SUM(fs.sip_inflow_crore) OVER (
        PARTITION BY dd.year
        ORDER BY dd.month
        ROWS UNBOUNDED PRECEDING
    )                                   AS ytd_sip_inflow
FROM fact_sip_industry fs
JOIN dim_date dd ON fs.date_id = dd.date_id
ORDER BY dd.year, dd.month;

-- ============================================================
-- Q04: Total Transaction Value by State
-- Business use: Geographic distribution of investment activity
-- ============================================================
SELECT
    ft.state,
    ft.city_tier,
    COUNT(*)                            AS num_transactions,
    COUNT(DISTINCT ft.investor_id)      AS unique_investors,
    SUM(ft.amount_inr)                  AS total_amount_inr,
    ROUND(AVG(ft.amount_inr), 0)        AS avg_amount_inr,
    ROUND(
        100.0 * SUM(ft.amount_inr) /
        SUM(SUM(ft.amount_inr)) OVER (), 2
    )                                   AS pct_of_total
FROM fact_transactions ft
GROUP BY ft.state, ft.city_tier
ORDER BY total_amount_inr DESC;

-- ============================================================
-- Q05: Funds with Expense Ratio < 1% (Low-Cost Funds)
-- Business use: Identify investor-friendly low-cost options
-- ============================================================
SELECT
    df.amfi_code,
    df.scheme_name,
    df.fund_house,
    df.category,
    df.sub_category,
    df.plan,
    df.expense_ratio_pct,
    df.risk_category,
    fp.return_3yr_pct,
    fp.sharpe_ratio,
    fp.morningstar_rating
FROM dim_fund df
LEFT JOIN fact_performance fp ON df.amfi_code = fp.amfi_code
WHERE df.expense_ratio_pct < 1.0
ORDER BY df.expense_ratio_pct ASC;

-- ============================================================
-- Q06: Alpha Generators — Funds Beating Benchmark (3-Year)
-- Business use: Identify active funds adding value over index
-- ============================================================
SELECT
    df.amfi_code,
    df.scheme_name,
    df.fund_house,
    df.sub_category,
    df.plan,
    ROUND(fp.return_3yr_pct, 2)         AS return_3yr_pct,
    ROUND(fp.benchmark_3yr_pct, 2)      AS benchmark_3yr_pct,
    ROUND(fp.alpha, 2)                  AS alpha,
    ROUND(fp.beta, 2)                   AS beta,
    ROUND(fp.sharpe_ratio, 4)           AS sharpe_ratio,
    fp.morningstar_rating,
    CASE
        WHEN fp.return_3yr_pct > fp.benchmark_3yr_pct THEN '✅ Beats Benchmark'
        ELSE '❌ Lags Benchmark'
    END                                 AS vs_benchmark
FROM fact_performance fp
JOIN dim_fund df ON fp.amfi_code = df.amfi_code
ORDER BY fp.alpha DESC;

-- ============================================================
-- Q07: Transaction Value by Age Group and Transaction Type
-- Business use: Understand investor demographics & behaviour
-- ============================================================
SELECT
    ft.age_group,
    ft.transaction_type,
    ft.gender,
    COUNT(*)                            AS num_transactions,
    SUM(ft.amount_inr)                  AS total_amount_inr,
    ROUND(AVG(ft.amount_inr), 0)        AS avg_amount_inr,
    ROUND(AVG(ft.annual_income_lakh), 2) AS avg_income_lakh
FROM fact_transactions ft
GROUP BY ft.age_group, ft.transaction_type, ft.gender
ORDER BY ft.age_group, ft.transaction_type, ft.gender;

-- ============================================================
-- Q08: Sector Concentration in Portfolio Holdings
-- Business use: Identify over/under-weight sectors across funds
-- ============================================================
SELECT
    fp.sector,
    COUNT(DISTINCT fp.amfi_code)        AS num_funds,
    ROUND(AVG(fp.weight_pct), 2)        AS avg_weight_pct,
    ROUND(SUM(fp.market_value_cr), 2)   AS total_market_value_cr,
    ROUND(
        100.0 * SUM(fp.market_value_cr) /
        SUM(SUM(fp.market_value_cr)) OVER (), 2
    )                                   AS sector_share_pct,
    -- HHI per sector: sum of squared weights
    ROUND(SUM(fp.weight_pct * fp.weight_pct), 4) AS sector_hhi
FROM fact_portfolio fp
GROUP BY fp.sector
ORDER BY total_market_value_cr DESC;

-- ============================================================
-- Q09: Monthly SIP Inflow Trend with Running Total
-- Business use: Track cumulative SIP mobilisation over time
-- ============================================================
SELECT
    fs.month,
    dd.year,
    dd.month_name,
    fs.sip_inflow_crore,
    fs.active_sip_accounts_crore,
    SUM(fs.sip_inflow_crore) OVER (
        ORDER BY fs.month
        ROWS UNBOUNDED PRECEDING
    )                                   AS cumulative_sip_inflow,
    ROUND(
        100.0 * (fs.sip_inflow_crore -
            LAG(fs.sip_inflow_crore) OVER (ORDER BY fs.month)) /
            NULLIF(LAG(fs.sip_inflow_crore) OVER (ORDER BY fs.month), 0),
        2
    )                                   AS mom_growth_pct
FROM fact_sip_industry fs
JOIN dim_date dd ON fs.date_id = dd.date_id
ORDER BY fs.month;

-- ============================================================
-- Q10: Risk-Adjusted Return Ranking (Sharpe Ratio Leaderboard)
-- Business use: Find funds with best return per unit of risk
-- ============================================================
SELECT
    df.amfi_code,
    df.scheme_name,
    df.fund_house,
    df.sub_category,
    df.plan,
    df.risk_category,
    ROUND(fp.return_1yr_pct, 2)         AS return_1yr_pct,
    ROUND(fp.return_3yr_pct, 2)         AS return_3yr_pct,
    ROUND(fp.sharpe_ratio, 4)           AS sharpe_ratio,
    ROUND(fp.sortino_ratio, 4)          AS sortino_ratio,
    ROUND(fp.max_drawdown_pct, 2)       AS max_drawdown_pct,
    ROUND(fp.std_dev_ann_pct, 2)        AS std_dev_ann_pct,
    fp.morningstar_rating,
    fp.anomaly_flag,
    RANK() OVER (
        ORDER BY fp.sharpe_ratio DESC
    )                                   AS sharpe_rank,
    RANK() OVER (
        PARTITION BY df.sub_category
        ORDER BY fp.sharpe_ratio DESC
    )                                   AS sharpe_rank_in_category
FROM fact_performance fp
JOIN dim_fund df ON fp.amfi_code = df.amfi_code
ORDER BY fp.sharpe_ratio DESC;

-- ============================================================
-- BONUS Q11: KYC Status Impact on Transaction Volume
-- Business use: Compliance and onboarding insight
-- ============================================================
SELECT
    ft.kyc_status,
    COUNT(*)                            AS num_transactions,
    COUNT(DISTINCT ft.investor_id)      AS unique_investors,
    SUM(ft.amount_inr)                  AS total_amount_inr,
    ROUND(AVG(ft.amount_inr), 0)        AS avg_amount_inr
FROM fact_transactions ft
GROUP BY ft.kyc_status
ORDER BY total_amount_inr DESC;