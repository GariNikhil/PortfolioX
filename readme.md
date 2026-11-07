# PortfolioX

PortfolioX is a local desktop portfolio ledger for Indian equity investing (Groww, IIFL and bank statements included). It is designed to keep portfolio data on the user's computer while providing trade imports, holdings calculations, dividend tracking, banking, and reports.

## Project status

The application is a working CustomTkinter desktop app with:

- **Imports** — Groww tradebook (CSV/XLSX), contract-note PDFs and Orders sheets, IIFL trade listings, a stocks-ledger portfolio snapshot, stocks and mutual-fund holding reports, US-stock and bond tradebooks and holding statements, and Axis / PNB bank statements (PDF, plus XLSX/CSV exports). Every import is audited and its rows are tagged to the file that brought them in.
- **Holdings** — moving weighted-average cost, F&O and mutual funds separated from equity, statement-authoritative rebuilds (a holding report defines what the account actually holds), manual holdings, and per-symbol delete.
- **Realized P&L** — FIFO matching: each sale consumes the oldest buy lots, with buy charges rolled into lot cost and sell charges deducted from proceeds, returning per-sale match detail (`calculations/fifo.py`). It is a pure calculation — short/long-term tax classification and any screen or database integration are not built.
- **Banking** — per-account transaction lists, balances, and summaries across personal and broker accounts.
- **Dividends** — dividend entry and reporting.
- **Learn** — an offline hub with four tabs: beginner lessons, a searchable book library, a strategy playbook, and a six-phase planning path. Every book in `referance/books` has distilled notes, and selecting a book opens it for reading inside the app (PDF or its Markdown conversion), in a resizable window with page navigation, find, and adjustable text size. Nothing is fetched from the internet.
- **Prices** — a local price table seeded from holding reports, editable in the app.
- **Calculator** — a dockable panel opened from the calculator icon at the top right: a basic expression pad plus a profit / loss form showing invested amount, proceeds, return percent, and breakeven price.
- **Reports** — Demat report, Balance Statement (account balances plus the full import audit with per-file Remove), Contract Note report, Dividend report.
- **Settings** — Tax, Pass Vault (OS keyring-backed password storage), general settings, and a read-only Published by page whose details live in `ui/published_by_content.py`.
- **Database** — SQLite with versioned, idempotent migrations (schema v9) and automatic backups.
- A test suite of 475 unit tests covering the database, importers, calculations, the offline Learn content, and the book-text reader.

FIFO realized P&L is available as a calculation only: tax classification (short/long-term, grandfathering), a realized-P&L screen, and charts are not built yet. Financial calculations should be treated as assistive information only and verified independently before being used for tax or investment decisions.

## Technology

- **Language:** Python 3.13+
- **GUI:** CustomTkinter
- **Database:** SQLite
- **Spreadsheets:** openpyxl (XLSX) and xlrd (legacy IIFL .xls)
- **PDF parsing:** pypdf (including password-protected contract notes)
- **Vault:** keyring + cryptography (Windows Credential Manager, AES-GCM)
- **Optional metadata fetch:** yfinance (explicit network use only)

PortfolioX works locally without login, cloud storage, or subscriptions. The only feature that touches the internet is the optional stock-metadata fetch in `tools/fetch_stock_metadata.py`, which is run explicitly and never automatically.

## Requirements

- Windows or another platform supported by Python and Tkinter.
- Python 3.13 or newer.
- The dependencies in `requirements.txt`.

The project uses a virtual environment at `.venv`.

## Run the application

From the project root:

```powershell
Set-Location "<path-to-PortfolioX>"
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv\Scripts\python.exe" app.py
```

The application opens on the Dashboard. Use the sidebar to switch pages: Dashboard, Accounts, Import, Holdings, Prices, Transactions, Banking, Dividends, Learn, and Settings (which hosts the Reports, Tax, Pass Vault, General, and Published by tabs). The calculator icon at the top right docks a calculator beside the open page.

On Windows you can also double-click `start.bat`. It runs the app with this folder's `.venv`, so the project can be moved or renamed without editing the file.

## First run

A new install starts empty. The database is created on first launch, and the only rows in it are two placeholder accounts — `Main broker` and `Main personal`.

1. Open **Accounts** and rename those two, or add the accounts you actually hold.
2. Open **Import** and pick your own files: tradebooks, contract notes, holding reports, or bank statements. Every import is audited, so one file can be removed again from the Balance Statement report.
3. Optionally open **Pass Vault** to store the password for encrypted contract notes.

