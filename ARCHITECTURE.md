# Macrolytics Architecture

This document describes the current architecture, data flows, design decisions,
and technical conventions of Macrolytics.

Macrolytics is a macroeconomic data platform focused primarily on Argentina.
It combines automated ETL pipelines, a version-controlled Dolt database,
DoltHub as the public data layer, and a React frontend deployed through
GitHub Pages.

---

## System Overview

```text
┌──────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                         │
├──────────────────────────────────────────────────────────────┤
│ Argentina Datos API                                         │
│   └─ UVA                                                    │
│                                                              │
│ Ámbito Financiero                                           │
│   ├─ Official USD/ARS                                       │
│   ├─ MEP USD/ARS                                            │
│   ├─ Blue USD/ARS                                           │
│   └─ Crypto USD/ARS                                         │
│                                                              │
│ Datos Argentina                                             │
│   ├─ IPC / INDEC                                            │
│   ├─ EMAE / INDEC                                           │
│   ├─ Foreign Trade / INDEC                                  │
│   ├─ Consumer Confidence / UTDT                             │
│   └─ IMIG fiscal / tax series                               │
│                                                              │
│ Ministerio de Economía / ONP                                │
│   └─ Monthly AIF fiscal-account Excel workbooks             │
│                                                              │
│ BCRA                                                        │
│   └─ CER historical XLS files                               │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                          ETL LAYER                           │
├──────────────────────────────────────────────────────────────┤
│ FX / UVA                                                    │
│   daily_update.py                                           │
│   ├─ utils/fetch_uva.py                                     │
│   └─ utils/fetch_usd_data.py                                │
│                                                              │
│ Monthly macro datasets                                      │
│   populate_ipc_arg.py                                       │
│   populate_emae_arg.py                                      │
│   populate_trade_arg.py                                     │
│   populate_fiscal_arg.py                                    │
│   populate_consumer_confidence_arg.py                       │
│                                                              │
│ Historical / auxiliary                                      │
│   populate_cer_historical.py                                │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                       DATABASE LAYER                         │
├──────────────────────────────────────────────────────────────┤
│ etl/utils/db_manager.py                                     │
│                                                              │
│ DoltDBManager                                               │
│   ├─ connect()                                              │
│   ├─ query()                                                │
│   ├─ insert_fx_rate()                                       │
│   ├─ dolt_add()                                             │
│   ├─ dolt_commit()                                          │
│   └─ disconnect()                                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    LOCAL DOLT DATABASE                       │
│                      macroeconomia                           │
├──────────────────────────────────────────────────────────────┤
│ fx_rate                                                     │
│ ipc_argentina                                               │
│ emae                                                        │
│ trade_argentina                                             │
│ fiscal_argentina                                            │
│ consumer_confidence_argentina                               │
│ additional macroeconomic tables                             │
└──────────────────────────────────────────────────────────────┘
                              │
                    Dolt commit + push
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                           DOLTHUB                            │
│                rbasa/macroeconomia : main                   │
│                                                              │
│ Public versioned analytical database                        │
└──────────────────────────────────────────────────────────────┘
                              │
                    DoltHub HTTP SQL API
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND                        │
├──────────────────────────────────────────────────────────────┤
│ React + Vite                                                │
│ React Router                                                │
│ Plotly                                                      │
│                                                              │
│ frontend/src/api/dolt.js                                    │
│        ↓                                                    │
│ Pages → Components → Utils                                  │
└──────────────────────────────────────────────────────────────┘
                              │
                        Vite build
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                      GITHUB PAGES                           │
│                                                              │
│ https://rbasa.github.io/macrolytics/                        │
└──────────────────────────────────────────────────────────────┘
```

---

# Repository Responsibilities

Macrolytics uses two repositories with different responsibilities.

## Code Repository

```text
rbasa/macrolytics
```

Contains:

- ETL code
- React frontend
- GitHub Actions
- documentation
- data-processing utilities
- analytical notebooks

## Data Repository

```text
rbasa/macroeconomia
```

Hosted in DoltHub.

Contains the versioned macroeconomic database used by the frontend and ETLs.

This separation is intentional:

```text
macrolytics
    → application and ETL code

macroeconomia
    → versioned economic data
```

