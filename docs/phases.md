# PortfolioX Phases

PortfolioX is a personal desktop portfolio ledger for Groww and Indian equity investing. The goal is to build it in a disciplined way: stable backend first, then import logic, calculations, reports, and finally UI polish.

Current known state from the referenced conversation:

- Project name: PortfolioX
- Stack direction: Python desktop app using CustomTkinter
- Database choice: SQLite
- Current milestone: Milestone 2, Database Layer
- Milestone 1.1, Professional UI Foundation, was intentionally skipped for now
- Planned database tables: transactions, holdings, dividends, imports

---

## Phase 0 - Project Control And Working Rules

### Goal
Make the project easy to continue without copy-paste errors, broken indentation, or unclear next steps.

### Work
- Keep all source code inside the PortfolioX project folder.
- Use complete file edits instead of partial snippets.
- Run the app or tests after each meaningful change.
- Keep backend logic separate from UI logic.
- Treat financial calculations carefully and test them with small examples.

### Deliverables
- Clear folder structure.
- A running baseline app.
- A written roadmap, this file.

### Required Skills
- Python basics
- File organization
- Debugging tracebacks
- Basic command-line usage

### Helpful Plugins
- GitHub: useful later for version control, issues, and backups.
- Codex Security: useful later before handling real financial files.

---

## Phase 1 - Basic Application Shell

### Goal
Create a simple desktop application shell that opens reliably.

### Work
- Create `app.py` as the entry point.
- Create `ui/main_window.py`.
- Create `ui/theme.py`.
- Create sidebar navigation.
- Create placeholder pages for:
  - Dashboard
  - Import
  - Holdings
  - Transactions
  - Reports
  - Settings

### Deliverables
- App opens with `python app.py`.
- Sidebar navigation works.
- Dashboard page renders.

### Required Skills
- Python
- CustomTkinter
- UI layout basics
- Package imports

### Helpful Plugins
- Build Web Apps: not required for the current desktop app, but useful if PortfolioX later becomes a web app.
- Product Design: useful later for UI concepts, but not needed for core functionality.

### Notes
Professional UI polish is intentionally deferred. The first priority is correctness and stability.

---

## Phase 2 - Database Layer

### Goal
Create the local SQLite database that stores all portfolio data.

### Work
- Create `database/__init__.py`.
- Create `database/db.py`.
- Create `database/schema.py`.
- Create database tables:
  - `transactions`
  - `holdings`
  - `dividends`
  - `imports`
- Add small database helper functions:
  - `create_connection()`
  - `execute_query()`
  - `fetch_all()`
  - `fetch_one()`
- Add a database manager layer for common operations:
  - `add_transaction()`
  - `get_transactions()`
  - `update_holding()`
  - `get_holdings()`
  - `record_import()`

### Deliverables
- `data/portfoliox.db` is created automatically.
- Tables are created safely with `CREATE TABLE IF NOT EXISTS`.
- Database setup runs from project root.
- Basic insert and select operations work.

### Required Skills
- SQLite
- SQL table design
- Python database programming
- Python package imports

### Helpful Plugins
- Neon Postgres: not needed now because SQLite is better for a local desktop app, but useful if PortfolioX later needs cloud sync.
- Data Analytics: useful later for portfolio summaries and CSV analysis.

---

## Phase 3 - Groww Import System

### Goal
Import Groww tradebook data into the database safely.

### Work
- Create `importers/`.
- Create Groww tradebook parser.
- Support CSV or Excel files, depending on Groww export format.
- Normalize column names.
- Validate required fields:
  - trade date
  - symbol
  - ISIN
  - buy/sell type
  - quantity
  - price
  - charges
  - net amount
- Prevent duplicate imports.
- Store import history in `imports`.
- Store clean rows in `transactions`.

### Deliverables
- User can select a Groww file.
- App reads the file.
- App previews parsed rows.
- App imports valid trades into SQLite.
- Invalid rows are reported clearly.

### Required Skills
- Python
- Pandas or CSV module
- Excel/CSV parsing
- Data validation
- Error handling

### Helpful Plugins
- Data Analytics: useful for inspecting tradebook files and validating imported rows.
- Spreadsheets: useful if sample tradebooks are in `.xlsx` or `.csv` format.

---

## Phase 4 - Holdings Engine

### Goal
Calculate current holdings from imported transactions.

### Work
- Read all buy and sell transactions.
- Group transactions by symbol or ISIN.
- Calculate:
  - current quantity
  - average buy price
  - invested amount
  - realized quantity
  - remaining quantity
- Rebuild holdings whenever transactions change.

### Deliverables
- Holdings table updates from actual transactions.
- Sold-out positions are handled correctly.
- Partial sells are handled correctly.
- Holdings page can display live database values.

### Required Skills
- Python data structures
- Financial transaction modeling
- SQL queries
- Test-case design

### Helpful Plugins
- Data Analytics: useful for validating calculation outputs.

