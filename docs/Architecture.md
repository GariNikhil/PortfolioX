# PortfolioX Architecture

## Overview

PortfolioX is a **local-first** desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer — no cloud, no subscriptions, no external services required (the only optional network use is an explicit stock-metadata fetch).

## Technology Stack

- **Language**: Python 3.13+
- **GUI Framework**: CustomTkinter
- **Database**: SQLite (local file-based database, `data/portfoliox.db`, schema v9)
- **Spreadsheets**: openpyxl (XLSX), xlrd (legacy IIFL .xls)
- **PDF parsing**: pypdf (including password-protected contract notes)
- **Vault**: keyring + cryptography (OS credential store, AES-GCM)
- **Packaging**: PyInstaller (planned for standalone executables)

## Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│                        USER LAYER                             │
│  Sidebar pages: Dashboard, Accounts, Import, Holdings hub     │
│  (Stocks / F&O / Mutual Funds), Prices, Transactions,         │
│  Banking, Dividends, Learn, Settings hub                      │
│  (Reports / Tax / Pass Vault / General)                       │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                  CALCULATION LAYER                             │
│                                                               │
│  calculations/holdings.py  -  Moving weighted-average cost    │
│  calculations/fno.py       -  F&O symbol normalization        │
│  calculations/allocation.py - Fund / F&O labelling            │
│  calculations/xirr.py      -  Return statistics               │
│                                                               │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                  │
│                                                               │
│  database/schema.py    -  Versioned schema + migrations (v9)  │
│  database/db.py        -  SQLite connection & transactions    │
│  database/manager.py   -  CRUD operations & helpers           │
│                                                               │
└──────────────────────────────┬───────────────────────────────┘
                               ▼
┌──────────────────────────────────────────────────────────────┐
│                    INPUT LAYER                                 │
│                                                               │
│  importers/groww.py          -  Groww tradebook CSV/XLSX      │
│  importers/pdf_note.py       -  Contract-note PDFs            │
│  importers/contract_note.py  -  Orders sheets                 │
│  importers/iifl.py           -  IIFL trade listings           │
│  importers/stocksledger.py   -  Portfolio snapshot workbooks  │
│  importers/holding_report.py -  Stocks holding reports        │
│  importers/mf_holding_report.py - MF holding reports          │
│  importers/axis_statement.py -  Axis bank statements          │
│  importers/pnb_statement.py  -  PNB mPassbook statements      │
│  importers/common.py         -  Shared audit-first flow       │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

## Key flows

- **Import**: every importer parses to common row dicts, records a PENDING
  audit row, inserts its rows tagged with the audit id, then finalizes the
  status. Duplicates are skipped by a canonical content key, overselling
  rows become row-level failures, and holdings are rebuilt afterwards.
- **Holdings rebuild**: transaction-derived positions merge with manual /
  statement snapshot rows; a holding report makes its account's listed
  positions authoritative (see `docs/database-layer.md`).
- **Remove an import**: the Balance Statement page counts the rows tagged
  to an import, confirms, deletes exactly those rows plus the audit entry,
  and rebuilds holdings.

## Documentation

Feature-level documentation lives in [`docs/`](.): the database layer
(`database-layer.md`), the importers (`groww-import.md`,
`contract-note-import.md`), the holdings calculator
(`holdings-calculator.md`), and the password vault (`password-vault.md`).
