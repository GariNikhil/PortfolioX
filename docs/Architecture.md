# PortfolioX Architecture

## Overview

PortfolioX is a **local-first** desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer — no cloud, no subscriptions, no external services required (internet access may be added later as an optional feature for market prices).

## Technology Stack

- **Language**: Python 3.13+
- **GUI Framework**: CustomTkinter (modern Tkinter wrapper with dark/light mode support)
- **Database**: SQLite (local file-based database, `data/portfoliox.db`)
- **Spreadsheet support**: openpyxl and pandas (for import/export workflows)
- **PDF parsing**: pdfplumber (planned)
- **Charts**: matplotlib (planned)
- **Packaging**: PyInstaller (planned for standalone executables)

## Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│                        USER LAYER                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┐       │
│  │  Dashboard  │  │  Import     │  │  Holdings   │  │       │
│  │  Reports    │  │  Transactions│  │  Settings   │  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  │       │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    CALCULATION LAYER                           │
│                                                               │
│  calculations/holdings.py  -  Moving weighted-average cost    │
│  calculations/fifo.py      -  FIFO profit and loss (planned)  │
│  calculations/tax.py       -  Tax calculations (planned)      │
│                                                               │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                  │
│                                                               │
│  database/schema.py   -  SQL table definitions                │
│  database/db.py       -  SQLite connection & setup            │
│  database/manager.py    -  CRUD operations & helpers          │
│                                                               │
└──────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    INPUT LAYER                                 │
│                                                               │
│  importers/groww.py   -  Groww tradebook CSV/XLSX parsing       │
│                                                               │
└──────────────────────────────────────────────────────────────┘
