# PortfolioX — Personal Investment Portfolio Resource

> Project goal: Build a professional, local-first portfolio management and investment-analysis application for Indian equities, with a clean dashboard, transaction tracking, portfolio analytics, watchlists, risk controls, and import/export support.

---

# 01 — Project Vision

## PortfolioX

PortfolioX is a personal investment-management system designed around an Indian equity portfolio.

### Primary goals

- Track holdings
- Track buy/sell transactions
- Calculate invested capital
- Calculate current market value
- Calculate realized P&L
- Calculate unrealized P&L
- Calculate overall return
- Track average buy price
- Track quantity
- Track portfolio allocation
- Track sector allocation
- Track watchlists
- Track targets and stop-loss levels
- Track dividends
- Support Indian-market data
- Import broker statements
- Export complete portfolio data
- Provide a professional investor dashboard
- Keep the user's portfolio data under their control

### Core principle

```text
TRANSACTIONS
     ↓
PORTFOLIO ENGINE
     ↓
HOLDINGS
     ↓
MARKET DATA
     ↓
ANALYTICS ENGINE
     ↓
DASHBOARD
     ↓
DECISION SUPPORT
```

PortfolioX should be an **analysis and record-keeping system**, not an autonomous trading system.

---

# 02 — Product Requirements

## Portfolio Tracking

Each holding should support:

- Stock symbol
- Company name
- Exchange
- ISIN
- Quantity
- Average buy price
- Invested amount
- Current price
- Current market value
- Unrealized P&L
- Unrealized P&L %
- Realized P&L
- Total P&L
- Portfolio weight
- Sector
- Industry
- Buy date
- Holding period
- Dividend income

### Holding example

```yaml
holding:
  symbol: "PNB"
  exchange: "NSE"
  quantity: 8
  average_buy_price: 93.00
  invested_amount: 744.00
  current_price: 0
  market_value: 0
  unrealized_pnl: 0
  unrealized_pnl_percent: 0
  sector: "Financials"
```

Market values must always be calculated from current or explicitly selected historical prices rather than hard-coded.

---

# 03 — Transaction Ledger

The transaction ledger is the source of truth.

## Transaction types

- BUY
- SELL
- DIVIDEND
- BONUS
- SPLIT
- RIGHTS
- IPO
- CORPORATE ACTION
- DEPOSIT
- WITHDRAWAL
- FEES
- TAX
- OTHER

### Transaction model

```yaml
transaction:
  id: "unique-id"
  date: "YYYY-MM-DD"
  symbol: "NSE_SYMBOL"
  type: "BUY"
  quantity: 0
  price: 0
  brokerage: 0
  taxes: 0
  other_charges: 0
  total_value: 0
  notes: ""
```

### Important rule

Never manually overwrite historical transactions to make the portfolio balance.

Correct the transaction ledger instead.

---

# 04 — Portfolio Engine

The portfolio engine converts transactions into current holdings.

```text
TRANSACTION LEDGER
        ↓
BUY / SELL PROCESSOR
        ↓
POSITION CALCULATOR
        ↓
CURRENT HOLDINGS
        ↓
P&L ENGINE
```

## Required calculations

### Quantity

```text
Net Quantity =
Total Buy Quantity
− Total Sell Quantity
± Corporate Actions
```

### Invested capital

The exact accounting method should be configurable.

At minimum:

```text
Invested Capital =
Cost Basis of Current Holdings
```

### Market value

```text
Market Value =
Current Quantity × Current Market Price
```

### Unrealized P&L

```text
Unrealized P&L =
Market Value − Current Cost Basis
```

### Return

```text
Return % =
(Unrealized P&L ÷ Current Cost Basis) × 100
```

For more accurate portfolio-level performance, PortfolioX should additionally support time-weighted and money-weighted return calculations.

---

# 05 — P&L Engine

PortfolioX should distinguish clearly between:

## Unrealized P&L

Profit/loss on currently held securities.

```text
Current Market Value
− Current Cost Basis
```

## Realized P&L

Profit/loss from completed sales.

```text
Net Sale Proceeds
− Corresponding Cost Basis
```

## Total P&L