---

# ETL Architecture

## General Pattern

Most ETLs follow the same pattern:

```text
Fetch
  ↓
Normalize / Transform
  ↓
DataFrame
  ↓
INSERT ... ON DUPLICATE KEY UPDATE
  ↓
dolt_add()
  ↓
dolt_commit()
```

The GitHub Actions workflow performs the final:

```text
dolt push origin main
```

This means each ETL is responsible for committing its own logical dataset
while the workflow is responsible for publishing all resulting commits to
DoltHub.

---

# ETL Design Principles

## 1. Deterministic Data Sources

Whenever possible, statistical series use fixed official IDs.

Example:

```python
IPC_SERIES = {
    "nivel_general":
        "145.3_INGNACNAL_DICI_M_15",
}
```

Avoid dynamically selecting economic series through fuzzy metadata searches.

A previous fiscal ETL implementation dynamically searched Datos Argentina
metadata and sometimes matched economically different concepts.

For economic datasets:

```text
explicit official series ID
    >
heuristic metadata matching
```

---

## 2. Never Invent Economic Observations

Missing published observations are stored as:

```sql
NULL
```

They must not be replaced with:

```text
0
```

unless the official source explicitly publishes zero.

---

## 3. Do Not Infer Accounting Identities in ETL

When an official source publishes a total directly, store the published total.

Example:

```text
GASTOS DE CONSUMO Y OPERACION
```

should be read directly from the official fiscal statement instead of being
reconstructed as:

```text
Remuneraciones
+ Bienes y Servicios
+ Otros Gastos
```

This preserves fidelity to the official source.

Derived analytical metrics may be computed in the frontend or analytical
layer when appropriate.

---

## 4. Preserve Published Periods

Monthly data is stored using the date returned by the source, normally:

```text
YYYY-MM-01
```

The ETL should not convert monthly observations to month-end dates.

---

## 5. Recent-Window Updates

Most monthly APIs are queried using a recent rolling window:

```text
last = 5
last = 6
```

rather than downloading the entire history every day.

The ETL then uses:

```sql
INSERT ... ON DUPLICATE KEY UPDATE
```

This allows Macrolytics to capture:

- new periods
- revised historical observations
- source corrections

Historical initialization can use:

```text
LAST_PERIODS = 1000
```

when required.

---

# Data Sources and Tables

## FX and UVA

### Sources

UVA:

```text
Argentina Datos API
```

USD exchange rates:

```text
Ámbito Financiero historical endpoints
```

### Table

```sql
fx_rate (
    DATE DATE,
    pair VARCHAR,
    kind VARCHAR,
    rate DECIMAL,
    PRIMARY KEY (DATE, pair, kind)
)
```

### Pairs

| Pair | Description |
|---|---|
| `USD_ARS` | Official USD/ARS |
| `USDM_ARS` | MEP USD/ARS |
| `USDB_ARS` | Blue USD/ARS |
| `USDC_ARS` | Crypto USD/ARS |
| `UVA_ARS` | UVA index in ARS |

The FX table is normalized because new rates and instruments can be added
without schema changes.

---

# IPC Argentina

## Source

```text
Datos Argentina
Underlying source: INDEC
```

ETL:

```text
etl/populate_ipc_arg.py
```

Table:

```text
ipc_argentina
```

Includes:

- General CPI
- Food and non-alcoholic beverages
- Alcohol and tobacco
- Clothing
- Housing and utilities
- Household equipment
- Health
- Transport
- Communications
- Recreation
- Education
- Restaurants and hotels
- Other goods and services
- Seasonal
- Core
- Regulated
- Goods
- Services

The API is queried using multiple series IDs together and a recent `last=N`
window.

---

# Economic Activity

## Source

```text
Datos Argentina
Underlying source: INDEC
```

ETL:

```text
etl/populate_emae_arg.py
```

Table:

```text
emae
```

Contains:

- EMAE general index
- seasonally adjusted index
- trend-cycle index
- sector-level activity indices

---

# Foreign Trade

## Source

```text
Datos Argentina
Underlying source: INDEC / Intercambio Comercial Argentino
```

ETL:

```text
etl/populate_trade_arg.py
```