---

## Phase 5 - Profit, Loss, And Tax Logic

### Goal
Calculate realized and unrealized returns correctly.

### Work
- Implement FIFO matching for sell transactions.
- Calculate realized profit and loss.
- Calculate unrealized profit and loss when market prices are available.
- Separate short-term and long-term equity gains where possible.
- Track charges and taxes correctly.
- Add calculation tests using small sample trades.

### Deliverables
- FIFO calculation module.
- Realized P&L report.
- Unrealized P&L report.
- Basic tax classification report.

### Required Skills
- FIFO accounting
- Indian equity capital gains basics
- Python testing
- Careful numerical handling

### Helpful Plugins
- Public Equity Investing: useful for investment terminology and reporting structure.
- Data Analytics: useful for checking calculation accuracy.

### Important Note
Tax logic must be treated as assistive, not as professional tax advice. The app should show calculation assumptions clearly.

---

## Phase 6 - Market Price Updates

### Goal
Update current market value for holdings.

### Work
- Decide price source:
  - manual entry first
  - optional API later
- Add price table if needed.
- Update market value.
- Update unrealized profit and loss.
- Show last updated timestamp.

### Deliverables
- Holdings show market value.
- Dashboard shows current portfolio value.
- User can update prices manually or through a selected source.

### Required Skills
- API usage if automatic prices are added
- Data refresh design
- Error handling

### Helpful Plugins
- Public Equity Investing: useful if market-data workflows are explored.
- Cloudflare or Vercel: useful only if a cloud-hosted service is added later.

---

## Phase 7 - Dashboard

### Goal
Show the most important portfolio information clearly.

### Work
- Display summary cards:
  - total invested
  - current value
  - realized P&L
  - unrealized P&L
  - dividends received
- Add holdings table preview.
- Add recent transactions.
- Add simple charts if useful.

### Deliverables
- Dashboard reads from database.
- Dashboard updates after imports.
- Empty states are clean and helpful.

### Required Skills
- CustomTkinter UI
- Data presentation
- Query integration
- Basic charting if charts are added

### Helpful Plugins
- Product Design: useful for improving dashboard layout.
- Data Analytics: useful for chart and summary validation.

---

## Phase 8 - Transactions, Holdings, And Dividends UI

### Goal
Create usable screens for viewing and managing portfolio records.

### Work
- Transactions page:
  - table view
  - filter by symbol
  - filter by date range
  - add/edit/delete transaction if needed
- Holdings page:
  - current quantity
  - average price
  - invested amount
  - market value
  - profit/loss
- Dividends page:
  - add dividend
  - import dividend if source is available
  - yearly totals

### Deliverables
- User can inspect imported data.
- User can correct mistakes.
- UI stays connected to the database.

### Required Skills
- Desktop UI forms
- Table widgets
- CRUD workflows
- Validation

### Helpful Plugins
- Product Design: useful for making dense financial screens readable.

---

## Phase 9 - Reports And Export

### Goal
Generate useful reports for review, accounting, and backup.

### Work
- Create reports for:
  - holdings
  - realized gains
  - dividends
  - transaction ledger
  - yearly summary
- Export to:
  - CSV
  - Excel
  - PDF later if needed

### Deliverables
- Reports page.
- CSV export.
- Excel export.
- Optional PDF report.

### Required Skills
- Pandas or openpyxl
- Report generation
- File saving
- Data formatting

### Helpful Plugins
- Spreadsheets: useful for `.xlsx` reports.
- PDF: useful for polished report exports.
- Data Analytics: useful for checking report numbers.

---

## Phase 10 - Settings, Backup, And Reliability

### Goal
Make the app safer for real personal data.

### Work
- Add settings page.
- Add database backup.
- Add restore from backup.
- Add import logs.
- Add error logs.
- Add app version display.
- Add simple data integrity checks.

### Deliverables
- Backup button.
- Restore workflow.
- Clear error messages.
- Safer handling of real financial files.

### Required Skills
- File operations
- SQLite backup
- Error logging
- Defensive programming

### Helpful Plugins
- Codex Security: useful for reviewing local data handling.
- GitHub: useful for safe version history, excluding private data.

---

## Phase 11 - Professional UI Foundation

### Goal
Polish the UI after the core system works.

### Work
- Improve theme consistency.
- Improve spacing and typography.
- Add better tables.
- Add loading and empty states.
- Improve import review flow.
- Replace temporary placeholder screens.

### Deliverables
- Clean professional desktop experience.
- Better navigation.
- Better visual hierarchy.
- More confidence using the app daily.

### Required Skills
- UI design
- CustomTkinter component design
- UX writing
- Accessibility basics

### Helpful Plugins
- Product Design: best fit for UI direction.
- Figma: useful only if mockups are created outside the codebase.

---

## Phase 12 - Testing And Release

### Goal
Prepare PortfolioX for regular personal use.