```text
Total P&L =
Realized P&L
+
Unrealized P&L
+
Dividends
− Relevant Costs
```

The UI must never mix realized and unrealized P&L without labeling them.

---

# 06 — Indian Market Support

PortfolioX is designed primarily for Indian equities.

## Exchanges

- NSE
- BSE

## Indian-market fields

- Symbol
- ISIN
- Exchange
- Quantity
- Average price
- Market price
- Brokerage
- STT
- Exchange transaction charges
- GST
- SEBI charges
- Stamp duty
- DP charges
- Other applicable charges

Charges should be stored separately rather than hidden inside a single number.

## Currency

Default:

```text
INR (₹)
```

The architecture should nevertheless allow additional currencies in the future.

---

# 07 — Broker Import

PortfolioX should support importing broker data rather than requiring manual entry.

## Import sources

The initial design should support:

- CSV
- XLSX
- Broker holding statements
- Transaction statements
- Contract notes where practical

### Import flow

```text
BROKER FILE
     ↓
FILE VALIDATION
     ↓
COLUMN MAPPING
     ↓
DATA NORMALIZATION
     ↓
DUPLICATE CHECK
     ↓
TRANSACTION VALIDATION
     ↓
IMPORT PREVIEW
     ↓
CONFIRM
     ↓
PORTFOLIO DATABASE
```

Never directly insert an unvalidated broker file into the database.

---

# 08 — Data Normalization

Different brokers may use different names.

Example:

```text
PNB
Punjab National Bank
NSE:PNB
INE160A01022
```

PortfolioX should maintain a security master.

```text
SECURITY MASTER
├── Symbol
├── Company Name
├── ISIN
├── Exchange
├── Sector
├── Industry
└── Instrument Type
```

ISIN should be preferred as the strongest identity key when available.

---

# 09 — Market Data Layer

Market data should be isolated from the portfolio engine.

```text
MARKET DATA PROVIDER
        ↓
DATA ADAPTER
        ↓
NORMALIZED PRICE DATA
        ↓
PORTFOLIO ENGINE
        ↓
DASHBOARD
```

## Price data

Support:

- Current price
- Previous close
- Open
- High
- Low
- Volume
- Historical OHLC
- Corporate actions where available

## Design rule

The application must never assume that a market price is current unless its timestamp/source says so.

---

# 10 — Dashboard

PortfolioX should provide a professional investor dashboard.

## Main dashboard

```text
┌───────────────────────────────────────────┐
│              PORTFOLIO X                  │
├───────────────────────────────────────────┤
│ Invested │ Market Value │ P&L │ Return % │
├───────────────────────────────────────────┤
│                                           │
│         PORTFOLIO PERFORMANCE             │
│              CHART                        │
│                                           │
├───────────────────────┬───────────────────┤
│ Allocation             │ Top Holdings      │
│ Chart                  │                   │
├───────────────────────┼───────────────────┤
│ Sector Allocation      │ Watchlist         │
├───────────────────────┴───────────────────┤
│ Recent Transactions                       │
└───────────────────────────────────────────┘
```

---

# 11 — Dashboard Metrics

## Portfolio-level

- Total invested
- Current value
- Realized P&L
- Unrealized P&L
- Total P&L
- Return %
- Day change
- Day change %
- Number of holdings
- Cash balance
- Dividend income
- Portfolio concentration

## Holding-level

- Quantity
- Average price
- Current price
- Cost basis
- Market value
- P&L
- P&L %
- Weight
- Holding period

---

# 12 — Portfolio Allocation

PortfolioX should show allocation by:

- Stock
- Sector
- Industry
- Exchange
- Asset type

### Allocation formula

```text
Holding Weight % =
Holding Market Value
÷
Total Portfolio Market Value
× 100
```

### Visualization

```text
PORTFOLIO
│
├── Stock Allocation
├── Sector Allocation
├── Industry Allocation
└── Asset Allocation
```

The user should be able to drill down:

```text
Sector
  ↓
Industry
  ↓
Company
  ↓
Holding
```

---

# 13 — Risk Dashboard

PortfolioX should provide risk visibility without pretending to predict the market.

## Risk metrics