Files are read locally and nothing is uploaded. `data/`, `referance/` and `exports/` are gitignored, so a clone never carries anyone else's portfolio.

## Build a Windows app

`portfoliox.spec` builds a standalone folder that runs without Python installed:

```powershell
& ".\.venv\Scripts\python.exe" -m pip install -r requirements-build.txt
& ".\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean portfoliox.spec
```

The result is `dist\PortfolioX\PortfolioX.exe`; copy the whole `dist\PortfolioX` folder, not the executable alone.

Only `assets` is bundled. `data`, `backups`, `exports` and `referance` are left out on purpose: they hold the live database, generated reports, and personal broker statements and books. A built app creates them next to `PortfolioX.exe`, so `paths.py` resolves those folders from the running app rather than from a module's own path — a bundled module lives in a temporary folder that is deleted on exit. Set `PORTFOLIOX_HOME` to run a build against a different folder, for example to try it without touching your real portfolio.

## Validate the source

Run the test suite. It uses temporary databases and does not modify your portfolio data:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover
```

Compile-check without starting the GUI:

```powershell
& ".\.venv\Scripts\python.exe" -m compileall -q app.py ui books database importers calculations
```

## Folder structure

```text
PortfolioX/
├── app.py                    # Application entry point
├── paths.py                  # Runtime folders (source and built app)
├── start.bat                 # Windows launcher using this folder's .venv
├── portfoliox.spec           # PyInstaller build recipe
├── requirements-build.txt    # Runtime + PyInstaller, for building only
├── phases.md                 # Development roadmap
├── readme.md                 # Project documentation
├── docs/                     # Feature and design documentation
├── ui/                       # CustomTkinter pages, hubs, and theme
│   ├── main_window.py        # Main window and sidebar navigation
│   ├── holdings_hub.py       # Stocks / F&O / Mutual Funds hub
│   ├── reports_hub.py        # Demat / Balance Statement / ... hub
│   ├── settings_hub.py       # Reports / Tax / Pass Vault / General / Published by
│   ├── published_by_content.py  # Published by details (edit these values)
│   ├── published_by_page.py  # Read-only Published by page
│   ├── balance_statement_page.py  # Funds + full import audit with Remove
│   ├── learn_page.py         # Lessons / Book Library / Playbook / Planning
│   ├── learn_content.py      # Offline notes distilled from the books
│   ├── book_reader.py        # In-app book reader window
│   └── ...                   # One file per page, plus theme.py
├── books/                    # Book-text extraction, cleaning, and cache
│   ├── library.py            # PDF / Markdown → readable pages
│   └── test_library.py       # Headless tests for the reading rules
├── database/                 # SQLite schema (v9), manager, backups
├── importers/                # Groww, contract notes, IIFL, holding
│   │                         # reports, Axis / PNB bank statements
├── calculations/             # Holdings, F&O, allocation, XIRR
├── market_data/              # Local price helpers
├── security/                 # Password vault
├── tools/                    # CLI utilities (imports, exports, metadata)
├── data/                     # Local portfolio database (gitignored)
├── referance/                # Real broker files (gitignored, never commit)
└── backups/                  # Local database backups
```

## Data and privacy

PortfolioX stores data locally. The SQLite database is created at `data/portfoliox.db` next to `app.py` (or next to `PortfolioX.exe` in a built app), regardless of the current working directory used to launch it. Do not commit real tradebooks, contract notes, statements, exported reports, or other sensitive financial files to source control; `data/` and `referance/` are gitignored.

Reading a book in Learn parses the file locally on first open and caches the extracted text in `data/book_text/` so later opens are instant. Deleting that folder only means the book is parsed again. Book files are never copied into the repository or bundled with the app, and the reader never downloads anything.

Database backups are written to `data/backups/` before schema migrations and can also be created from the app.

## Documentation

- [`docs/Architecture.md`](docs/Architecture.md) — layers and components.
- [`docs/database-layer.md`](docs/database-layer.md) — schema v9, import tagging, and manager API.
- [`docs/contract-note-import.md`](docs/contract-note-import.md) — real broker file import (dedup, oversells, audit).
- [`docs/groww-import.md`](docs/groww-import.md) — the Groww tradebook importer.
- [`docs/holdings-calculator.md`](docs/holdings-calculator.md) — the holdings algorithm.
- [`docs/SPEC-fifo-realized-pnl.md`](docs/SPEC-fifo-realized-pnl.md) — FIFO realized P&L calculation rules and scope.
- [`docs/password-vault.md`](docs/password-vault.md) — the Pass Vault design.
- [`phases.md`](phases.md) — the development roadmap.