Table:

```text
trade_argentina
```

Contains:

- exports
- imports
- trade balance
- exports by major categories
- imports by economic use

Values are primarily expressed in millions of USD.

---

# Fiscal Accounts

## Objective

The fiscal dataset should reproduce the official monthly:

```text
Cuenta Ahorro - Inversión - Financiamiento
Sector Público Nacional
Base Caja
```

and additionally provide detailed tax revenue by tax.

Table:

```text
fiscal_argentina
```

## Main Fiscal Source

Official monthly Excel workbooks published by:

```text
Ministerio de Economía
Oficina Nacional de Presupuesto
```

The ETL reads the published `TOTAL` column directly.

Required lines include:

### Current Revenue

- Current revenue
- Tax revenue
- Social-security contributions
- Non-tax revenue
- Sales of goods and services
- Operating revenue
- Net property income
- Current transfers
- Other revenue
- Operating surplus of public companies

### Current Expenditure

- Current expenditure
- Consumption and operations
  - Compensation
  - Goods and services
  - Other expenditure
- Interest and other property income
  - Net interest
  - Other income
- Social-security benefits
- Other current expenditure
- Current transfers
  - Private sector
  - Public sector
    - Provinces and CABA
    - Universities
    - Other
  - External sector
- Other expenditure
- Public-company operating deficit

### Capital Accounts

- Economic result
- Capital resources
- Capital expenditure
- Direct investment
- Capital transfers
  - Provinces and CABA
  - Other
- Financial investment
  - Provinces and CABA
  - Other

### Figurative Transactions

- Revenue before figurative transactions
- Expenditure before figurative transactions
- Financial result before figurative transactions
- Figurative contributions
  - Treasury
  - Earmarked resources
  - Decentralized organizations
  - Social security
  - PAMI / fiduciary funds / others
- Figurative expenditure

### Final Results

- Revenue after figurative transactions
- Primary expenditure after figurative transactions
- Expenditure after figurative transactions
- Primary result
- Financial result

### Memo Items

- BCRA income received
- Public income received by FGS and others
- Intra-public-sector interest payments

---

## Detailed Tax Revenue

Detailed tax composition is loaded from:

```text
Datos Argentina / IMIG
```

using fixed official IDs.

Includes:

- VAT
- Income tax
- Debit and credit tax
- Personal assets tax
- Fuel taxes
- Export duties
- Import duties
- Internal taxes
- Other tax revenue

The fiscal ETL must not use fuzzy metadata matching to select these series.

---

# Consumer Expectations

Table:

```text
consumer_confidence_argentina
```

Source:

```text
UTDT
republished through Datos Argentina
```

Main series:

- National Consumer Confidence Index
- Capital
- GBA
- Interior
- Personal situation
- Macroeconomic situation
- Durable goods and real estate

For index-based indicators, analysis should focus primarily on:

- current level
- temporal trajectory
- monthly change in index points
- 12-month change in index points
- regional divergence
- component divergence

A change in an index should not automatically be interpreted as a conventional
percentage return.

Future expectation indicators may include:

- Government Confidence Index
- business confidence
- inflation expectations

---

# CER

Historical CER data can be sourced from:

```text
BCRA XLS files
```

Current historical script:

```text
etl/populate_cer_historical.py
```

This script predates the current ETL conventions and should eventually be
migrated to:

```text
DoltDBManager
standard upsert logic
standard Dolt commit handling
```

---

# Database Modeling Strategy

Macrolytics intentionally uses two database modeling styles.

## Normalized Time Series

Used for heterogeneous high-frequency metrics:

```text
fx_rate
```

Structure:

```text
date + pair + kind + value
```

Advantages:

- easy addition of new FX series
- no schema migration for each rate
- efficient cross-rate queries

## Domain Tables

Used for cohesive economic datasets:

```text
ipc_argentina
emae
trade_argentina
fiscal_argentina
consumer_confidence_argentina
```

These use:

```text
one row per period
one column per official economic concept
```

Advantages:

- easier analytical queries
- explicit economic meaning
- simpler frontend consumption
- straightforward validation against official publications

---

# Database Layer

All new ETLs should use:

