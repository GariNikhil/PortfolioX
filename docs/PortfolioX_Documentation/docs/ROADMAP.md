# PortfolioX — Roadmap

Priorities should be re-evaluated after inspecting the existing code and tests.

## Phase 0 — Repository alignment
- [ ] Inspect repository, stack, entry points, current database, and tests.
- [ ] Compare existing implementation with docs.
- [ ] Record current capabilities and gaps.
- [ ] Decide which docs are authoritative and update them.

## Phase 1 — Reliable core ledger
- [ ] Security master
- [ ] Transaction ledger and validation
- [ ] Holdings/quantity calculation
- [ ] Cost basis and charge treatment documented
- [ ] Realized and unrealized P&L
- [ ] Unit tests and known-value fixtures
- [ ] Local persistence and migrations

## Phase 2 — Usable portfolio workflow
- [ ] Dashboard and holdings table
- [ ] CSV/XLSX import preview and duplicate detection
- [ ] CSV/JSON export
- [ ] Backup and restore
- [ ] Watchlist, thesis notes, user-defined targets/risk plans

## Phase 3 — Market data and reporting
- [ ] Market-data adapters with timestamps and source attribution
- [ ] Staleness and missing-data states
- [ ] Allocation and historical snapshots
- [ ] Dividends and corporate actions
- [ ] Monthly/annual reports

## Phase 4 — Performance and risk
- [ ] XIRR and CAGR
- [ ] Benchmark comparison
- [ ] Concentration and drawdown
- [ ] Tax/capital-gains reporting with configurable rules
- [ ] MTF accounting, if required

## Phase 5 — Optional AI and additional clients
- [ ] Read-only structured portfolio query tools
- [ ] AI explanations with provenance
- [ ] Privacy controls for local/remote model use
- [ ] Additional broker adapters
- [ ] Mobile or remote access after a separate security review

## Definition of done
A feature is done only when requirements, data model, tests, edge cases, error states, security impact, and documentation are reviewed. Financial values must be reproducible against known fixtures.
