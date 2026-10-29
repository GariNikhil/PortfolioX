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
- **Audit-first imports (schema v9).** `commit_import()` records the audit
  row as PENDING before inserting anything, tags every inserted row with
  that audit id (`import_id` on transactions, bank_transactions and
  manual_holdings), and flips the status to SUCCESS/FAILED when the batch
  commits. Every imported row is therefore traceable to its source file,
  and the Balance Statement page can Remove a file together with exactly
  the rows it inserted (see `docs/database-layer.md`).
- `commit_import()` dedupes by content key (date, **canonical** symbol, side,
  quantity, price in paise) — the symbol is canonicalized through the same
  F&O + alias normalization `rebuild_holdings()` applies, so the same trade
  imported under different verbatim names (`VEDANTA` vs `VEDANTA LIMITED`,
  or two F&O expiry spellings) is skipped on re-import instead of doubling
  the holding. Then it inserts atomically via `database.manager` and
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

Two refinements keep legitimate real-world notes importing:

- **Canonical position matching.** The simulation matches incoming rows
  against holdings by canonical symbol (F&O shape, then aliases), the same
  normalization the rebuild applies — a note selling `PUNJAB NATIONAL BANK`
  is covered by a holding stored as `PNB`.
- **Same-day roundtrips import regardless of printed order.** Notes list
  intraday roundtrips in trade-time order, which sometimes puts sells
  before their same-day buys (real note 5874818698-9: Zomato sells 10/51
  printed before the buys they close). Within a (symbol, date) group whose
  sells are covered by the day's buys plus the position held before the
  import, rows are inserted buys-first so the (trade date, id) rebuild
  ordering never sees an oversell. Groups that remain infeasible keep
  their file order and the genuinely overselling rows are rejected.

## `importers/contract_note.py` — Orders sheet

Source inspected: `referance/stock/inter (1).xlsx`, sheet `Orders` — 384
non-empty rows, ~26 day-blocks, 50 instruments (BANKNIFTY / FINNIFTY / NIFTY
options, plus a few equity blocks).

Format quirks and how the importer handles them:

| Quirk in the real file | Handling |
|---|---|
| **No date column anywhere** (it is a manual amalgamation; see below) | `trade_date` is a required argument applied to every row. |
| Repeated header rows, one variant starting with `Order no.` and a shifted variant with `Column1` in column A | Both are detected (whitespace/newlines inside header cells are collapsed before matching) and skipped. |
| Per-instrument `Total` rows and block `Net Total` rows | Any of the first five cells equal to `total` or containing `net total` is skipped. |
| `Buy(B)/Sell(S)` column; sells stored as negative quantities | Side comes from B/S; when the cell is empty the quantity sign decides (e.g. expired-option rows). |
| `Expired` rows: quantity −75, price 0 | Imported as SELL at price 0 — legitimate (zero price is allowed; negative prices are not). The realized loss is captured by the average-cost calculation when the position closes. |
| Brokerage only as `Brokerage per Unit` | Stored as per-unit × quantity; other levies are not itemized, so taxes are 0. |
| Instrument text like `BANKNIFTY 45500 CE 13 Jul 2023` | Stored **verbatim** (upper-cased, whitespace-collapsed). Symbols are not decomposed into symbol/strike/expiry, and spacing variants such as `BANKNIFTY45500PE27Jul2023` are not normalized. |

Result on the real file (scratch DB, `trade_date=2023-07-03`):
**281 parsed rows → 278 imported, 3 oversell failures** (the demat sells).

### Why the Orders workbook cannot be self-dated (block analysis, Oct 2026)

A full block analysis of `inter (1).xlsx` settled the dating question:

- The Orders sheet has **29 header-delimited blocks**, not clean day-blocks.
  They are **not chronological**: block 1's times run 09:36→09:35, trade
  numbers jump wildly between blocks, and 03-Aug-expiry instruments appear
  in the *last* blocks between equity rows.
- The blocks came from **different sources**: blocks 1–17 use spaced symbol
  text (`BANKNIFTY 45500 CE 13 Jul 2023`), blocks 18–24 a no-space variant
  (`BANKNIFTY45500PE27Jul2023`) that matches PDF text extraction.
- One hard anchor exists: **block 18 is 2023-07-27** — its first row
  (order `1800000115399826`, trade `698378429`, 12:12:53) is byte-identical
  to the first trade of the unencrypted contract note `28.pdf`
  (Trade date 27-07-2023).
- The workbook's own **Settlement sheet (16 dated settlement blocks,
  2023-07-03 → 2023-08-01) and P&L sheet cannot be joined** to Orders rows:
  Orders rows carry no settlement numbers.

**Dating strategy going forward:** contract notes repeat the same
(order no, trade no) pairs as the Orders sheet. Once the encrypted PDFs
are unlocked and imported (they self-date), Orders blocks can be dated by
matching their trade numbers against the imported PDF trades. Until then
the workbook stays unimported — stamping 29 mixed-source blocks with one
date would corrupt the record.

## `importers/iifl.py` — Trade Listing .xls