```text
etl/utils/db_manager.py
```

rather than:

- direct subprocess-based Dolt operations
- duplicated PyMySQL connection logic
- separate database helper modules

Typical flow:

```python
db = DoltDBManager()

try:
    db.connect()

    # insert / update data

    db.dolt_add(TABLE_NAME)
    db.dolt_commit(message)

finally:
    db.disconnect()
```

---

# Frontend Architecture

The frontend lives in:

```text
frontend/
```

Stack:

- React
- Vite
- React Router
- Plotly
- JavaScript / JSX

There is no application backend between the browser and DoltHub.

The browser queries DoltHub directly through:

```text
frontend/src/api/dolt.js
```

Flow:

```text
React Page
    ↓
fetchDolt(SQL)
    ↓
DoltHub SQL API
    ↓
rbasa/macroeconomia
```

---

# Frontend Structure

```text
frontend/
├── public/
├── src/
│   ├── api/
│   │   └── dolt.js
│   │
│   ├── components/
│   │   ├── ChartCard.jsx
│   │   ├── Footer.jsx
│   │   ├── Layout.jsx
│   │   ├── Navbar.jsx
│   │   ├── PlotlyChart.jsx
│   │   ├── StatCard.jsx
│   │   └── VariationChart.jsx
│   │
│   ├── pages/
│   │   ├── HomePage.jsx
│   │   ├── Inflation.jsx
│   │   ├── EconomicActivity.jsx
│   │   ├── TradeBalance.jsx
│   │   ├── FiscalBalance.jsx
│   │   ├── UvaAnalysis.jsx
│   │   └── Expectations.jsx
│   │
│   ├── utils/
│   │   ├── charts.js
│   │   ├── formatters.js
│   │   └── series.js
│   │
│   ├── App.jsx
│   └── main.jsx
│
├── package.json
└── vite.config.js
```

---

# Frontend Separation of Responsibilities

## Pages

Pages define:

```text
what economic analysis is shown
```

Examples:

```text
Inflation.jsx
FiscalBalance.jsx
Expectations.jsx
```

Pages should avoid implementing generic calculations or chart-building logic.

---

## Components

Reusable presentation logic.

Examples:

```text
StatCard
ChartCard
PlotlyChart
VariationChart
Navbar
Layout
Footer
```

---

## `utils/series.js`

Reusable economic-series calculations.

Examples:

- numeric normalization
- percentage variations
- point changes
- annual variations
- monthly variations

---

## `utils/formatters.js`

Presentation formatting.

Examples:

- percentages
- index values
- point changes
- dates
- numbers
- currencies

---

## `utils/charts.js`

Reusable Plotly trace construction.

Examples:

- line traces
- bar traces
- pie traces

This avoids hardcoding Plotly configuration repeatedly inside every page.

---

# Plotly Architecture

`PlotlyChart.jsx` owns the common visual defaults:

- responsive sizing
- standard margins
- background
- legend placement
- Plotly lifecycle
- resize behavior

Individual pages should only override chart-specific properties.

Example:

```jsx
<PlotlyChart
  data={traces}
  layout={{
    yaxis: {
      title: 'Index',
    },
  }}
/>
```

---

# Local Frontend Development

From the repository root:

```bash
cd frontend
npm install
npm run dev
```

Vite provides the local development server.

Production builds use:

```bash
npm run build
```

Output:

```text
frontend/dist/
```

`dist/` and `node_modules/` are not committed.

---

# GitHub Pages Deployment

The production frontend is deployed by:

```text
.github/workflows/publish_pages.yml
```

It runs when:

```text
frontend/** changes
publish_pages.yml changes
manual workflow_dispatch
```

Flow:

```text
checkout
    ↓
npm ci
    ↓
npm run build
    ↓
frontend/dist
    ↓
GitHub Pages artifact
    ↓
deploy-pages
```

A data update does not require a frontend deployment because the browser reads
current data from DoltHub at runtime.

---

# Daily ETL Automation

The data workflow is:

```text
.github/workflows/daily_etl.yml
```

Scheduled execution:

```text
02:00 UTC daily
```

It can also be triggered manually.

High-level flow:

