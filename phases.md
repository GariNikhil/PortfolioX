# PortfolioX - Development Roadmap
## Overview

PortfolioX is a local-first desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer.
- [x] Initialize Python project structure
- [x] Set up version control (.gitignore)
- [x] Create project README
- [x] Set up package structure (database/, calculations/, importers/, ui/)
- [x] Configure Python dependencies (requirements.txt / pyproject.toml)
## Phase 2: Database Layer ✅

**Goal**: Establish the local SQLite database with schema, connection management, and CRUD operations.

- [x] Define database schema (transactions, holdings, dividends, imports tables)
- [x] Implement connection management (create_connection, DB_PATH handling)
- [x] Ensure schema at startup with v1 -> paise migration (ensure_schema)
- [x] Exact money storage as INTEGER paise with NOT NULL / CHECK constraints
- [x] Side-aware net_amount (BUY debits, SELL credits)
- [x] add_transactions batch insert, delete_transaction, rebuild_holdings
## Phase 3: Groww Import System ✅

**Goal**: Build the import system to parse Groww tradebook CSV/XLSX files and populate the database.

- [x] Parse Groww CSV tradebook format
- [x] Parse Groww XLSX tradebook format
- [x] Validate imported data (required fields, numeric types, date formats)
- [x] Idempotent re-import (content-key duplicate skip) with audit logging to the imports table

(The UI upload page is part of Phase 6. Implementation notes and the
reference-file findings live in [docs/groww-import.md](docs/groww-import.md).)

Extend Phase 3 to the real broker files in referance/stock/: contract-note
Orders sheets, IIFL Trade Listing .xls and the stocksledger Portfolio
snapshot — see [docs/contract-note-import.md](docs/contract-note-import.md).
## Phase 4: Holdings Calculator ✅

**Goal**: Implement the moving weighted-average cost algorithm for calculating portfolio positions.

- [x] Implement calculate_holdings() function
## Phase 5: CustomTkinter UI ✅

**Goal**: Build the graphical user interface using CustomTkinter.

- [x] Main window with sidebar navigation (active page highlighted)
- [x] Dashboard page with KPI cards (live totals from get_portfolio_summary)
- [x] Holdings, Transactions, Import, Settings pages wired to the live database
- [x] Import page drives all five importers incl. the once-only password dialog
- [x] Display formatting helpers (Indian rupee grouping) with unit tests

(Reports page stays a placeholder until Phase 6; the dashboard chart
placeholder awaits the live-pricing phase. Verified with a headless smoke
test that builds every page against the real database.)
## Phase 6: Export & Reporting ✅

**Goal**: Generate reports and exports from portfolio data.

- [x] Generate text/CSV reports of holdings and transactions (reports/writer.py + tools/export_reports.py CLI + Reports page save dialogs)
- [x] Import page for Groww tradebook upload (built in Phase 5 with all five importers)
## Phase 7: Packaging & Deployment 🔵

**Goal**: Prepare the application for distribution.

- [ ] Configure PyInstaller for standalone executable
- [ ] Map Groww columns to database schema
## Phase 8: Advanced Calculations 🔵

**Goal**: Add advanced financial calculations.

- [ ] FIFO profit and loss calculations
- [ ] Handle multiple date formats and edge cases
## Phase 9: Multi-Broker Support 🔵

**Goal**: Support imports from multiple broker platforms.

- [x] Support Groww tradebook import (Phase 3)
- [x] Support contract-note Orders sheet import (undated rows; caller supplies the trade date)
- [x] Support IIFL Trade Listing .xls import (dated rows, buy+sell sides per instrument)
- [x] Support stocksledger Portfolio snapshot import (hand-entered holdings imported as BUYs)
- [x] Create import result reporting (successes, failures, warnings) via ImportResult
- [x] Contract-note PDF parsing (self-dating; encrypted files via the password vault — see [docs/password-vault.md](docs/password-vault.md))
- [x] Secure password vault (AES-GCM + OS keystore; once-only password prompt)
- [x] Cross-source symbol identity (symbol_aliases table, applied at holdings aggregation)
- [x] F&O symbol normalization across broker sources (calculations/fno.py: every text shape -> `BANKNIFTY 45500 PE 2023-07-27`; spaced / no-space / ISO / IIFL `DD MMM YYYY`, case-insensitive; non-F&O text passes through verbatim)
- [ ] Real encrypted contract-note PDFs: waiting for the user to enter each note's password once (vault flow is ready and tested)

