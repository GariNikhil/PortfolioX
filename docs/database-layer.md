# PortfolioX - Database Layer

The database is SQLite at `data/portfoliox.db`, created and migrated by
`database/schema.py` and accessed through `database/manager.py`. The schema
is versioned: `PRAGMA user_version` stores the current version, and
`ensure_schema()` applies idempotent migrations in order on every startup,
so the same code works on a fresh database and on an existing one.

## Schema (v9)

Tables:

| Table | Purpose |
|---|---|
| `accounts` | Broker and personal accounts; kind, main flag, current balance, auto-filled details (holder name, account number, phone, PAN, UCC) |
| `transactions` | Equity and F&O trades; money as INTEGER paise |
| `holdings` | Rebuilt holdings cache per symbol (quantity, average price, invested amount) |
| `dividends` | Dividend receipts per symbol |
| `imports` | Import audit: filename, import type, status, timestamp |
| `symbol_aliases` | Verbatim broker names mapped to canonical symbols |
| `prices` | Per-symbol price in paise with a source label |
| `bank_transactions` | Bank statement rows per account (date, description, amount, balance) |
| `stock_metadata` | Sector / market-cap classification per symbol |
| `manual_holdings` | Statement snapshot rows and hand-entered holdings, per account, with a source label |

Conventions:

- **Money is stored as INTEGER paise.** Parsers return rupees;
  `manager` converts at the boundary (`_to_paise` / `_from_paise`).
- **Dates are ISO-8601 strings.**
- Every table has `created_at` / `updated_at` defaults where relevant.

## Import audit and tagging (v9)

Every import creates an `imports` audit row, and every data row it inserts
carries that audit row's id:

- `transactions.import_id`
- `bank_transactions.import_id`
- `manual_holdings.import_id`

`dividends` has no importer yet and therefore no link column.

The flow is **audit-first** (`importers/common.py::commit_import` and the
bank / holding-report importers):

1. `add_import(filename, import_type, "PENDING")` records the audit row and
   returns its id.
2. The parsed rows are inserted with `import_id=import_id`.
3. `set_import_status(import_id, "SUCCESS")` — or `"FAILED (...)"` when the
   batch was rejected — finalizes the audit entry.

A file whose rows were all duplicates still gets one `SUCCESS` audit entry;
a file that fails to parse gets a `FAILED` entry with no data rows.

This makes every imported row traceable to its source file, which powers
the **Remove** option on the Balance Statement page:

- `get_import_row_counts(import_id)` counts the tagged rows per table
  (only non-zero tables are present), so the UI can say what a Remove
  would delete.
- `delete_import(import_id)` deletes the tagged rows in all three tables
  plus the audit row, and returns a counts dict. It is a harmless no-op
  for an unknown id.

Rows inserted by other means (manual entry, older imports) are never
touched by `delete_import`.

## Holdings rebuild

`rebuild_holdings()` recomputes the `holdings` cache from transactions
(moving weighted-average cost, via `calculations/holdings.py`), merged with
`manual_holdings`. Two rules keep statement imports authoritative:

- Once an account has a `holding_report` snapshot, stock and F&O positions
  **not listed in it** drop out of the cache (they stay as transactions).
  `mf_holding_report` governs fund positions the same way.
- `manual` rows always survive the rebuild.

Accounts without any snapshot fall back to transaction-derived holdings.

## Manager API overview

Grouped by area (all in `database/manager.py`):

- **Transactions:** `add_transaction`, `add_transactions`, `delete_transaction`, `get_transactions`
- **Holdings:** `rebuild_holdings`, `get_holdings`, `update_holding`, `delete_holding`, `apply_prices_to_holdings`, `get_portfolio_summary`
- **Accounts:** `add_account`, `get_accounts`, `find_account_by_name`, `find_account_by_id`, `set_main_account`, `set_account_balance`, `update_account_details`, `fill_account_details_if_empty`
- **Manual holdings / statements:** `add_manual_holding`, `replace_holding_report`, `get_manual_holdings`, `delete_manual_holding`, `update_manual_holding`, `move_holding`
- **Bank:** `add_bank_transactions`, `get_bank_transactions`, `count_bank_transactions`
- **Prices:** `set_price`, `get_prices`, `get_prices_paise`
- **Aliases:** `set_symbol_alias`, `delete_symbol_alias`, `get_symbol_aliases`, `canonical_symbol`
- **Dividends:** `add_dividend`, `get_dividends`
- **Import audit:** `add_import`, `set_import_status`, `get_imports`, `get_import_row_counts`, `delete_import`
- **Metadata:** `set_stock_metadata`, `find_stock_metadata`, `get_stock_metadata`

## Migrations

`schema.py` keeps one `_upgrade_to_vN` per version and applies whatever the
database is missing. Notable steps: money conversion from REAL rupees to
INTEGER paise (v1 → v2), the bank-transactions table (v7), stock metadata
(v8), and the `import_id` link columns (v9, added in place with
`ALTER TABLE ... ADD COLUMN`).

## Testing

The suite in `database/` runs against temporary databases (the `DB_PATH`
patch pattern), so tests never touch `data/portfoliox.db`. Schema tests
verify both fresh creation and in-place upgrades, including dropping the
v9 columns and re-migrating.
