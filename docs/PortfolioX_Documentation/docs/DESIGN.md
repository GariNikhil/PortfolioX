# PortfolioX — Product and UX Design

- Status: Baseline design specification
- Design priority: clarity, auditability, fast data entry, low ambiguity

## 1. Design principles
1. Financial correctness outranks visual decoration.
2. Label the metric, period, currency, source, and timestamp.
3. Show realized P&L and unrealized P&L separately.
4. Use colour as a secondary cue; never rely on colour alone.
5. Make stale, missing, estimated, and verified data visibly different.
6. Destructive or irreversible operations require explicit confirmation.
7. Provide drill-down from summary metric to the records behind it.

## 2. Primary navigation
- Dashboard
- Holdings
- Transactions
- Watchlist
- Analytics
- Dividends & Corporate Actions
- Reports
- Settings / Data Sources / Backup

Navigation may be adapted to the existing application, but these functional areas should remain discoverable.

## 3. Dashboard
### Summary cards
- Portfolio market value
- Cost basis / invested capital
- Unrealized P&L
- Realized P&L
- Dividends
- Day change (only when reliable current and previous-close data exist)

Each card should provide a definition/tooltip and data timestamp where relevant.

### Main panels
- Portfolio value/performance chart
- Asset/sector allocation
- Largest holdings and concentration
- Recent transactions
- Data freshness / import status
- Watchlist alerts

### Empty and error states
- No transactions: explain how to import or add a transaction.
- No price: show “Price unavailable”; do not substitute zero as if it were a real price.
- Stale price: show last update time and source.
- Import error: explain row number, field, issue, and possible correction.

## 4. Holdings table
Suggested columns:
- Security / symbol
- Exchange
- Quantity
- Average cost
- Cost basis
- Latest price
- Market value
- Unrealized P&L and %
- Realized P&L
- Portfolio weight
- Price timestamp/status

Allow sorting, filtering, and a detail view. Preserve precision internally; display precision should be consistent and configurable.

## 5. Security detail
Sections:
- Position summary
- Transaction history
- Price/performance history
- Dividends and corporate actions
- Investment thesis and notes
- User-defined targets and risk plan
- Data provenance

## 6. Transaction workflow
1. Choose manual entry or import.
2. Validate required fields and security identity.
3. Show calculated totals and charges.
4. Preview effects on quantity, cost basis, and P&L.
5. Confirm save.
6. Show a receipt/record ID and allow audit review.

Historical corrections should use a correction/reversal flow rather than silently overwriting the original event.

## 7. Import wizard
Stages:
1. Select file and import type.
2. Validate file format and size.
3. Map columns.
4. Normalize symbols/ISINs and dates.
5. Detect duplicates and suspicious rows.
6. Preview accepted/rejected rows and resulting position changes.
7. Require user confirmation.
8. Display import report and source-file fingerprint.

Do not execute macros or treat file contents as trusted instructions.

## 8. Analytics and reports
- Allocation by security, sector, industry, exchange, and supported asset type.
- Return view with method clearly named: absolute return, CAGR, XIRR, or time-weighted return.
- Benchmark comparison only when benchmark data coverage and dates are comparable.
- Reports include as-of date, currency, data sources, assumptions, and exclusions.

## 9. Accessibility and responsive behaviour
- Keyboard navigation and visible focus.
- Text labels for icons and chart summaries.
- Adequate contrast in light/dark themes.
- Tables should remain usable on smaller screens via responsive columns or detail views.
- Do not use red/green as the only way to indicate loss/gain.

## 10. Interaction safeguards
- Confirm bulk deletion, reset, restore-overwrite, and transaction correction.
- For import, never commit before preview/confirmation.
- For backup restore, show target, backup date, and whether existing data will be replaced.
- Alerts are informational and never submit orders.
