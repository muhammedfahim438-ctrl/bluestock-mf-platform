# 📖 Data Dictionary
## Bluestock Fintech — Mutual Fund Analytics Platform
**Version:** 1.0 | **Day:** 2 | **Date:** 2026-06-04

---

## Table of Contents
1. [dim_fund](#1-dim_fund)
2. [dim_date](#2-dim_date)
3. [fact_nav](#3-fact_nav)
4. [fact_transactions](#4-fact_transactions)
5. [fact_performance](#5-fact_performance)
6. [fact_aum](#6-fact_aum)
7. [fact_sip_industry](#7-fact_sip_industry)
8. [fact_portfolio](#8-fact_portfolio)
9. [fact_category_inflows](#9-fact_category_inflows)
10. [fact_folio_count](#10-fact_folio_count)
11. [fact_benchmark](#11-fact_benchmark)
12. [Business Glossary](#12-business-glossary)

---

## Schema Overview

```
STAR SCHEMA
                    ┌─────────────┐
                    │  dim_date   │
                    │  (date_id)  │
                    └──────┬──────┘
                           │
          ┌────────────────┼───────────────┐
          │                │               │
   ┌──────┴──────┐  ┌──────┴──────┐  ┌────┴────────┐
   │  fact_nav   │  │fact_transact│  │  fact_aum   │
   └──────┬──────┘  └──────┬──────┘  └─────────────┘
          │                │
          └────────────────┘
                    │
             ┌──────┴──────┐
             │  dim_fund   │
             │ (amfi_code) │
             └─────────────┘
```

---

## 1. dim_fund

**Source:** `01_fund_master.csv`
**Grain:** One row per mutual fund scheme
**Primary Key:** `amfi_code`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `amfi_code` | INTEGER | NO | Unique 6-digit scheme code assigned by AMFI (Association of Mutual Funds in India). Chronologically assigned at scheme registration. | `119551` |
| `fund_house` | TEXT | NO | Name of the Asset Management Company (AMC) managing the fund. | `SBI Mutual Fund` |
| `scheme_name` | TEXT | NO | Full official scheme name as registered with SEBI/AMFI. | `SBI Bluechip Fund - Regular Plan - Growth` |
| `category` | TEXT | NO | Broad SEBI asset class: `Equity` or `Debt`. | `Equity` |
| `sub_category` | TEXT | NO | SEBI-defined sub-category within the broad category. Determines investment mandate. | `Large Cap` |
| `plan` | TEXT | NO | Distribution channel. `Regular` includes distributor commission; `Direct` does not. Direct plans have lower expense ratios. | `Regular` |
| `launch_date` | DATE | YES | Date the scheme was launched and made available for investment. | `2006-02-14` |
| `benchmark` | TEXT | YES | Official benchmark index against which fund performance is measured. | `NIFTY 100 TRI` |
| `expense_ratio_pct` | REAL | NO | Annual fee charged by the fund house as a % of AUM. Range: 0.1%–2.5%. Direct plans always lower than Regular. | `1.54` |
| `exit_load_pct` | REAL | NO | Fee charged on redemption before the lock-in period. 0 = no exit load. | `1.0` |
| `min_sip_amount` | INTEGER | NO | Minimum monthly SIP investment amount in INR. | `500` |
| `min_lumpsum_amount` | INTEGER | NO | Minimum one-time investment amount in INR. | `1000` |
| `fund_manager` | TEXT | YES | Name of the lead fund manager responsible for investment decisions. | `Sohini Andani` |
| `risk_category` | TEXT | NO | SEBI-mandated risk label. Values: `Low`, `Moderate`, `Moderately High`, `High`, `Very High`. | `Moderate` |
| `sebi_category_code` | TEXT | YES | SEBI's internal category classification code (e.g., EC01 = Equity Large Cap). | `EC01` |

---

## 2. dim_date

**Source:** Generated programmatically (2022-01-01 → 2026-12-31)
**Grain:** One row per calendar date
**Primary Key:** `date_id`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `date_id` | INTEGER | NO | Surrogate key in YYYYMMDD format for fast integer joins. | `20220103` |
| `full_date` | DATE | NO | ISO 8601 calendar date. | `2022-01-03` |
| `year` | INTEGER | NO | Calendar year. | `2022` |
| `quarter` | INTEGER | NO | Calendar quarter (1–4). | `1` |
| `month` | INTEGER | NO | Calendar month number (1–12). | `1` |
| `month_name` | TEXT | NO | Full month name. | `January` |
| `week_of_year` | INTEGER | NO | ISO week number (1–52). | `1` |
| `day_of_month` | INTEGER | NO | Day of month (1–31). | `3` |
| `day_of_week` | INTEGER | NO | Day of week: 0=Monday, 6=Sunday. | `0` |
| `day_name` | TEXT | NO | Full weekday name. | `Monday` |
| `is_weekend` | INTEGER | NO | 1 if Saturday or Sunday, else 0. | `0` |
| `is_business_day` | INTEGER | NO | 1 if Monday–Friday, else 0. Does not account for market holidays. | `1` |
| `fy_year` | TEXT | NO | Indian Financial Year label (April–March). | `FY22-23` |
| `fy_quarter` | TEXT | NO | Indian FY quarter label (Q1=Apr–Jun). | `Q1FY23` |

---

## 3. fact_nav

**Source:** `02_nav_history.csv` (after cleaning + ffill)
**Grain:** One row per fund per business day
**Primary Key:** `nav_id` (auto-increment)
**Foreign Keys:** `amfi_code → dim_fund`, `date_id → dim_date`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `nav_id` | INTEGER | NO | Surrogate auto-increment PK. | `1` |
| `amfi_code` | INTEGER | NO | FK to dim_fund. Identifies the fund. | `119551` |
| `date_id` | INTEGER | NO | FK to dim_date. Trade date as YYYYMMDD. | `20220103` |
| `nav` | REAL | NO | Net Asset Value per unit in INR. Must be > 0. Weekend/holiday gaps filled via forward-fill from last trading day. | `54.3856` |

---

## 4. fact_transactions

**Source:** `08_investor_transactions.csv`
**Grain:** One row per investor transaction
**Primary Key:** `txn_id` (auto-increment)
**Foreign Keys:** `amfi_code → dim_fund`, `date_id → dim_date`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `txn_id` | INTEGER | NO | Surrogate auto-increment PK. | `1` |
| `investor_id` | TEXT | NO | Unique investor identifier (format: INVxxxxxx). 5,000 unique investors. | `INV003054` |
| `transaction_date` | DATE | NO | Date the transaction was executed. | `2024-01-01` |
| `date_id` | INTEGER | NO | FK to dim_date. | `20240101` |
| `amfi_code` | INTEGER | NO | FK to dim_fund. Fund in which transaction occurred. | `119092` |
| `transaction_type` | TEXT | NO | Type of transaction. `SIP`=monthly systematic investment, `Lumpsum`=one-time investment, `Redemption`=withdrawal. | `SIP` |
| `amount_inr` | INTEGER | NO | Transaction amount in Indian Rupees. Must be > 0. | `1834` |
| `state` | TEXT | NO | Indian state of the investor. | `Telangana` |
| `city` | TEXT | NO | City of the investor. | `Hyderabad` |
| `city_tier` | TEXT | NO | AMFI city classification. `T30`=Top 30 cities (higher financial literacy), `B30`=Beyond Top 30. | `T30` |
| `age_group` | TEXT | NO | Investor age bracket: `18-25`, `26-35`, `36-45`, `46-55`, `56+`. | `56+` |
| `gender` | TEXT | NO | Investor gender: `Male`, `Female`, `Other`. | `Female` |
| `annual_income_lakh` | REAL | YES | Investor's self-declared annual income in lakhs (₹). | `77.1` |
| `payment_mode` | TEXT | NO | Payment method used: `UPI`, `Mandate`, `Cheque`, `Net Banking`. | `UPI` |
| `kyc_status` | TEXT | NO | KYC compliance status. `Verified`=fully onboarded, `Pending`=in process. | `Verified` |

---

## 5. fact_performance

**Source:** `07_scheme_performance.csv`
**Grain:** One row per fund (point-in-time snapshot)
**Primary Key:** `perf_id` (auto-increment)
**Foreign Key:** `amfi_code → dim_fund`

| Column | Data Type | Nullable | Business Definition | Formula / Note |
|--------|-----------|----------|---------------------|----------------|
| `perf_id` | INTEGER | NO | Surrogate auto-increment PK. | — |
| `amfi_code` | INTEGER | NO | FK to dim_fund. | — |
| `return_1yr_pct` | REAL | YES | Absolute return over last 1 year (%). | `(NAV_now / NAV_1yr_ago - 1) × 100` |
| `return_3yr_pct` | REAL | YES | CAGR over last 3 years (%). | `(NAV_now/NAV_3yr_ago)^(1/3) - 1` |
| `return_5yr_pct` | REAL | YES | CAGR over last 5 years (%). | `(NAV_now/NAV_5yr_ago)^(1/5) - 1` |
| `benchmark_3yr_pct` | REAL | YES | Benchmark index 3-year CAGR for comparison. | — |
| `alpha` | REAL | YES | Excess return over benchmark. Positive = fund manager adds value. | `alpha = Rp - [Rf + β(Rm - Rf)]` |
| `beta` | REAL | YES | Sensitivity to market movements. β=1 means moves with market. | `β = Cov(Rp,Rm) / Var(Rm)` |
| `sharpe_ratio` | REAL | YES | Return per unit of total risk. Higher is better. Rf=6.5%. | `(Rp - Rf) / σp × √252` |
| `sortino_ratio` | REAL | YES | Return per unit of downside risk only. More relevant for investors. | `(Rp - Rf) / σ_downside × √252` |
| `std_dev_ann_pct` | REAL | YES | Annualised standard deviation of daily returns (%). Measure of total volatility. | `σ_daily × √252` |
| `max_drawdown_pct` | REAL | YES | Largest peak-to-trough decline (%). Always ≤ 0. | `(Trough - Peak) / Peak × 100` |
| `aum_crore` | INTEGER | YES | Assets Under Management in Crores (₹). | — |
| `expense_ratio_pct` | REAL | YES | Annual fee as % of AUM (duplicate from dim_fund for convenience). | — |
| `morningstar_rating` | INTEGER | YES | Morningstar star rating (1–5). Based on risk-adjusted returns. | — |
| `risk_grade` | TEXT | YES | Qualitative risk label: `Low`, `Moderate`, `High`, `Very High`. | — |
| `anomaly_flag` | TEXT | YES | Semicolon-separated anomaly codes: `HIGH_SHARPE`, `EXP_RATIO_OOR`, `NEGATIVE_BETA`. Empty = clean. | — |

---

## 6. fact_aum

**Source:** `03_aum_by_fund_house.csv`
**Grain:** One row per fund house per quarter
**Primary Key:** `aum_id` (auto-increment)
**Foreign Key:** `date_id → dim_date`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `aum_id` | INTEGER | NO | Surrogate PK. | `1` |
| `date_id` | INTEGER | NO | FK to dim_date (quarter-end date). | `20220331` |
| `report_date` | DATE | NO | Quarter-end reporting date. | `2022-03-31` |
| `fund_house` | TEXT | NO | AMC name. | `SBI Mutual Fund` |
| `aum_lakh_crore` | REAL | NO | AUM in lakh crore (₹). 1 lakh crore = ₹1 trillion. | `6.05` |
| `aum_crore` | INTEGER | NO | AUM in crore (₹). 1 crore = ₹10 million. | `605000` |
| `num_schemes` | INTEGER | NO | Total active schemes managed by this fund house. | `186` |

---

## 7. fact_sip_industry

**Source:** `04_monthly_sip_inflows.csv`
**Grain:** One row per month (industry aggregate)
**Primary Key:** `sip_id` (auto-increment)
**Foreign Key:** `date_id → dim_date`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `sip_id` | INTEGER | NO | Surrogate PK. | `1` |
| `date_id` | INTEGER | NO | FK to dim_date (first day of month). | `20220101` |
| `month` | DATE | NO | First day of the month (YYYY-MM-01). | `2022-01-01` |
| `sip_inflow_crore` | INTEGER | NO | Total SIP collections industry-wide in that month (₹ Crore). | `11517` |
| `active_sip_accounts_crore` | REAL | NO | Total active SIP accounts in crore units. | `4.91` |
| `new_sip_accounts_lakh` | REAL | NO | New SIP accounts registered in that month (lakh). | `9.1` |
| `sip_aum_lakh_crore` | REAL | NO | Total SIP AUM at month-end (₹ lakh crore). | `4.80` |
| `yoy_growth_pct` | REAL | **YES** | Year-on-year growth in SIP inflows (%). **NULL for first 12 months** (Jan–Dec 2022) — no prior year baseline exists. Do NOT impute. | `31.5` |

---

## 8. fact_portfolio

**Source:** `09_portfolio_holdings.csv`
**Grain:** One row per fund per stock per portfolio date
**Primary Key:** `holding_id` (auto-increment)
**Foreign Keys:** `amfi_code → dim_fund`, `date_id → dim_date`

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `holding_id` | INTEGER | NO | Surrogate PK. | `1` |
| `amfi_code` | INTEGER | NO | FK to dim_fund. | `119551` |
| `portfolio_date` | DATE | NO | Snapshot date of the holdings disclosure. | `2025-12-31` |
| `date_id` | INTEGER | NO | FK to dim_date. | `20251231` |
| `stock_symbol` | TEXT | NO | NSE/BSE ticker symbol (uppercase). | `POWERGRID` |
| `stock_name` | TEXT | NO | Full company name. | `Power Grid Corporation` |
| `sector` | TEXT | NO | GICS-style sector classification. | `Utilities` |
| `weight_pct` | REAL | NO | Stock's % weight in the fund portfolio. Must be > 0. | `13.85` |
| `market_value_cr` | REAL | NO | Market value of holding in ₹ Crore at portfolio date. | `737.09` |
| `current_price_inr` | REAL | NO | Stock price in INR at portfolio date. | `6011.08` |

---

## 9. fact_category_inflows

**Source:** `05_category_inflows.csv`
**Grain:** One row per category per month
**Note:** Category `Value/Contra` normalised to `Value` during ETL.

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `inflow_id` | INTEGER | NO | Surrogate PK. | `1` |
| `date_id` | INTEGER | NO | FK to dim_date. | `20240401` |
| `month` | DATE | NO | First day of the month. | `2024-04-01` |
| `category` | TEXT | NO | Fund category (normalised). | `Large Cap` |
| `net_inflow_crore` | REAL | NO | Net inflows (inflows minus redemptions) in ₹ Crore. Can theoretically be negative (net outflow). | `2413.0` |

---

## 10. fact_folio_count

**Source:** `06_industry_folio_count.csv`
**Grain:** One row per quarter (industry-level folio data)

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `folio_id` | INTEGER | NO | Surrogate PK. | `1` |
| `date_id` | INTEGER | NO | FK to dim_date. | `20220101` |
| `month` | DATE | NO | Quarter start date. | `2022-01-01` |
| `total_folios_crore` | REAL | NO | Total investor accounts (folios) industry-wide in crore. | `13.26` |
| `equity_folios_crore` | REAL | NO | Folios in equity funds in crore. | `9.28` |
| `debt_folios_crore` | REAL | NO | Folios in debt funds in crore. | `1.86` |
| `hybrid_folios_crore` | REAL | NO | Folios in hybrid funds in crore. | `0.80` |
| `others_folios_crore` | REAL | NO | Folios in other fund types in crore. | `1.33` |

---

## 11. fact_benchmark

**Source:** `10_benchmark_indices.csv`
**Grain:** One row per index per trading day

| Column | Data Type | Nullable | Business Definition | Example |
|--------|-----------|----------|---------------------|---------|
| `benchmark_id` | INTEGER | NO | Surrogate PK. | `1` |
| `date_id` | INTEGER | NO | FK to dim_date. | `20220103` |
| `trade_date` | DATE | NO | Trading date. | `2022-01-03` |
| `index_name` | TEXT | NO | Benchmark index identifier. Values: `NIFTY50`, `NIFTY100`, `NIFTY_MIDCAP150`, `BSE_SMALLCAP`, `NIFTY500`, `CRISIL_LIQUID`, `CRISIL_GILT`. | `NIFTY50` |
| `close_value` | REAL | NO | Index closing value on trade date. Must be > 0. | `17492.79` |

---

## 12. Business Glossary

| Term | Definition |
|------|-----------|
| **AMFI** | Association of Mutual Funds in India. Regulates and assigns scheme codes. |
| **AMC** | Asset Management Company. The fund house that manages and operates mutual fund schemes. |
| **AUM** | Assets Under Management. Total market value of assets managed by a fund or AMC. |
| **NAV** | Net Asset Value. Per-unit price of a mutual fund scheme = (Total Assets - Liabilities) / Units. |
| **SIP** | Systematic Investment Plan. Fixed monthly auto-debit investment into a mutual fund. |
| **SEBI** | Securities and Exchange Board of India. Mutual fund industry regulator. |
| **TRI** | Total Return Index. Benchmark variant that includes dividend reinvestment. Preferred for performance comparison. |
| **Expense Ratio** | Annual management fee as % of AUM. Deducted daily from NAV. Lower = more investor-friendly. |
| **Exit Load** | Penalty fee (% of NAV) charged if investor redeems before minimum holding period. |
| **Alpha** | Fund's excess return over what would be predicted by its beta. Positive alpha = manager skill. |
| **Beta** | Fund's sensitivity to market. β=1 moves with market; β<1 less volatile; β>1 more volatile. |
| **Sharpe Ratio** | (Return - Risk-Free Rate) / Std Dev. Risk-adjusted return. Higher = better. Rf=6.5% used. |
| **Sortino Ratio** | Like Sharpe but only penalises downside volatility. More relevant for loss-averse investors. |
| **Max Drawdown** | Largest peak-to-trough portfolio decline. Always negative. Measures worst-case loss. |
| **HHI** | Herfindahl-Hirschman Index. Sum of squared portfolio weights. Measures concentration risk. |
| **T30/B30** | Top 30 / Beyond Top 30 cities by AMFI classification. T30 cities drive most AUM. |
| **CAGR** | Compound Annual Growth Rate. Annualised return assuming compounding. |
| **Folio** | Unique investor account number within a fund. One investor can have multiple folios. |
| **KYC** | Know Your Customer. Mandatory identity verification for mutual fund investment in India. |
| **Direct Plan** | Mutual fund plan bought without a distributor. Lower expense ratio than Regular plan. |
| **Regular Plan** | Mutual fund plan bought via a distributor/advisor. Higher expense ratio due to commission. |

---

*Generated by Bluestock Fintech Capstone Team — Day 2, 2026-06-04*