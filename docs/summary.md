# PortfolioX - Documentation Summary

## Project Overview
PortfolioX is a local-first desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer.

## Project Structure
```
d:\projects\PortfolioX\
├── app.py                  # Entry point
├── requirements.txt        # Python dependencies
├── phases.md               # Development roadmap (12 phases)
├── readme.md               # Project documentation
├── database/               # SQLite schema (v9), manager, backups
├── calculations/           # Holdings, F&O, allocation, XIRR
├── importers/              # Groww, contract notes, IIFL, holding
│                           # reports, Axis / PNB bank statements
├── ui/                     # CustomTkinter pages and hubs
├── security/               # Password vault
├── tools/                  # CLI utilities (imports, exports, metadata)
└── docs/                   # Documentation directory
```

## Phase Status
| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Project Scaffold |
| 2 | ✅ | Database Layer (schema v9, versioned migrations) |
| 3 | ✅ | Import system (Groww, contract notes, IIFL, holding reports, bank statements) |
| 4 | ✅ | Holdings Calculator (statement-authoritative rebuilds) |
| 5 | ✅ | CustomTkinter UI (holdings, banking, dividends, prices, reports) |
| 6-12 | 🟡 | FIFO/tax P&L, charts, packaging, release |

## Current Focus
The app is in daily use as a local portfolio ledger. Recent work: import
audit tagging (schema v9) with a per-file Remove on the Balance Statement
page, delete on holdings, and statement-authoritative rebuilds. Next:
FIFO realized P&L and reports polish.

## Documentation Index
- **groww-import.md**: Detailed documentation for the Groww import system
- **database-layer.md**: Schema and CRUD operations documentation
- **holdings-calculator.md**: Algorithm documentation for holdings calculation