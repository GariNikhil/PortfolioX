# PortfolioX — Product Requirements Document (PRD)

- Status: Baseline draft
- Product: PortfolioX
- Initial market: India
- Primary currency: INR
- Primary instruments: listed equities on NSE/BSE
- Audience: individual investor managing personal investments

## 1. Vision
Provide a reliable, transparent, local-first workspace to record investments, calculate holdings and performance, understand risk and allocation, and maintain a documented investment process.

## 2. Goals
- Maintain a canonical transaction ledger.
- Calculate positions, cost basis, market value, realized/unrealized P&L, and portfolio allocation.
- Import and export portfolio records.
- Track watchlists, investment theses, targets, and user-defined risk plans.
- Track dividends and corporate actions.
- Provide dated, source-labelled market data.
- Provide performance analytics such as XIRR, CAGR, and benchmark comparison when sufficient data exists.
- Offer optional AI explanations grounded in verified records.
- Keep user data portable and protected.

## 3. Non-goals
- No automatic trade execution in the MVP.
- No guaranteed price predictions or profit claims.
- No silent rewriting of historical transactions.
- No unverified real-time market-data claims.
- No assumption that tax reports replace professional tax advice.
- No mandatory cloud account or remote AI inference requirement.

## 4. Personas and key jobs
**Individual investor:** wants a correct view of holdings, invested capital, current value, gains/losses, and exposure.
**Research-oriented investor:** wants watchlists, thesis notes, target/risk levels, and review reminders.
**Data-conscious user:** wants local control, transparent imports, reliable backup, and export.

## 5. Functional requirements

### P0 — MVP
- Security master with symbol, company name, exchange, ISIN, instrument type, sector/industry when known.
- Transaction ledger: buy, sell, deposit, withdrawal, fees/taxes, dividend, and supported corporate-action events.
- Holdings derived from transactions rather than independently edited totals.
- Configured cost-basis method, explicitly documented and tested.
- Current and historical price records with source and timestamp.
- Dashboard: invested/cost basis, market value, realized P&L, unrealized P&L, total P&L, return, and holding count.
- CSV/XLSX import with validation, mapping, duplicate detection, preview, and confirmation.
- CSV/JSON export; complete backup and restore.
- Watchlist and user-defined targets/stop-loss fields.
- Basic allocation and performance charts.
- Local persistence and useful error messages.

### P1 — Analytics
- Dividends and dividend reports.
- Corporate actions: split, bonus, rights, merger/demerger where supported.
- XIRR for dated cash flows and CAGR where appropriate.
- Benchmark comparison with source/timestamp checks.
- Concentration, volatility, drawdown, and other risk metrics when reliable history is available.
- Monthly/annual reports and portfolio snapshots.
- Tax-lot/capital-gains reporting aligned with configurable, current rules.

### P2 — Advanced
- Optional AI analysis layer.
- Additional broker adapters and import templates.
- MTF tracking isolated from ordinary cash positions, including financing costs.
- Optional mobile UI or companion client.

## 6. Core business rules
- Transactions are the source of truth; positions are derived.
- Never combine realized and unrealized P&L without clearly labelling the components.
- Store charges separately: brokerage, STT, exchange charges, GST, SEBI charges, stamp duty, DP charges, and other applicable charges.
- A market price must include timestamp, source, currency, and data status.
- Corporate actions are first-class events, not ordinary buy/sell transactions.
- Imported records must be normalized and validated before database commit.
- Duplicate imports must be detected using stable identifiers and conservative matching.
- Financial amounts use decimal-safe arithmetic; do not use binary floating point for money calculations.
- AI-generated numerical statements must cite or expose the underlying portfolio records/data source.

## 7. Quality attributes
- Correctness: deterministic calculations and regression tests.
- Auditability: important changes and imports are traceable.
- Privacy: avoid unnecessary data transmission.
- Portability: documented export and restore.
- Resilience: safe failure on malformed files or missing/stale prices.
- Usability: distinguish verified data, stale data, estimates, and missing data.
- Maintainability: separate UI, domain logic, persistence, and external adapters.

## 8. MVP acceptance criteria
- Given a known transaction fixture, holdings and cost basis match hand-verified expected results.
- Realized and unrealized P&L appear separately and reconcile to the defined accounting rules.
- Import preview reports invalid rows and suspected duplicates without changing stored data.
- Confirmed import can be audited and safely rolled back or corrected.
- Missing/stale market prices are visibly marked; no false “live” status.
- Export followed by restore preserves supported records and relationships.
- XIRR handles irregular cash flows, invalid inputs, and non-convergence with explicit error states.
- Critical calculation paths have unit tests and regression fixtures.

## 9. Success measures
- Reconciliation accuracy against broker statements.
- Import success rate and clear handling of rejected rows.
- Zero silent transaction loss or duplicate insertion in tested import flows.
- Backup/restore validation passes.
- Financial calculation regression suite passes on every relevant change.

## 10. Open decisions
- Actual application stack and runtime.
- Database engine and migration framework.
- Cost-basis method(s) and treatment of charges.
- Approved market-data providers and their terms.
- Authentication/encryption approach for the chosen platform.
- Whether mutual funds, bonds, ETFs, and other asset classes are in the first release.
