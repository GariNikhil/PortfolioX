# PortfolioX - Groww Import System Documentation

## Phase 3: Groww Tradebook Import

### Overview
The Groww Import System (Phase 3) enables PortfolioX to parse Groww tradebook CSV/XLSX files and integrate the parsed data into the existing SQLite database layer established in Phase 2.

> Real broker files (contract-note Orders sheets, IIFL Trade Listing .xls,
> stocksledger Portfolio snapshot) are covered separately in
> [docs/contract-note-import.md](contract-note-import.md); all importers
> share their helpers through `importers/common.py`.

### Features
- Parse Groww CSV tradebook format
- Parse Groww XLSX tradebook format
- Validate imported data against database schema
- Map Groww columns to PortfolioX transactions table schema
- Idempotent import: skip already-imported transactions

### Data Mapping
| Groww Column | Database Field | Type | Notes |
|--------------|----------------|------|-------|
| Date | date | TEXT (YYYY-MM-DD) | Convert from DD-MM-YYYY format |
| Symbol | symbol | TEXT | Stock symbol/name |
| Quantity | qty | REAL | Number of shares |
| Price | price | REAL | Price per share |
| Buy/Sell | buy_sell | TEXT | "Buy" or "Sell" |
| Trade Type | trade_type | TEXT | "Intraday" or "Delivery" |
| Status | status | TEXT | "Square off" or "Open" |
| Product | product | TEXT | "Equity" or "F&O" |

### Requirements
- Python 3.9+
- stdlib `csv` module for CSV parsing
- openpyxl (for XLSX reading; see requirements.txt)
- Existing database layer (Phase 2)

### Validation Rules
- Date must be a valid date in supported formats
- Symbol must not be empty and match stock symbol pattern
- Quantity must be a positive number
- Price must be a positive number
- Trade Type must be "Intraday" or "Delivery"
- Buy/Sell must be "Buy" or "Sell"

### Error Handling
- Invalid Date Format: Skip row, add to failures list
- Missing Required Field: Skip row, add to failures list
- Invalid Quantity: Skip row, add to failures list
- Invalid Price: Skip row, add to failures list

### Acceptance Criteria
- Groww CSV tradebook can be parsed and imported to database
- Groww XLSX tradebook can be parsed and imported to database
- Required field validation works (date, symbol, quantity, price, trade type)
- Idempotent import: re-importing same file skips already-imported transactions
- Import summary report shows success/failure counts

## Implementation status (Oct 28 2026) — done

Implemented in [`importers/groww.py`](../importers/groww.py), tests in
`importers/test_groww.py` (25-test suite green). The committed fixture
`importers/fixtures/groww_tradebook_sample.csv` uses synthetic `DEMO_*`
symbols; real broker files are never read by the test suite.

All acceptance criteria are met, with these design details:

### Column recognition

Headers match case- and whitespace-insensitively against aliases, so exports
across Groww versions keep parsing:

| Canonical | Required? | Aliases |
|---|---|---|
| date | yes | `Trade Date`, `Date` |
| symbol | yes | `Symbol`, `Stock Name`, `Script Name`, `Instrument` |
| quantity | yes | `Quantity`, `Qty`, `Shares` |
| price | yes | `Price`, `Price/Unit`, `Trade Price`, `Price per Unit` |
| side | yes | `Buy/Sell`, `Type`, `Side`, `Action` (values: Buy/Sell, B/S) |
| isin | no | `ISIN` (validated, persisted) |
| exchange | no | `Exchange` |
| brokerage / taxes | no | `Brokerage`, `Charges`, `Taxes` (persisted, feed net_amount) |
| trade type | no | `Trade Type`, `Trade Category` (validated only) |
| status / product | no | recognized, ignored |

A file is rejected with a message naming the missing columns when no header
matches (for example, a UPI expense export has `Date` but no `Symbol`).

### What is stored vs validated only

The v2 schema (see [`data-foundation.md`](data-foundation.md)) has no columns
for Trade Type, Status, or Product, so they are validated but not persisted.
Intraday square-off legs import as ordinary BUY/SELL rows and cancel out
naturally in the holdings cache. A future schema version can add dedicated
columns without changing the parser contract.

Storage follows the data-foundation contract: dates normalized to ISO-8601
`YYYY-MM-DD` (accepts `YYYY-MM-DD`, `DD-MM-YYYY`, `DD/MM/YYYY`, `DD Mon YYYY`,
and native Excel date cells), money handed to `database.manager` as rupees
(stored as exact INTEGER paise), rows inserted atomically via
`add_transactions`, holdings rebuilt, attempt logged to `imports`.

### Duplicate (idempotency) policy

Re-imports skip rows whose content key — (date, symbol, side, quantity,
price in paise) — already exists in the database. Trade-off: two genuinely
identical same-day trades at the same price share a key, so a re-import
treats the second as a duplicate. Pass `skip_duplicates=False` to force a
full re-import.

### Rejection behaviors

- Non-tradebook files are rejected naming the missing columns.
- Legacy `.xls` is not supported by openpyxl — save as CSV/XLSX first.
- Oversell sequences (a SELL before any BUY, e.g. partial trade histories)
  are refused by the holdings validator; import complete histories.
- Every attempt is written to the `imports` table — `SUCCESS` or
  `FAILED (reason)` — even when nothing was imported.

### Reference files inspected (Oct 28 2026) — none is a Groww tradebook

| File | What it actually is | Importer outcome |
|---|---|---|
| `referance/stock/all.csv` | UPI expense tracker export (PNB/Axis/Cash spends) | Rejected: missing Symbol, Quantity, Price |
| `referance/stock/stocksledger.xlsx` | Third-party portfolio template ("MY PORTFOLIO 2014.1"); Portfolio sheet = hand-entered holdings, Ledger = fund flows | Rejected: no sheet has a tradebook header |
| `referance/stock/inter (1).xlsx` | Broker contract-note workbook: Orders sheet with real trades (incl. BANKNIFTY options), Settlement, P&L, Ledger sheets | Rejected: no sheet has a tradebook header |

All three were run through the importer against a scratch database: zero rows
written, real database untouched. Candidate future importers (deliberately
not built in Phase 3): a contract-note "Orders" sheet importer and a
stocksledger Portfolio snapshot importer.