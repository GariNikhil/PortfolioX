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

## `importers/pdf_note.py` — Contract-note PDFs

Source inspected: the **unencrypted** samples
`referance/stock/CONTRACT NOTE/07-2023/28.pdf` and `31.pdf` (8 pages each).
The PDFs carry the **same Orders layout** as the xlsx — order no, order
time, trade no, trade time, Security/Contract description, exchange, B/S,
quantity, rate, optional middle columns, Net Total — extracted as text.

- **Self-dating**: each note carries its own `Trade date DD-MM-YYYY` header
  line, so unlike the Orders xlsx no caller-supplied date is needed.
- **Trade-line matching**: rows must start with a 10–16 digit order number,
  two times, a trade number and a second time; page headers, per-instrument
  `Total` rows and `Net Total` lines never match and are skipped.
- **Brokerage from money, not columns**: the optional middle columns
  (brokerage / net rate / closing rate) are ambiguous in extracted text, so
  charges = |Net Total| − quantity×rate. This keeps the stored row exactly
  consistent with the note's own Net Total (0 for the common no-charges
  rows) and cannot misread `25010.00` as a per-unit rate.
- **SELL quantities arrive negative** in the text; the stored magnitude is
  positive with the side carrying the direction (same as the xlsx).
- Requires `pypdf` (in requirements.txt; `pdfplumber` stays commented out).

Result on the real unencrypted sample (scratch DB): all trade rows of
`28.pdf` parse and import through the standard `commit_import()` path.

### Encrypted notes and the password vault

The real archive (`CONTRACT NOTE 1234567890*.pdf`, the 06-2022 pair) is
password-protected. `parse_contract_note_pdf()` resolves the password via
`security/vault.password_for(path, "CONTRACT_NOTE_PDF")`:

- no stored password → `PasswordRequiredError` (the once-only prompt; not
  an audit failure),
- stored password → decrypt and parse automatically,
- rejected password → `PasswordRequiredError` naming the file.

See [docs/password-vault.md](password-vault.md) for the vault design.

## `database/manager.py` — Cross-source symbol identity

The same company arrives under different verbatim names (`VEDANTA` from the
hand-entered snapshot vs `VEDANTA LIMITED` from IIFL; `COAL INDIA LTD.` vs
`COAL INDIA LTD`). A `symbol_aliases` table (alias → canonical, additive to
schema v2) merges them **at holdings-aggregation time only**:

- `rebuild_holdings()` canonicalizes transaction symbols through the alias
  table before `calculate_holdings()`; the `transactions` table keeps the
  verbatim symbols, so provenance is never lost.
- Aliases are single-level by construction: an alias key may not already be
  a canonical target, and a canonical target may not itself be an alias
  key — chains and cycles are rejected with `ValueError` at write time.
- Re-pointing an alias takes effect on the next rebuild; deleting one
  splits the holding again on the next rebuild.

## Known limitations / follow-ups

- **Real encrypted PDFs still locked.** The vault flow is built and tested,
  but the actual passwords for `CONTRACT NOTE 1234567890*.pdf` and the
  06-2022 pair must be entered once by the user (or discovered from broker
  conventions such as PAN case variants); until then those files cannot be
  imported.
- **Multi-day Orders workbooks** need to be split into per-date files (one
  `trade_date` per import) until the day boundaries can be established from
  broker metadata.
- The UI import page (Phase 6) will surface `ImportResult.summary()` and
  the failure list; the audit trail already distinguishes import kinds:
  `GROWW_TRADEBOOK`, `CONTRACT_NOTE_ORDERS`, `IIFL_TRADE_LISTING`,
  `STOCKSLEDGER_PORTFOLIO`, `CONTRACT_NOTE_PDF`.
