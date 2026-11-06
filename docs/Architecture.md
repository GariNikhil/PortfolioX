# PortfolioX Architecture

## Overview

PortfolioX is a **local-first** desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer — no cloud, no subscriptions, no external services required (the only optional network use is an explicit stock-metadata fetch).

## Technology Stack

- **Language**: Python 3.13+
- **GUI Framework**: CustomTkinter
- **Database**: SQLite (local file-based database, `data/portfoliox.db`, schema v9)
- **Spreadsheets**: openpyxl (XLSX), xlrd (legacy IIFL .xls)
- **PDF parsing**: pypdf (contract notes, plus book text in the Learn reader)
- **Vault**: keyring + cryptography (OS credential store, AES-GCM)
- **Packaging**: PyInstaller, driven by `portfoliox.spec` (a folder build; see "Build a Windows app" in `readme.md`)

## Runtime locations

`paths.py` resolves the writable folders for both ways of running the app:

| Location | Source checkout | Built app |
|---|---|---|
| Database | `<repo>/data/portfoliox.db` | `<exe folder>/data/portfoliox.db` |
| Password vault | `<repo>/data/vault.json` | `<exe folder>/data/vault.json` |
| Book cache | `<repo>/data/book_text/` | `<exe folder>/data/book_text/` |
| Personal books | `<repo>/referance/books/` | `<exe folder>/referance/books/` |

Modules ask `paths.app_root()` instead of computing a folder from `__file__`. Inside a PyInstaller build a module's own path points into a temporary folder that is deleted on exit, so writing there would silently reset the portfolio on every launch. `PORTFOLIOX_HOME` redirects all four, which is how a build can be tried without touching real data.


## Architecture Layers

Top to bottom: the UI calls calculations, calculations read the data layer,
and the data layer is fed by the importers.

| Layer | Modules |
|---|---|
| **User** | Sidebar pages: Dashboard, Accounts, Import, Holdings hub (Stocks / F&O / Mutual Funds), Prices, Transactions, Banking, Dividends, Learn hub (Lessons / Book Library / Strategy Playbook / Planning, content in `ui/learn_content.py`, book reader in `ui/book_reader.py`), Settings hub (Reports / Tax / Pass Vault / General / Published by), plus a dockable calculator panel (`ui/calculator_panel.py`) beside the open page |
| **Calculations** | `calculations/holdings.py` (moving weighted-average cost), `calculations/fifo.py` (FIFO realized P&L), `calculations/calculator.py` (safe expression evaluation and profit / loss), `calculations/fno.py` (F&O symbol normalization), `calculations/allocation.py` (fund / F&O labelling), `calculations/xirr.py` (return statistics) |
| **Data** | `database/schema.py` (versioned schema + migrations, v9), `database/db.py` (SQLite connection & transactions), `database/manager.py` (CRUD operations & helpers) |
| **Input** | `importers/` — see below. Separate from portfolio data, `books/` reads local book files for the Learn reader |

### Importers

Most importers are one file per source file *format*; US-stock and bond files
reuse the equity parsers instead of duplicating them, because they are the
same table shape with a different label.

| Module | Handles |
|---|---|
| `groww.py` | Groww tradebooks (XLSX/CSV) — also US-stock and bond tradebooks via `source_kind` (`US_TRADEBOOK` / `BOND_TRADEBOOK`) |
| `holding_report.py` | Stocks holding statements — also US-stock and bond statements via `source` (`us_holding_report` / `bond_holding_report`) |
| `mf_holding_report.py` | Mutual-fund holding statements |
| `contract_note.py` | Contract-note Orders sheets |
| `pdf_note.py` | Contract-note PDFs (including password-protected) |
| `iifl.py` | IIFL trade listings (legacy `.xls`) |
| `stocksledger.py` | stocksledger portfolio snapshot workbooks |
| `axis_statement.py` | Axis bank statements (PDF) |
| `pnb_statement.py` | PNB mPassbook statements (PDF) |
| `bank_statement_tabular.py` | Axis / PNB bank statements as XLSX or CSV |
| `bank_common.py` | Shared bank-import flow (account resolution, detail auto-fill, duplicate skipping) |
| `common.py` | Shared audit-first flow, number/date parsing, duplicate keys |
| `support.py` | Test-support helpers |

## Key flows

- **Import**: every importer parses to common row dicts, records a PENDING
  audit row, inserts its rows tagged with the audit id, then finalizes the
  status. Duplicates are skipped by a canonical content key, overselling
  rows become row-level failures, and holdings are rebuilt afterwards.
- **Holdings rebuild**: transaction-derived positions merge with manual /
  statement snapshot rows. A stocks statement (`holding_report`) makes its
  account's stock and F&O positions authoritative, a fund statement
  (`mf_holding_report`) does the same for funds, and US-stock / bond
  statements (`us_holding_report` / `bond_holding_report`) replace only the
  symbols they list. See `docs/database-layer.md`.
- **Remove an import**: the Balance Statement page counts the rows tagged
  to an import, confirms, deletes exactly those rows plus the audit entry,
  and rebuilds holdings.
- **Learn content**: `ui/learn_content.py` holds frozen dataclasses
  (`Track`, `Book`, `PlaybookEntry`, `PlanningPhase`) and the curated
  constants the Learn tabs render. It imports no Tk or database modules,
  so it is unit-tested headless (`ui/test_learn_content.py`). The notes
  are original summaries of the books in `referance/books`; the source
  files stay local and nothing is fetched from the network.
- **Reading a book**: clicking a book card (or its "Read book" button)
  calls `open_reader`, which opens one non-modal `BookReader` per book and
  lifts an existing window instead of stacking a second copy. The window
  asks `books/library.py` for a `Source` (the Markdown conversion when one
  sits beside the PDF, else the PDF), serves cached pages from
  `data/book_text/` when the file is unchanged, and otherwise extracts on
  a background thread in 10-page batches, inserting pages as they arrive
  so a 600-page PDF stays responsive. Cleaning drops running heads, page
  numbers, ligatures and soft hyphens, then reflows hard-wrapped lines
  into paragraphs. The module imports no Tk code, so the rules are tested
  headless in `books/test_library.py`; a missing file is explained in the
  window, never downloaded.

## Documentation

Feature-level documentation lives in [`docs/`](.): the database layer
(`database-layer.md`), the importers (`groww-import.md`,
`contract-note-import.md`), the holdings calculator
(`holdings-calculator.md`), and the password vault (`password-vault.md`).