```text
Checkout macrolytics
        ↓
Install Python dependencies
        ↓
Install Dolt
        ↓
Configure DoltHub credentials
        ↓
Clone rbasa/macroeconomia
        ↓
Start local Dolt SQL server
        ↓
Run ETLs
        ↓
Each ETL creates its Dolt commit
        ↓
dolt push origin main
```

The workflow currently runs:

```text
daily_update.py
populate_ipc_arg.py
populate_emae_arg.py
populate_trade_arg.py
populate_fiscal_arg.py
```

Additional ETLs should be added to this pipeline once validated.

---

# Connection Strategy

## Local Development

Prefer Unix socket when available:

```python
pymysql.connect(
    unix_socket='/tmp/mysql.sock',
    ...
)
```

## GitHub Actions

Use TCP:

```text
localhost:3306
```

The `DOLT_DB` environment variable determines the runtime connection.

---

# Data Versioning

Dolt is not treated only as a SQL database.

Every ETL update creates a database commit.

This allows:

- historical inspection
- reproducibility
- diffing economic-data revisions
- rollback
- transparent dataset evolution

Git version-controls the application.

Dolt version-controls the data.

---

# Code Quality Principles

## Language

Code should use English for:

- function names
- variable names
- comments
- docstrings
- error messages
- technical documentation

Economic labels shown to users may be Spanish.

---

## Reuse

Before adding a helper function, check whether it belongs in:

```text
etl/utils/
frontend/src/utils/
frontend/src/components/
```

Do not create abstractions purely to reduce line count.

Abstract logic when it is genuinely reusable.

---

## Economic Correctness

For economic data:

```text
correctness > convenience
```

Rules:

1. Prefer primary or official sources.
2. Use fixed identifiers when available.
3. Do not silently substitute similar series.
4. Preserve missing observations as NULL.
5. Do not infer accounting identities when the official value is available.
6. Keep nominal and real values clearly distinguished.
7. Preserve source units and methodology.

---

# Known Technical Debt / Backlog

## Fiscal Data

- Complete migration from fuzzy series resolution to deterministic AIF Excel
  extraction + fixed IMIG tax IDs.
- Validate each fiscal row against the official monthly balance sheet.
- Build constant-price fiscal equivalents using CPI or another explicitly
  documented deflator.

## FX / UVA

`daily_update.py` should use `UPDATE_DAYS` consistently rather than rely on
temporary hardcoded date ranges.

## CER

Migrate `populate_cer_historical.py` away from subprocess-based Dolt operations
and into `DoltDBManager`.

## Expectations

Potential additions:

- Government Confidence Index
- business confidence
- inflation expectations

## Source Freshness

External APIs do not always update immediately after the primary statistical
agency publishes a release.

ETLs should distinguish between:

```text
source publication date
API availability date
database update date
```

## Frontend

- Continue removing legacy static HTML under `docs/` once every page has been
  migrated to React.
- Continue consolidating reusable series calculations, formatting, and chart
  behavior.

## Validation

Add automated checks for:

- latest expected period
- unexpected NULLs
- duplicate periods
- extreme revisions
- series ID mismatches
- accounting consistency checks

Validation may calculate identities for quality control, but those checks
should not overwrite the published source values.

---

# Deployment Architecture

There are two independent pipelines.

## Data Pipeline

```text
daily_etl.yml
    ↓
external sources
    ↓
ETLs
    ↓
local Dolt
    ↓
Dolt commits
    ↓
DoltHub
```

## Application Pipeline

```text
frontend change
    ↓
publish_pages.yml
    ↓
Vite build
    ↓
GitHub Pages
```

This separation means:

```text
new data
≠
new frontend deployment
```

and:

```text
frontend deployment
≠
database update
```

---

# Current Technical Stack

## Data / ETL

- Python 3.12+
- Pandas
- Requests
- PyMySQL
- OpenPyXL / xlrd
- Dolt

## Frontend

- React
- Vite
- React Router
- Plotly
- JavaScript / JSX

## Infrastructure

- GitHub
- GitHub Actions
- GitHub Pages
- DoltHub
- Dolt SQL Server

---

# Status

**Last Updated:** 2026-08-14  
**Architecture Version:** 2.0  
**Status:** Active Development