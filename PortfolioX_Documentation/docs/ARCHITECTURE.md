# PortfolioX — System Architecture

- Status: Baseline logical architecture
- Implementation status: Must be reconciled with the current repository before coding

## 1. Architectural goals
- Deterministic financial domain logic.
- Clear separation between data providers and portfolio calculations.
- Local-first data control.
- Testable interfaces and replaceable adapters.
- Traceable values and reproducible reports.

## 2. Logical component diagram

```text
                UI / CLI / Optional Mobile Client
                            |
                     Application Services
                            |
        +-------------------+-------------------+
        |                   |                   |
 Transaction Service   Import/Export       Reporting Service
        |                   |                   |
        +-------------------+-------------------+
                            |
                     Domain / Portfolio Engine
           +----------------+----------------+
           |                |                |
      Holdings & P&L   Performance/Risk   Corporate Actions
           |                |                |
           +----------------+----------------+
                            |
                     Repository Interfaces
                            |
                      Local Database
                            |
              +-------------+--------------+
              |                            |
        Market Data Adapters          Backup/Export
              |
      External Provider APIs / Files

Optional AI:
Verified portfolio query -> analytics/context builder -> model adapter
-> explanation with source references; never direct database mutation.
```

## 3. Component responsibilities
- **UI:** display data and collect user intent; no duplicated financial formulas.
- **Application services:** coordinate workflows, validation, transactions, imports, and reports.
- **Domain engine:** pure or tightly controlled calculations for positions, cost basis, P&L, returns, risk.
- **Repository layer:** persistence, migrations, and query access.
- **Market-data adapters:** provider-specific integration, normalization, timestamps, source and failure states.
- **Import/export:** parsing, mapping, validation, duplicate detection, preview, commit, and portable export.
- **AI adapter:** receives only the minimum structured context needed; cannot invent facts or silently change records.
- **Audit/logging:** records important operations without leaking secrets or unnecessary financial details.

## 4. Data flow
### Transaction write
User input/import -> schema validation -> security resolution -> duplicate check -> preview -> explicit confirmation -> atomic transaction -> recompute derived positions -> audit event.

### Price update
Provider -> adapter -> normalized quote with source/timestamp/currency -> freshness validation -> price repository/cache -> valuation calculation -> UI with freshness indicator.

### Portfolio question to AI
User question -> structured query against verified records -> calculation engine -> compact result with provenance -> model explanation -> response that distinguishes facts, assumptions, and missing data.

## 5. Data ownership and source of truth
- Transaction ledger is canonical for user-entered trade history.
- Corporate actions and dividends are recorded as explicit events.
- Positions and summary metrics are derived views, not independent editable truths.
- Quotes are observations with source and time; they are not permanent attributes of a security.
- Imported source files may be retained in a protected import archive according to user settings.

## 6. Persistence
Use a relational database or equivalent transactional store. The specific engine must match the current repository and deployment requirements. Required capabilities:
- Atomic transactions
- Unique constraints/indexes for stable identifiers
- Schema migrations
- Backup and restore
- Foreign-key or equivalent relationship integrity
- Decimal-safe storage for money and quantities

Do not adopt a new database or framework until the current project stack has been inspected.

## 7. Financial calculation design
- Use decimal-safe arithmetic for money.
- Keep calculation functions isolated and unit-testable.
- Define cost-basis policy explicitly.
- Track fees/taxes separately and define their accounting treatment.
- Handle splits, bonuses, rights, mergers, and other supported events explicitly.
- Return calculation status/errors instead of silently substituting zero.
- Use XIRR only with valid dated cash flows; handle non-convergence.
- Record formula/version or calculation metadata when needed for reproducibility.

## 8. External integrations
Market data and broker imports must be adapter-based. Provider failures, rate limits, schema changes, stale data, and unavailable symbols must not corrupt portfolio records. Follow provider terms and licensing; do not assume scraping is permitted.

## 9. Error handling and observability
- Validate at boundaries.
- Use stable error categories and actionable messages.
- Log technical failures without secrets.
- Include operation/import IDs for troubleshooting.
- Keep user-facing status distinct from internal diagnostic details.

## 10. Deployment profiles
- **Local desktop:** local database, local backups, optional online market data.
- **Local web app:** bind to loopback by default; remote access requires explicit secure deployment.
- **Optional remote/mobile access:** separate threat review, authentication, TLS, authorization, rate limiting, and secure secret management required.

## 11. Architecture constraints for contributors
- UI components must not independently recalculate core financial metrics.
- Provider-specific types must not leak into domain entities.
- AI output must never be the source of truth.
- No order execution in the MVP.
- Avoid broad rewrites of financial logic without tests and a migration plan.
