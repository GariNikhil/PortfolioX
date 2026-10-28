# Real broker file import: contract notes, IIFL trade listings, stocksledger

Phase 3 started with the Groww tradebook (see
[docs/groww-import.md](groww-import.md)). This document covers the importers
built against the **real files** in `referance/stock/` — a broker-archive
folder containing contract-note workbooks, IIFL Securities exports, a
hand-entered portfolio snapshot and password-protected PDFs.

> `referance/` holds real financial records (client code, masked PAN,
> address). It is gitignored and must never be committed; the importers are
> tested against synthetic workbooks built in the test suite, and the real
> files are only read locally, against a scratch database.

## Shared importer infrastructure (`importers/common.py`)

All importers (Groww included) share the same contract, per
[docs/data-foundation.md](data-foundation.md):

- Money as INTEGER paise, side-aware net amounts (BUY = qty×price + charges,
  SELL = qty×price − charges), ISO-8601 dates.
- `ImportFileError` for file-level problems (after a FAILED audit entry),
  `RowFailure`/`ImportResult` for the row-level report.
- `commit_import()` dedupes by content key (date, symbol, side, quantity,
  price in paise), then inserts atomically via `database.manager` and
  rebuilds holdings.

**Oversell handling.** Real contract notes sell shares bought in an earlier
period or held in demat — e.g. the real Orders sheet sells 3 DR. REDDY S
LABORATORIES that this database has never seen. One such row used to fail
the whole batch inside `rebuild_holdings()`. `commit_import()` now simulates
positions (same ordering and tolerance as
`calculations/holdings.py::calculate_holdings`) and converts overselling
rows into row-level failures (`row_number=0`, reason names the symbol), so
the rest of the file still imports. Import the earlier buys (or opening
holdings) first if you want those rows accepted.

## `importers/contract_note.py` — Orders sheet

Source inspected: `referance/stock/inter (1).xlsx`, sheet `Orders` — 384
non-empty rows, ~26 day-blocks, 50 instruments (BANKNIFTY / FINNIFTY / NIFTY
options, plus a few equity blocks).

Format quirks and how the importer handles them:

| Quirk in the real file | Handling |
|---|---|
| **No date column anywhere** (it is a multi-day concatenation; each day-block repeats the header) | `trade_date` is a required argument applied to every row. A multi-day workbook must be split by block first; the blocks are not machine-datable (order numbers cluster by day, but that is an assumption, not a fact). |
| Repeated header rows, one variant starting with `Order no.` and a shifted variant with `Column1` in column A | Both are detected (whitespace/newlines inside header cells are collapsed before matching) and skipped. |
| Per-instrument `Total` rows and block `Net Total` rows | Any of the first five cells equal to `total` or containing `net total` is skipped. |
| `Buy(B)/Sell(S)` column; sells stored as negative quantities | Side comes from B/S; when the cell is empty the quantity sign decides (e.g. expired-option rows). |
| `Expired` rows: quantity −75, price 0 | Imported as SELL at price 0 — legitimate (zero price is allowed; negative prices are not). The realized loss is captured by the average-cost calculation when the position closes. |
| Brokerage only as `Brokerage per Unit` | Stored as per-unit × quantity; other levies are not itemized, so taxes are 0. |
| Instrument text like `BANKNIFTY 45500 CE 13 Jul 2023` | Stored **verbatim** (upper-cased, whitespace-collapsed). Symbols are not decomposed into symbol/strike/expiry, and spacing variants such as `BANKNIFTY45500PE27Jul2023` are not normalized. |

Result on the real file (scratch DB, `trade_date=2023-07-03`):
**281 parsed rows → 278 imported, 3 oversell failures** (the demat sells).

## `importers/iifl.py` — Trade Listing .xls

Source inspected: `referance/stock/CONTRACT NOTE/Trade_Listing
DEMO_8_19_2024.xls`, sheet `TradeListing_Equity_Currency` — header at
sheet row 12, 26 data rows spanning 2022-05-09 → 2024-08-19 (NSECASH
equities + NSEFNO NIFTY options). Requires `xlrd` (pinned 2.0.2; the files
are genuine OLE2 .xls and xlrd prints a harmless
`WARNING *** file size ...` while reading them).

- One row per instrument per trade date with **both** sides aggregated:
  the importer emits up to two transactions (BUY and/or SELL) per sheet
  row. Equities (PENIND, NTPC, TATASTEEL, TATAMOTORS) use the `Name` ticker
  as symbol; F&O rows (Option Type CE/PE) build
  `<Code> <Strike> <OptionType> <expiry-ISO>` (e.g.
  `NIFTY 19300 PE 2023-08-03`).
- Trade Date arrives as DD/MM/YYYY text; Excel serial floats are also
  accepted (via `xlrd.xldate.xldate_as_datetime` with the workbook
  datemode). Expiry Date is a YYYYMMDD float.
- `Market Rate` is used as the trade price and `Brokerage` as the rupee
  brokerage. IIFL's per-unit `Net Rate` does **not** reconcile with
  `Amt ± Brokerage` (their internal charge math is not documented), so it
  is deliberately ignored.
- Testing: xlrd cannot write .xls files, so `parse_trade_listing_rows()`
  (the parser core) is tested with synthetic row lists; only the file-level
  error paths touch real files.

Result on the real file (scratch DB): **26 sheet rows → 40 parsed
transactions, 0 parse failures; 39 imported, 1 oversell failure**.

## `importers/stocksledger.py` — Portfolio snapshot

Source inspected: `referance/stock/stocksledger.xlsx`, sheet `Portfolio` —
a downloaded stocksledger template (header on row 2, instruction text,
derived columns, repeated header blocks).

- This is a **snapshot, not a trade history**: each hand-entered holding is
  imported as a BUY. There is no sell side, so holdings opened and fully
  closed before the snapshot date cannot be reconstructed from it.
- The real sheet contains exactly 4 holdings (Vedanta 17, Coal India Ltd. 1,
  Punj. NationlBak 20, Reliance Power L 35) plus partial template copies.
  Identical (symbol, date, qty, price) rows inside one file are imported
  once; partial rows (missing price/qty/date) become row failures.
- `Brokerage` here is a rupee amount and is stored as-is.

Result on the real file (scratch DB): **4 imported, 3 template-debris
failures**.

## Known limitations / follow-ups

- **Contract-note PDFs are encrypted.** All `CONTRACT NOTE 1234567890*.pdf`
  and the 06-2022 trade-detail PDFs are password-protected; parsing is
  blocked pending the user's password / password-locker decision
  (`pdfplumber` is intentionally not yet in requirements.txt).
- **Cross-source symbol identity.** The same company appears under
  different verbatim symbols from different sources (`VEDANTA` vs
  `VEDANTA LIMITED`, `PUNJ. NATIONLBAK` vs `PUNJAB NATIONAL BANK`), so they
  form separate holdings. A symbol-mapping step is future work (Phase 9+).
- **Multi-day Orders workbooks** need to be split into per-date files (one
  `trade_date` per import) until the day boundaries can be established from
  broker metadata.
- The UI import page (Phase 6) will surface `ImportResult.summary()` and
  the failure list; the audit trail already distinguishes import kinds:
  `GROWW_TRADEBOOK`, `CONTRACT_NOTE_ORDERS`, `IIFL_TRADE_LISTING`,
  `STOCKSLEDGER_PORTFOLIO`.
