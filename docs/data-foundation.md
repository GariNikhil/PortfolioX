# Data Foundation Decisions (Phase 2.5)

Pre-importer decisions that the Groww import system must respect. Recorded so
the importer is built against a stable contract instead of rediscovering these
rules later. Review record: [`code-review-phase1.md`](code-review-phase1.md).

## 1. Money is stored as INTEGER paise

All amount columns (`price`, `brokerage`, `taxes`, `net_amount`,
`average_price`, `invested_amount`, `market_value`, `profit_loss`,
dividend `amount`) are `INTEGER` paise, 1 rupee = 100 paise. Sums are exact
floats sums are not.

- `database.manager` converts rupees to paise on write (`_to_paise`, round to
  nearest paise) and back to rupees on read (exact two-decimal rounding).
- Quantity stays `REAL`: fractional share counts are legitimate.
- Everything downstream of the manager (calculator, reports, imports) works
  in rupees; only the storage layer sees paise.

## 2. net_amount is side-aware

A broker’s transaction data has two different meanings for “net”:

- **BUY** — what left your account: `quantity*price + brokerage + taxes`
- **SELL** — what reached your account: `quantity*price - brokerage - taxes`

`manager._net_amount_paise()` computes this per side and refuses any
transaction type other than BUY or SELL. Dividend-type movements belong in
the `dividends` table, never in `transactions`.

## 3. holdings is a rebuildable cache

The `holdings` table is derived state, never a source of truth. When any
transaction changes (add, edit, delete), call `rebuild_holdings()`:

- position math comes from `calculations.holdings.calculate_holdings()`
- fully sold symbols are removed from the cache
- `market_value` and `profit_loss` reset to zero (they need market prices,
  restored when the pricing phase lands)
- correcting a mistake is allowed: `delete_transaction(id)` + rebuild

## 4. Database constraints guard bad data

`transactions.symbol`, `trade_date`, `transaction_type`, `quantity`,
`price` etc. are `NOT NULL`; `transaction_type` is `CHECK`ed to
BUY/SELL; money columns are `CHECK`ed non-negative. The v1→v2 migration
(`ensure_schema()`) fails loudly on ambiguous rows rather than altering
financial values. `ensure_schema()` is idempotent and runs at app startup.

## 5. Dates are stored as ISO-8601 `YYYY-MM-DD` TEXT

All ordering (`ORDER BY trade_date`) and chronological position math depend
on lexicographic ISO order. **The Groww importer must normalize every
trade/broker date to ISO-8601 before insert** — Groww tradebooks and contract
notes use display formats (e.g. `07 Oct 2024`, `06-2022` folder styles,
DD-MM-YYYY). Non-ISO dates must fail the row, never be written raw.