### Work
- Add tests for:
  - database operations
  - Groww import parsing
  - duplicate import detection
  - holdings calculation
  - FIFO profit/loss
- Add sample test data.
- Add a `README.md`.
- Add setup instructions.
- Optionally package as a Windows desktop app.

### Deliverables
- Test suite.
- README.
- Known limitations list.
- Optional `.exe` build.

### Required Skills
- Python testing
- Packaging
- Documentation
- Release discipline

### Helpful Plugins
- GitHub: useful for repository management.
- Codex Security: useful before release.
- Build macOS Apps or Build iOS Apps: not needed unless the project expands to those platforms.

---

# Recommended Folder Structure

```text
PortfolioX/
  app.py
  data/
    portfoliox.db
  database/
    __init__.py
    db.py
    schema.py
    manager.py
  importers/
    __init__.py
    groww.py
  calculations/
    __init__.py
    holdings.py
    fifo.py
    tax.py
  reports/
    __init__.py
    export_csv.py
    export_excel.py
  ui/
    __init__.py
    theme.py
    main_window.py
    dashboard.py
    pages/
      __init__.py
      import_page.py
      holdings_page.py
      transactions_page.py
      reports_page.py
      settings_page.py
    components/
      __init__.py
      sidebar.py
      table.py
  tests/
    test_database.py
    test_import_groww.py
    test_holdings.py
    test_fifo.py
  README.md
```

---

# Plugin Plan

Use plugins only when they clearly help. Do not add plugin complexity too early.

## Useful Now

- Spreadsheets: for reading and verifying Groww CSV/XLSX files.
- Data Analytics: for checking imported rows, portfolio summaries, and calculations.

## Useful Later

- Product Design: for the professional UI phase.
- PDF: for polished exportable reports.
- GitHub: for version control, backups, and issue tracking.
- Codex Security: for reviewing handling of local financial data.
- Public Equity Investing: for investment reporting language and market-data workflows.

## Not Needed For The Current Desktop App

- Vercel
- Supabase
- Neon Postgres
- Cloudflare
- Build Web Apps
- Build iOS Apps
- Build macOS Apps
- Slack
- Teams
- Outlook Email
- Outlook Calendar

These may become useful only if PortfolioX becomes a cloud, mobile, team, or notification-based product.

---

# Professional Engineer Prompt

Use this prompt when asking Codex or another AI engineer to continue PortfolioX.

```text
You are a senior Python engineer helping build PortfolioX, a personal desktop portfolio ledger for Groww and Indian equity investing.

Work style:
- Be task-focused, direct, and friendly.
- Teach briefly when a concept matters, but do not over-explain.
- Make complete, consistent file edits instead of giving partial snippets.
- Prefer stable, boring, maintainable code over clever code.
- Keep the backend, calculations, importers, reports, and UI separated.
- After every meaningful change, run the smallest useful verification.
- If a traceback appears, fix the root cause and explain it in simple terms.
- Do not continue with UI polish until the core data model, import flow, and calculations are reliable.

Current project direction:
- Python desktop application.
- UI framework: CustomTkinter.
- Database: SQLite.
- Main purpose: import Groww tradebook data, store transactions, calculate holdings, track dividends, and generate portfolio reports.

Current phase:
- Continue from Phase 2, Database Layer, unless the existing code shows a different completed state.

Architecture rules:
- `app.py` is the entry point.
- `ui/` contains only user interface code.
- `database/` contains SQLite connection, schema, and manager functions.
- `importers/` contains Groww file parsing and validation.
- `calculations/` contains holdings, FIFO, P&L, and tax-related logic.
- `reports/` contains exports and report generation.
- `tests/` contains focused tests for risky logic.

Implementation rules:
- Use parameterized SQL queries.
- Never build SQL using string concatenation with user data.
- Keep database creation idempotent.
- Avoid broad refactors unless needed for the current phase.
- Handle bad import files gracefully.
- Preserve raw imported values where useful, but store normalized values for calculations.
- Use clear names and small functions.

Verification rules:
- For database work, verify table creation and basic insert/select.
- For import work, verify with a small sample Groww-like file.
- For calculations, verify with simple buy/sell examples where the expected result is obvious.
- For UI work, verify the app opens and the changed page renders.

Financial-care rule:
- Calculations should show assumptions clearly. Tax-related outputs are estimates for personal tracking, not professional tax advice.

Your next action:
1. Inspect the current project files.
2. Identify the exact completed phase.
3. Continue with the next smallest useful step.
4. Edit the files directly.
5. Run verification.
6. Report what changed and what to do next.
```

---

# Immediate Next Step

Continue with Phase 2:

1. Ensure `database/__init__.py` exists.
2. Ensure `database/db.py` creates `data/portfoliox.db`.
3. Create `database/schema.py`.
4. Run the schema creation.
5. Create `database/manager.py`.
6. Add and test basic transaction functions.