- Concentration
- Largest holding %
- Sector concentration
- Number of holdings
- Volatility
- Drawdown
- Beta where reliable data is available
- Correlation
- Portfolio turnover
- Cash allocation

### Concentration warning

```text
IF holding_weight > configured_limit
THEN
    show "High concentration"
```

Limits must be user-configurable.

---

# 14 — Target & Stop-Loss System

PortfolioX should allow the user to record trading levels.

## Per-position fields

```yaml
risk_plan:
  entry_price: 0
  stop_loss: 0
  target_1: 0
  target_2: 0
  target_3: 0
  thesis: ""
  invalidation_condition: ""
```

### Example

```text
Entry
  ↓
Stop Loss
  ↓
Target 1
  ↓
Target 2
  ↓
Target 3
```

These values are **user-defined plans**.

PortfolioX should not automatically place trades unless a separate, explicitly authorized execution module is later implemented.

---

# 15 — Watchlist

## Watchlist fields

- Symbol
- Company
- Current price
- Change %
- Desired entry
- Target
- Stop-loss
- Thesis
- Reason for watching
- Sector
- Notes
- Priority

### Watchlist workflow

```text
DISCOVER
   ↓
RESEARCH
   ↓
WATCH
   ↓
DEFINE THESIS
   ↓
DEFINE ENTRY
   ↓
REVIEW
   ↓
BUY / IGNORE
```

---

# 16 — Investment Thesis

Every serious position can have a written thesis.

```yaml
thesis:
  symbol: "SYMBOL"
  reason_to_buy: ""
  expected_catalysts: []
  risks: []
  invalidation: ""
  review_date: ""
  notes: ""
```

### Principle

> A stock should have a reason for being in the portfolio.

PortfolioX should make the reasoning visible rather than reducing investing to price movement alone.

---

# 17 — Dividend Tracker

Track dividend income separately.

```text
DIVIDEND
├── Security
├── Ex-Date
├── Record Date
├── Payment Date
├── Dividend / Share
├── Quantity
├── Gross Dividend
├── Tax / Deduction
└── Net Dividend
```

### Dividend metrics

- Total dividends
- Annual dividends
- Dividend yield on cost
- Dividend yield on current value
- Dividend by stock
- Dividend by year

---

# 18 — Corporate Actions

Support corporate actions as first-class events.

Examples:

- Stock split
- Bonus issue
- Rights issue
- Merger
- Demerger
- Buyback
- Dividend

```text
CORPORATE ACTION
       ↓
POSITION ADJUSTMENT
       ↓
COST BASIS ADJUSTMENT
       ↓
HISTORICAL DATA CONSISTENCY
```

Corporate actions must not be treated as ordinary buy/sell transactions.

---

# 19 — Portfolio Performance

PortfolioX should support several performance views.

## Absolute return

```text
Absolute Return =
(Current Value − Invested Capital)
÷ Invested Capital
× 100
```

## CAGR

For long-term holdings:

```text
CAGR =
(Ending Value / Beginning Value)^(1 / Years) − 1
```

## XIRR

For irregular cash flows, use XIRR.

```text
Cash Flows
    ↓
Date-aware return calculation
    ↓
XIRR
```

## Time-weighted return

Useful when comparing portfolio management performance while reducing the effect of external cash flows.

---

# 20 — Benchmark Comparison

PortfolioX should optionally compare portfolio performance against benchmarks.

Potential benchmark architecture:

```text
PORTFOLIO
    │
    ├── NIFTY 50
    ├── SENSEX
    └── Custom Benchmark
```

### Comparison metrics

- Return
- CAGR
- Volatility
- Drawdown
- Relative performance

Benchmark data must be timestamped and sourced.

---

# 21 — Tax & Capital Gains

PortfolioX should maintain transaction-level information needed for tax analysis.

## Track

- Purchase date
- Sale date
- Purchase cost
- Sale proceeds
- Holding period
- Realized gain/loss
- Charges
- Corporate actions

## Reports

```text
CAPITAL GAINS
├── Realized Gains
├── Realized Losses
├── Short-term
├── Long-term
└── Transaction Detail
```

Tax calculations should be configurable for the applicable Indian tax rules and should be treated as reporting assistance, not professional tax advice.