Source inspected: `referance/stock/CONTRACT NOTE/Trade_Listing
MUDAPPAG_8_19_2024.xls`, sheet `TradeListing_Equity_Currency` — header at
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
- **The snapshot rows duplicate the official contract notes.** Attribution
  (Oct 2026): all 4 snapshot rows re-appear in notes 1–5/10 under the full
  names (`VEDANTA LIMITED`, `COAL INDIA LTD`, `PUNJAB NATIONAL BANK` 40,
  `RELIANCE POWER LTD.`) — the notes are the authoritative record. Two
  snapshot entries even contradict them (PNB 20 vs the note's 40; Coal
  India 233.05 vs the note's 233.5). The snapshot rows were removed from
  the live database in favour of the notes; the aliases
  (`PUNJ. NATIONLBAK`, `RELIANCE POWER L`, …) keep a future re-import of
  this file deduping to a no-op — except the contradictory PNB row, which
  content dedup cannot reconcile (different quantity) and which must not
  be re-imported.

Result on the real file (scratch DB): **4 imported, 3 template-debris
failures**.

## `importers/pdf_note.py` — Contract-note PDFs

Source inspected: the **unencrypted** samples
`referance/stock/CONTRACT NOTE/07-2023/28.pdf` and `31.pdf` (8 pages each).
The PDFs carry the **same Orders layout** as the xlsx — order no, order
time, trade no, trade time, Security/Contract description, exchange, B/S,
quantity, rate, optional middle columns, Net Total — extracted as text.

- **Self-dating**: each note carries its own `Trade date DD-MM-YYYY` header
  line, so unlike the Orders xlsx no caller-supplied date is needed. The
  header match is case-insensitive — real notes print both `Trade date`
  (notes 1–5, 10) and `Trade Date` (notes 6–9).
- **Trade-line matching**: rows must start with a 10–16 digit order number,
  two times, a trade number and a second time; page headers, per-instrument
  `Total` rows and `Net Total` lines never match and are skipped.
- **Wrapped F&O descriptions are joined back**: pypdf wraps long contract
  descriptions across three physical lines (`… BANKNIFTY 45700 CE 20 Jul` /
  `2023` / `NSE B 25 138.20 138.20 -3455.00`). When a trade line carries no
  B/S flag and the next two lines are a bare year plus an
  exchange+side+numbers tail, the three lines are merged into one logical
  row (notes 6 and 8; six trades this used to drop).
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

Result on the real encrypted notes (scratch DB, passwords from the vault):
notes 1–5, 10 and 28, 29, 31 import cleanly; notes 6–9 (after the
case-insensitivity and unwrap fixes) import 50 trades with the only
remaining failure being the 18-07 PUNJAB NATIONAL BANK sell-20, which the
empty scratch DB cannot cover — against the live holdings (PNB bought 40 on
07-13 per its own note) it is a legitimate sale.

### The 06-2022 `trade_details_*.pdf` files are skipped

`trade_details_CAHXXXXX2L_2413523121.pdf` and
`trade_details_Buyback_CAHXXXXX2L_2415720172.pdf` are a different IIFL
format — a "Capital Market" per-trade table (Sr.No, TM name, client code,
B/S, security, symbol, series, trade no, time, qty, price, traded value),
not the Orders layout. Observations:

- The `Trade No` embeds the date (`2022062751040128` → 2022-06-27), so the
  files are datable, but each row is a single fill while the IIFL Trade
  Listing already covers the same 2022-06-27 NTPC/PENIND roundtrips
  **aggregated** (listing: B4+S2+S2; trade details: B2+B2+S2+S2). Importing
  both levels would double-count the same fills.
- The Buyback file is a single-row subset of the other file.

**Decision:** skip both files. The trades they contain are already in the
database through the Trade Listing import; a per-fill importer would add
row granularity the aggregation-based dedup cannot reconcile. Revisit only
if fill-level history is ever needed.

### Encrypted notes and the password vault

The real archive (`CONTRACT NOTE 5874818698*.pdf`, the 06-2022 pair) is
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

- **~~Real encrypted PDFs still locked.~~ Resolved (Oct 2026):** the
  passwords are stored in the vault and all `CONTRACT NOTE 5874818698*.pdf`
  notes import. The 06-2022 `trade_details_*.pdf` pair is deliberately
  skipped (see above).
- **~~Multi-day Orders workbooks cannot be dated from their contents.~~
  Resolved (Oct 2026):** all 37 real blocks of the `inter (1).xlsx` Orders
  sheet are now dated by matching (order no, trade no) pairs against the
  PDF-derived trade-number map — 34 blocks matched a single note date
  directly (zero mixed blocks); the 3 remaining blocks (15 F&O trades,
  BANKNIFTY/FINNIFTY 11-Jul expiries) exist in no PDF note and were dated
  **2023-07-11** by settlement elimination (P&L settlement 2023126 is the
  only one between 07-06 and 07-13; the FINNIFTY 11-Jul expiry confirms).
  The match also exposed that notes `1.pdf` (2023-08-01) and `2.pdf`
  (2023-08-02) had never been imported — their 5 trades (RELIANCE POWER
  sell-35, VEDANTA sell-13 @ 276.60, COAL INDIA buy-2 @ 235.25, NIFTY
  19300 PE roundtrip) went in together with the 15 workbook-only trades
  (user-approved live import, Oct 2026): 321 transactions, RELIANCE POWER
  position closed, VEDANTA 17→4, COAL INDIA 1→3.
- **06-2022 `CAHPN1222L_20220627.pdf` rejects the stored vault password**
  (decrypt returns 0). The 2022 trades are already in the database via the
  hand-entered snapshot, so the note is skipped until the correct password
  is provided.
- The UI import page (Phase 6) will surface `ImportResult.summary()` and
  the failure list; the audit trail already distinguishes import kinds:
  `GROWW_TRADEBOOK`, `CONTRACT_NOTE_ORDERS`, `IIFL_TRADE_LISTING`,
  `STOCKSLEDGER_PORTFOLIO`, `CONTRACT_NOTE_PDF`.
