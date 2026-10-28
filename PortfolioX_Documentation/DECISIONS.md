# PortfolioX — Architecture Decision Log

Record decisions here. Do not silently treat a proposal as an approved implementation choice.

## ADR-001: Transaction ledger is canonical
- Status: Accepted baseline principle
- Decision: Holdings and portfolio summaries are derived from transaction events and supported corporate actions.
- Reason: Enables reconciliation, auditability, and reproducible calculations.

## ADR-002: Separate market data from domain logic
- Status: Accepted baseline principle
- Decision: Provider integrations use adapters and normalized price observations.
- Reason: Provider failures/schema changes must not corrupt portfolio accounting.

## ADR-003: No autonomous trading in MVP
- Status: Accepted baseline principle
- Decision: Alerts and analysis inform the user; they do not submit orders.
- Reason: Reduces operational and financial risk.

## ADR-004: Local-first data handling
- Status: Proposed baseline; verify against current code
- Decision: Keep portfolio data local by default where the platform allows; remote data/AI flows must be explicit and documented.
- Reason: Financial data is sensitive.

## Pending decisions
- Actual language/framework/runtime and supported platforms.
- Database engine and migration strategy.
- Cost-basis method and accounting treatment for charges.
- Market-data provider(s), licensing, and refresh limits.
- Authentication and encryption approach.
- Initial asset-class scope beyond NSE/BSE equities.
- Whether source import files are retained and for how long.