---

# 22 — MTF Support

If margin trading facilities are tracked, they must be separated from ordinary cash holdings.

## MTF fields

```yaml
mtf:
  enabled: false
  quantity: 0
  funded_amount: 0
  own_capital: 0
  interest_rate: 0
  interest_accrued: 0
  collateral_value: 0
  margin_requirement: 0
```

### MTF architecture

```text
POSITION
   │
   ├── OWN CAPITAL
   │
   └── BROKER FUNDED
          ↓
      MTF COST
          ↓
       NET P&L
```

MTF interest and financing costs must not be silently ignored.

---

# 23 — Alerts

PortfolioX can provide local alerts.

## Examples

- Price reaches target
- Price reaches stop-loss
- Holding exceeds allocation limit
- Large daily movement
- Dividend announced
- Corporate action detected
- Thesis review date reached
- Watchlist entry condition reached

### Alert architecture

```text
MARKET DATA
     ↓
RULE ENGINE
     ↓
ALERT
     ↓
USER
```

Alerts should not automatically execute trades.

---

# 24 — AI Analysis Layer

PortfolioX may include an AI assistant, but the AI should operate on verified portfolio data.

## AI capabilities

- Explain portfolio allocation
- Summarize transactions
- Identify concentration
- Summarize a stock thesis
- Compare historical performance
- Generate portfolio reports
- Explain P&L changes
- Help organize research notes

## AI architecture

```text
PORTFOLIO DATABASE
       ↓
ANALYTICS ENGINE
       ↓
STRUCTURED DATA
       ↓
AI CONTEXT BUILDER
       ↓
LOCAL / REMOTE LLM
       ↓
EXPLANATION
```

### Critical rule

The AI must not invent prices, holdings, transactions, or financial data.

Every numerical answer should be traceable to portfolio data or a clearly identified market-data source.

---

# 25 — Data Architecture

Recommended high-level data model:

```text
User
 │
 ├── Accounts
 │
 ├── Securities
 │
 ├── Transactions
 │
 ├── Holdings
 │
 ├── Dividends
 │
 ├── Corporate Actions
 │
 ├── Watchlists
 │
 ├── Investment Theses
 │
 ├── Alerts
 │
 └── Portfolio Snapshots
```

## Core entities

```text
Security
Account
Transaction
Position
Price
Dividend
CorporateAction
PortfolioSnapshot
WatchlistItem
Thesis
RiskPlan
Alert
Benchmark
ResearchNote
```

---

# 26 — Recommended Project Structure

```text
portfoliox/
├── .vscode/
│   ├── settings.json
│   └── tasks.json
│
├── docs/
│   ├── architecture.md
│   ├── product-requirements.md
│   ├── portfolio-engine.md
│   ├── market-data.md
│   ├── risk-management.md
│   ├── tax-reporting.md
│   └── roadmap.md
│
├── specifications/
│   ├── holdings.md
│   ├── transactions.md
│   ├── pnl.md
│   ├── dividends.md
│   ├── corporate-actions.md
│   ├── watchlist.md
│   ├── alerts.md
│   └── ai-analysis.md
│
├── data/
│   ├── imports/
│   ├── exports/
│   ├── backups/
│   └── cache/
│
├── memory/
│   ├── project-memory.md
│   └── decisions.md
│
├── tasks/
│   ├── backlog.md
│   ├── active.md
│   └── completed.md
│
├── workflow/
│   ├── development.md
│   ├── data-import.md
│   ├── testing.md
│   └── release.md
│
├── standards/
│   ├── coding.md
│   ├── financial-data.md
│   ├── security.md
│   └── ui.md
│
├── templates/
│   ├── transaction.yaml
│   ├── security.yaml
│   ├── thesis.yaml
│   └── risk-plan.yaml
│
├── scripts/
│
├── app/
├── backend/
├── engine/
│   ├── portfolio/
│   ├── pnl/
│   ├── performance/
│   ├── risk/
│   ├── tax/
│   └── analytics/
│
├── market_data/
│   ├── adapters/
│   ├── normalization/
│   └── cache/
│
├── tests/
│
├── README.md
├── CLAUDE.md
└── ROADMAP.md
```

