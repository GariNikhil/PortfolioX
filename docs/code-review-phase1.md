# PortfolioX — Phase 1 Code Review

> Reviewed: Oct 28 2026 · Scope: full project tree (excluding `.venv/`, `__pycache__/`, `backups/`, vendored `.clinerules/` skill bundle)
> State at review time: ~850 lines of Python across 18 files · `compileall` clean · 9/9 tests pass

## What it is

Local-first desktop portfolio ledger (Python 3.14 + CustomTkinter + SQLite) for Groww /
Indian equity investing, currently at Phase 1: app shell, database layer, holdings calculator.

## Strengths

1. **`calculations/holdings.py` is the strongest file.** Aggressive validation (oversells,
   NaN/inf, bad transaction types raise `ValueError` instead of producing wrong positions),
   chronological re-sorting independent of query order, accepts DB tuples or mappings,
   frozen dataclass, correct epsilon tolerances.
2. **Honest documentation** — readme explicitly states what is *not* done.
3. **Tests never touch real data** — `DB_PATH` is patched into temp directories.
4. **SQL fully parameterized** — no injection risk.
5. **Specs before code** — `docs/` holds PRD.md, Architecture.md, SPEC-fifo-realized-pnl.md.
6. DB location resolved from `__file__`, not CWD — app runs from anywhere.

## Findings

### 🔴 High — fix before continuing

| # | Finding | Reference |
|---|---------|-----------|
| 1 | `create_tables()` never called at app startup → fresh install crashes with `no such table: transactions` on first data access (works locally only because `data/portfoliox.db` already exists) | `app.py`, `database/schema.py` |
| 2 | Not a git repo, no `.gitignore`, no `requirements.txt` — while `phases.md` marks all three done. Worst risk: no history to recover from bad edits | root |
| 3 | `.clinerules/skills/A4-Claude-skills-main` vendored collection (~140k+ lines, 300+ files) pollutes the tree and swamps code search | `.clinerules/` |

### 🟠 Medium — decide before the Phase 3 importer

| # | Finding | Reference |
|---|---------|-----------|
| 4 | Money stored as `REAL` (float) — drift risk for a financial ledger | `database/schema.py` |
| 5 | `net_amount` always = qty×price + charges — wrong semantics for SELLs (proceeds should subtract charges) | `database/manager.py:15` |
| 6 | `holdings` is derived state that can drift; no way to delete/correct a transaction; no rebuild-from-transactions function | `database/manager.py` |
| 7 | No `NOT NULL` / `CHECK` constraints on core columns | `database/schema.py` |
| 8 | All ordering assumes ISO date text sort; Groww CSVs are not ISO → importer must normalize dates to `YYYY-MM-DD` or ordering silently breaks | `manager.py`, `holdings.py` |

### 🟡 Lower priority / polish

| # | Finding | Reference |
|---|---------|-----------|
| 9 | New connection per query — bulk import would open 1,000 connections | `database/db.py` |
| 10 | Raw tuple reads; tests assert magic indexes like `[0][10]` | `database/manager.py`, `test_manager.py` |
| 11 | Sidebar buttons never highlight the active page | `ui/main_window.py` |
| 12 | Pages destroyed/recreated on navigation (future state loss) | `ui/main_window.py` |
| 13 | `from ui.theme import *` wildcard imports | all UI pages |
| 14 | No `requirements.txt` | root |
| 15 | `bypass` file is a stray extension-less note | root |
| 16 | Dashboard KPIs hardcoded `₹0.00` (acceptable for this phase) | `ui/dashboard.py` |
| 17 | Typo: `referance notes` folder | root |

## Recommended order of attack

1. `git init` + `.gitignore` + first commit — protects everything else
2. `create_tables()` (schema ensure) on startup — kills the fresh-install crash
3. `requirements.txt` + truthful `phases.md` state
4. Exclude the vendored skills bundle from the repo
5. Before Phase 3: make the trader decisions from findings 4–8 — they shape the importer
   (recorded in [`data-foundation.md`](data-foundation.md) as they land)

## Verification commands

```powershell
& ".\.venv\Scripts\python.exe" -m compileall -q app.py ui database calculations
& ".\.venv\Scripts\python.exe" -m unittest discover -v
```

## Outcome (Oct 28 2026)

| Action plan item | Result |
|---|---|
| 1. git init + .gitignore + first commit | `087f717` — 47 files tracked; `referance/` (real contract notes & statements), `data/`, `backups/`, `.clinerules/skills/`, `.venv/` excluded. Repo-local identity set; replace with a real email before any future `git push`. |
| 2. Schema on startup | `444066a` — app.py creates/ensures the schema; kills the fresh-install crash |
| 3. requirements.txt + truthful roadmap | `444066a` (customtkinter 6.0.0 pinned); phases.md updated to match reality |
| 4. Exclude vendored skills bundle | `.clinerules/skills/` ignored in git (kept on disk so Cline keeps working; same for your own `.clinerules` rule files, which **are** tracked) |
| 5. Trader decisions (findings 4–8) | Implemented as Phase 2.5 in this commit — paise INTEGER money, side-aware net_amount, `delete_transaction` + `rebuild_holdings`, DB constraints with v1→v2 migration, ISO-date contract for the importer. Decisions: [`data-foundation.md`](data-foundation.md) · Tests 17/17 green |

### Incident note (same day): commit `95b97d3` accidentally tracked the vendored skill bundle

`smart_commit.sh` stages with an unconditional `git add .`. When the agent
configuration dir was renamed `.clinerules/` → `.opencode/` (carrying the 4,465-file
vendored `A4-Claude-skills-main` collection to a path not yet covered by
`.gitignore`), commit `95b97d3` swept the whole bundle in. Fixed immediately
after in a following chore commit: `.opencode/skills/` added to `.gitignore` and
untracked with `git rm -r --cached` (kept on disk so agent skills keep working).
The blobs remain in history until a `git filter-repo` purge before any first push.
Rule files (`cline-skills.md`, `project-workflow.md`, `settings.json`) stay tracked
at their new `.opencode/` location.
