# PortfolioX - Development Roadmap
## Overview

PortfolioX is a local-first desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer.
- [x] Initialize Python project structure
- [x] Set up version control (.gitignore)
- [x] Create project README
- [x] Set up package structure (database/, calculations/, importers/, ui/)
- [x] Configure Python dependencies (requirements.txt / pyproject.toml)
## Phase 2: Database Layer ✅ **In Progress**

**Goal**: Establish the local SQLite database with schema, connection management, and CRUD operations.

- [x] Define database schema (transactions, holdings, dividends, imports tables)
- [x] Implement connection management (create_connection, DB_PATH handling)
## Phase 3: Groww Import System 🟡 **Current Focus**

**Goal**: Build the import system to parse Groww tradebook CSV/XLSX files and populate the database.

- [ ] Parse Groww CSV tradebook format
- [ ] Parse Groww XLSX tradebook format
- [ ] Validate imported data (required fields, numeric types, date formats)
## Phase 4: Holdings Calculator ✅

**Goal**: Implement the moving weighted-average cost algorithm for calculating portfolio positions.

- [x] Implement calculate_holdings() function
## Phase 5: CustomTkinter UI 🟡

**Goal**: Build the graphical user interface using CustomTkinter.

- [ ] Main window with sidebar navigation
- [ ] Dashboard page with KPI cards
## Phase 6: Export & Reporting 🔵

**Goal**: Generate reports and exports from portfolio data.

- [ ] Generate text/CSV reports of holdings and transactions
- [ ] Import page for Groww tradebook upload
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

- [ ] Support Groww tradebook import (Phase 3)
- [ ] Create import result reporting (successes, failures, warnings)
## Phase 10: Data Synchronization & Backups 🔵

**Goal**: Local data protection and recovery.

- [ ] Automatic database backup on import
- [ ] Add idempotent import (skip already-imported transactions)
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
| 2 | 🟡 | Database Layer (current focus) |
| 3 | 🟡 | Groww Import System (next focus) |
| 4 | ✅ | Holdings Calculator |
## Current Sprint: Phase 2 to Phase 3 Transition

**Objective**: Transition from Phase 2 (database layer complete) to Phase 3 (Groww import system).

**This Sprint Goals**:
1. Verify database schema creation from project root
2. Create importers/groww.py with CSV parsing
3. Write PRD.md and Tasks.md documentation
4. Test the full pipeline: import → calculate → display

**Success Criteria**:
- Database tables create successfully from project root
- Groww tradebook CSV can be parsed and stored
- Holdings are calculated correctly from imported data
- PRD.md and Tasks.md documents are complete
| 5 | 🔵 | CustomTkinter UI |
| 6 | 🔵 | Export & Reporting |
| 7 | 🔵 | Packaging & Deployment |
| 8 | 🔵 | Advanced Calculations |
| 9 | 🔵 | Multi-Broker Support |
| 10 | 🔵 | Data Synchronization & Backups |
| 11 | 🔵 | Testing & Quality |
| 12 | 🔵 | Production Release |
- [x] Add portfolio summary functions
- [x] Write and run unit tests
- [x] Create app.py entry point