---

# 27 — Context Engineering for PortfolioX

AI coding agents should receive project context before modifying financial logic.

## Required context

```text
README.md
    ↓
CLAUDE.md
    ↓
Architecture
    ↓
Relevant Specification
    ↓
Financial Calculation Rules
    ↓
Current Task
    ↓
Existing Code
    ↓
Tests
```

## AI coding rules

Before changing portfolio calculations:

1. Read the relevant specification.
2. Identify the accounting method being used.
3. Inspect existing transaction models.
4. Check corporate-action handling.
5. Check existing tests.
6. Make the smallest safe change.
7. Run calculations against known examples.
8. Update documentation.

---

# 28 — Data Integrity Rules

PortfolioX handles financial records, so data integrity is critical.

## Rules

### Rule 1

Transactions are immutable by default.

### Rule 2

Corrections should create an auditable correction rather than silently rewriting history.

### Rule 3

Every imported transaction should have a source reference.

### Rule 4

Duplicate imports must be detected.

### Rule 5

Currency must always be explicit.

### Rule 6

Prices must have timestamps.

### Rule 7

Market-data sources must be identifiable.

### Rule 8

Calculated values should be reproducible.

### Rule 9

Realized and unrealized P&L must remain separate.

### Rule 10

Portfolio backups must be exportable.

---

# 29 — Security & Privacy

Portfolio information is financially sensitive.

## Requirements

- Local database protection
- Secure backup handling
- No unnecessary transmission of holdings
- API keys stored securely
- No credentials inside source code
- Import files handled safely
- Audit logs for important changes
- Optional encryption at rest

### Security principle

```text
USER DATA
   ↓
LOCAL STORAGE
   ↓
ENCRYPTION / ACCESS CONTROL
   ↓
PORTFOLIOX
```

---

# 30 — Backup & Export

PortfolioX should make data portable.

## Export

```text
PORTFOLIOX
   ↓
EXPORT
   ├── Holdings
   ├── Transactions
   ├── Dividends
   ├── Corporate Actions
   ├── Watchlists
   ├── Theses
   └── Settings
```

Recommended formats:

- CSV
- XLSX
- JSON
- PDF reports

## Backup

```text
DATABASE
   ↓
VALIDATED BACKUP
   ↓
LOCAL BACKUP STORAGE
   ↓
SECONDARY BACKUP
```

---

# 31 — Reports

PortfolioX should generate professional reports.

## Monthly report

```text
PORTFOLIO REPORT
├── Starting Value
├── Contributions
├── Withdrawals
├── Ending Value
├── Realized P&L
├── Unrealized P&L
├── Dividends
├── Best Performer
├── Worst Performer
├── Allocation
└── Notes
```

## Annual report

Include:

- Annual return
- CAGR
- XIRR
- Realized gains/losses
- Dividends
- Portfolio allocation
- Benchmark comparison
- Drawdown
- Transaction summary

---

# 32 — Portfolio Snapshots

PortfolioX should preserve historical portfolio states.

```text
DATE
 ↓
PORTFOLIO SNAPSHOT
 ├── Total Value
 ├── Invested Capital
 ├── P&L
 ├── Holdings
 └── Allocation
```

This allows:

```text
TODAY
  ↕
1 MONTH AGO
  ↕
6 MONTHS AGO
  ↕
1 YEAR AGO
  ↕
ALL TIME
```

---

# 33 — Investment Journal

A journal can record decisions independently from transactions.

```yaml
journal_entry:
  date: "YYYY-MM-DD"
  symbol: "SYMBOL"
  action: "BUY / SELL / HOLD / REVIEW"
  reason: ""
  thesis: ""
  risks: []
  expected_outcome: ""
  review_date: ""
  result: ""
```

The journal helps distinguish:

```text
WHAT I DID
        vs
WHY I DID IT
        vs
WHAT HAPPENED
```

---

# 34 — Decision Support

PortfolioX should surface information, not make blind decisions.

## Example

```text
POSITION
   ↓
CURRENT DATA
   ↓
RISK METRICS
   ↓
THESIS
   ↓
USER-DEFINED TARGET / STOP
   ↓
DECISION SUPPORT
```

