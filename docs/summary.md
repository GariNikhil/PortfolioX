# PortfolioX - Documentation Summary

## Project Overview
PortfolioX is a local-first desktop portfolio management application designed for Indian equity investing. The core principle is that all portfolio data stays on the user's computer.

## Project Structure
```
d:\projects\PortfolioX\
├── app.py                  # Entry point
├── requirements.txt        # Python dependencies
├── phases.md               # Development roadmap (12 phases)
├── PRD.md                  # Phase 3 Product Requirements
├── Tasks.md                # Phase 3 Task breakdown
├── write_phases.py         # Script to generate phases.md
├── database/               # Phase 2: Database layer
│   ├── schema.py           # Table definitions
│   └── manager.py          # CRUD operations
├── calculations/           # Phase 4: Holdings calculator
│   └── holdings.py         # Moving weighted-average cost
├── importers/              # Phase 3: Groww import system
│   └── groww.py            # CSV/XLSX parsing (to be created)
├── ui/                     # Phase 5: CustomTkinter UI
└── docs/                   # Documentation directory
    ├── groww-import.md     # Groww import system documentation
    ├── database-layer.md   # Phase 2 database documentation
    └── holdings-calculator.md # Phase 4 holdings calculator documentation
```

## Phase Status
| Phase | Status | Description |
|-------|--------|-------------|
| 1 | ✅ | Project Scaffold |
| 2 | 🟡 | Database Layer (current focus) |
| 3 | 🟡 | Groww Import System (next focus) |
| 4 | ✅ | Holdings Calculator |
| 5 | 🔵 | CustomTkinter UI |
| 6-12 | 🔵 | Future phases |

## Current Sprint: Phase 2 to Phase 3 Transition
**Objective**: Transition from Phase 2 (database layer complete) to Phase 3 (Groww import system).

**This Sprint Goals**:
1. Verify database schema creation from project root
2. Create importers/groww.py with CSV parsing
3. Write PRD.md and Tasks.md documentation ✅
4. Test the full pipeline: import → calculate → display

**Success Criteria**:
- Database tables create successfully from project root
- Groww tradebook CSV can be parsed and stored
- Holdings are calculated correctly from imported data
- PRD.md and Tasks.md documents are complete

## Documentation Index
- **groww-import.md**: Detailed documentation for the Groww import system
- **database-layer.md**: Schema and CRUD operations documentation
- **holdings-calculator.md**: Algorithm documentation for holdings calculation