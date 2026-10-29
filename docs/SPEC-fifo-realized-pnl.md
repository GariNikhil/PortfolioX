# Specification: FIFO realized profit and loss

## Objective

Calculate realized profit or loss for BUY/SELL transactions by matching each
sale to the oldest available purchase lots. This is an accounting calculation
only; it does not classify gains for tax or provide tax advice.

## Scope

### Included

- A pure calculation function in `calculations/fifo.py`.
- Accept database transaction tuples in `transactions` table column order and
  mappings with the same field names.
- Process records in ascending trade-date order, using transaction ID as the
  tie-breaker when present.
- Match lots by ISIN when present; otherwise match by normalized symbol and
  exchange.
- Support partial buy lots and sells spanning multiple buy lots.
- Include purchase brokerage and taxes in lot cost, allocated in proportion to
  quantity consumed from that lot.
- Deduct sell brokerage and taxes from the sale proceeds, allocated in
  proportion to quantity sold.
- Return per-sale match details, including matched quantities, allocated cost,
  net proceeds, and realized P&L.
- Reject unsupported transaction types, malformed/non-finite values, and sells
  exceeding available inventory with a clear `ValueError`.
- Add isolated unit tests using the repository's `unittest` conventions.

### Excluded

- Tax-period, short-term/long-term, or statutory tax classification.
- Unrealized P&L or market-price lookups.
- Database writes, holdings-table updates, report/UI integration, or schema
  changes.
- Corporate actions and non-BUY/SELL transaction types.

## Calculation rules

1. A BUY lot's total cost is `quantity * price + brokerage + taxes`.
2. FIFO consumes the earliest remaining lot(s) for each SELL.
3. When only part of a buy lot is consumed, its original unit cost (including
   allocated buy charges) is retained for the remaining shares.
4. A SELL's net proceeds are `quantity * price - brokerage - taxes`.
5. Allocate that sale's net proceeds across its matched lots in proportion to
   matched quantity; each match's realized P&L is its allocated proceeds minus
   its allocated buy-lot cost.
6. The sum of match P&L for a sale equals that sale's total realized P&L.
7. Never silently treat an oversell as a short position.

## Acceptance criteria

- Multiple BUY lots are consumed oldest-first.
- Partial-lot sells preserve the correct remaining lot cost for later sells.
- One SELL spanning multiple lots returns correct match-level and total P&L.
- Buy and sell charges affect realized P&L according to the rules above.
- Transaction input order does not affect results when dates/IDs establish the
  same chronological ordering.
- Invalid inputs and oversells fail clearly.
- Tests do not access or modify the user's portfolio database.
- README describes FIFO realized P&L while clearly stating that tax
  classification and UI/database integration remain out of scope.

## Verification

Run `python -m unittest discover -v` with the project's virtual environment,
then compile the source with `python -m compileall -q app.py ui database calculations`.

## Open assumption for review

The current schema's `taxes` field is treated as transaction-level charges
(such as trade taxes/levies), not income tax withheld on realized gains. If
that field has a different meaning in the user's data, its allocation rule
must be revised before implementation.