## Phase 9b: Accounts & Live Pricing ✅

**Goal**: Per-account bookkeeping and market valuation of holdings.

- [x] Schema v3 in-place upgrade: `accounts` table (BROKER|PERSONAL, is_main) seeded with "Main broker" + "Main personal"; `prices` table; nullable `account_id` on transactions and holdings (NULL = Unassigned); idempotent structural detection so an interrupted upgrade re-runs safely
- [x] Accounts CRUD + account-scoped getters (`get_transactions` / `get_holdings` / `get_portfolio_summary` take an account filter; `UNASSIGNED` sentinel selects account-less rows)
- [x] Per-account holdings: rebuild_holdings() groups canonicalized transactions by account and values each group from stored prices (market_value = qty x price, profit_loss = market - invested; unpriced symbols stay 0)
- [x] Price store: set_price() upsert (manual or NSE source) then apply_prices_to_holdings() refreshes the cache in place
- [x] Account tagging through every importer: `account_id` parameter on all five importers, commit_import(), the Import page dropdown, and the CLI (`--account NAME`, case-insensitive with a clear error for unknown names)
- [x] Consent-gated NSE fetcher (market_data/nse.py): a consent callable is consulted before EVERY fetch and refusal raises ConsentRequired with zero network traffic; injectable transport so tests never touch the network; symbol mapping (mechanical + overrides; VEDANTA known-delisted) with graceful per-symbol failure reporting
- [x] Accounts page: list (kind, MAIN badge, transaction count, invested) + add form for more broker/personal accounts + Unassigned bucket row
- [x] Prices page: one editable row per holding prefilled from the prices table, Save prices, and Fetch from NSE behind a permission dialog asked on every click
- [x] Dashboard account filter (All accounts / Unassigned / each account) re-rendering KPI cards + top holdings; new Market Value and Profit/Loss cards
- [x] Live database migrated to v3 (manual file backup taken first); 174 transactions, 5 holdings, aliases intact

## Phase 10: Data Synchronization & Backups ✅

**Goal**: Local data protection and recovery.

- [x] Automatic database backup on import (database/backup.py; CLI and UI Import page snapshot data/portfoliox.db into data/backups/ before the first write; keeps the 20 newest)
- [x] Add idempotent import (skip already-imported transactions) (content-key duplicate skip, Phase 3)
## Phase 11: Testing & Quality 🔵

**Goal**: Ensure code quality and reliability.

- [ ] Increase test coverage
- [x] Implement basic CRUD operations
## Phase 12: Production Release 🔵

**Goal**: Release the application to users.

- [ ] Final bug fixes and stability improvements
- [x] Create table initialization script
## Phase Tracking

| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Project Scaffold |
| 2 | ✅ | Database Layer |
| 3 | ✅ | Groww Import System |
| 4 | ✅ | Holdings Calculator |
## Current Sprint: Phase 2 to Phase 3 Transition — ✅ Complete (Oct 28 2026)

**Objective**: Transition from Phase 2 (database layer complete) to Phase 3 (Groww import system).

**This Sprint Goals**:
1. Verify database schema creation from project root — ✅ done (ensure_schema at startup)
2. Create importers/groww.py with CSV parsing — ✅ done (CSV + XLSX)
3. Write PRD.md and Tasks.md documentation — ⬜ not done (PRD lives in PortfolioX_Documentation; a Tasks breakdown was never written)
4. Test the full pipeline: import → calculate → display — ✅ done (Phases 5/6: live UI pages + report exports)

**Success Criteria**:
- Database tables create successfully from project root
- Groww tradebook CSV can be parsed and stored
- Holdings are calculated correctly from imported data
- PRD.md and Tasks.md documents are complete
| 5 | ✅ | CustomTkinter UI |
| 6 | ✅ | Export & Reporting |
| 7 | 🔵 | Packaging & Deployment |
| 8 | 🔵 | Advanced Calculations |
| 9 | 🔵 | Multi-Broker Support |
| 10 | ✅ | Data Synchronization & Backups |
| 11 | 🔵 | Testing & Quality |
| 12 | 🔵 | Production Release |
- [x] Add portfolio summary functions
- [x] Write and run unit tests
- [x] Create app.py entry point