Possible outputs:

- Hold
- Review
- Reduce-risk consideration
- Research further
- Watch

These should be presented as analysis or user-configured rules, not guaranteed predictions.

---

# 35 — MVP

The first usable PortfolioX version should focus on:

- [ ] Security master
- [ ] Transaction ledger
- [ ] Holdings calculation
- [ ] Average price
- [ ] Cost basis
- [ ] Market value
- [ ] Realized P&L
- [ ] Unrealized P&L
- [ ] Portfolio dashboard
- [ ] CSV/XLSX import
- [ ] CSV/XLSX export
- [ ] Watchlist
- [ ] Target / stop-loss fields
- [ ] Basic portfolio charts
- [ ] Local database
- [ ] Backup

Then expand into:

- [ ] Market-data adapters
- [ ] Dividends
- [ ] Corporate actions
- [ ] XIRR
- [ ] CAGR
- [ ] Benchmark comparison
- [ ] Risk analytics
- [ ] Tax reports
- [ ] MTF tracking
- [ ] AI analysis
- [ ] Mobile application

---

# 36 — Definition of Done

A feature is complete only when:

- [ ] Specification exists
- [ ] Data model is documented
- [ ] Calculation logic is tested
- [ ] Edge cases are tested
- [ ] Import/export behavior is tested
- [ ] Financial values are reproducible
- [ ] Errors are handled
- [ ] Documentation is updated
- [ ] Existing portfolio calculations remain correct

---

# 37 — Master Architecture

```text
                         PORTFOLIOX
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
   TRANSACTIONS          SECURITIES          MARKET DATA
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ↓
                     PORTFOLIO ENGINE
                             │
              ┌──────────────┼──────────────┐
              ↓              ↓              ↓
             P&L          RISK         PERFORMANCE
              │              │              │
              └──────────────┼──────────────┘
                             ↓
                       ANALYTICS ENGINE
                             │
        ┌────────────────────┼────────────────────┐
        ↓                    ↓                    ↓
    DASHBOARD            REPORTS              AI LAYER
        │                    │                    │
        └────────────────────┼────────────────────┘
                             ↓
                          USER
```

---

# 38 — Project North Star

> **PortfolioX should turn raw broker transactions and market data into a clear, auditable picture of what the investor owns, how it is performing, what risks are concentrated, and why each position exists.**

The architecture should prioritize:

**Accurate → Auditable → Local-first → Transparent → Modular → Extensible**

---

# 39 — Initial Task Board

## Foundation

- [ ] Create repository
- [ ] Create project structure
- [ ] Define database schema
- [ ] Define security master
- [ ] Define transaction model
- [ ] Define calculation rules

## Portfolio Engine

- [ ] Implement BUY processing
- [ ] Implement SELL processing
- [ ] Implement cost basis
- [ ] Implement realized P&L
- [ ] Implement unrealized P&L
- [ ] Implement portfolio valuation

## Dashboard

- [ ] Portfolio summary
- [ ] Holdings table
- [ ] Allocation chart
- [ ] P&L chart
- [ ] Performance chart
- [ ] Transaction table

## Import / Export

- [ ] CSV import
- [ ] XLSX import
- [ ] Duplicate detection
- [ ] Import preview
- [ ] CSV export
- [ ] XLSX export
- [ ] JSON backup

## Advanced

- [ ] Dividends
- [ ] Corporate actions
- [ ] XIRR
- [ ] CAGR
- [ ] Risk metrics
- [ ] Benchmark comparison
- [ ] Tax reporting
- [ ] MTF
- [ ] AI analysis

---

# 40 — Final Engineering Principle

```text
             RAW DATA
                 ↓
          VALIDATE DATA
                 ↓
       NORMALIZE & STORE
                 ↓
        CALCULATE CORRECTLY
                 ↓
          VERIFY RESULTS
                 ↓
          SHOW CLEARLY
                 ↓
       SUPPORT THE DECISION
```

> **Never let a beautiful dashboard hide bad accounting.**

For PortfolioX, the transaction ledger and calculation engine are more important than visual polish. The dashboard is the window; the accounting engine is the foundation.
