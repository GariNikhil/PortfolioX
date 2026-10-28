# PortfolioX — Core Data Model

This is a logical model; adapt field types and naming to the existing codebase.

## Core entities
- `Account`: user-defined broker/account label and base currency.
- `Security`: symbol, company name, exchange, ISIN, instrument type, sector/industry when known.
- `Transaction`: immutable trade/cash-flow event with date, type, quantity, price, fees, taxes, currency, source, and external reference.
- `CorporateAction`: split, bonus, rights, merger/demerger, or other supported event.
- `Dividend`: security, relevant dates, gross amount, deductions, net amount, source.
- `PriceObservation`: security, price, currency, source, timestamp, and freshness/status.
- `Position`: derived quantity and cost basis at a point in time.
- `PortfolioSnapshot`: dated totals and allocation, with calculation and price provenance.
- `WatchlistItem`: security, priority, notes, desired entry, target, stop, review date.
- `InvestmentThesis`: rationale, catalysts, risks, invalidation conditions, review date.
- `Alert`: user-configured condition, status, trigger time, and source.
- `ImportBatch`: source file metadata, mapping, accepted/rejected rows, duplicate decisions, and confirmation status.
- `AuditEvent`: actor/action/time/object reference and safe metadata.

## Transaction fields (logical)
```yaml
id: unique-id
account_id: account-id
security_id: security-id-or-null
trade_date: YYYY-MM-DD
type: BUY | SELL | DEPOSIT | WITHDRAWAL | DIVIDEND | FEE | TAX | CORPORATE_ACTION | OTHER
quantity: decimal-or-null
price: decimal-or-null
currency: INR
brokerage: decimal
taxes: decimal
other_charges: decimal
external_reference: string-or-null
source: MANUAL | IMPORT | ADJUSTMENT
created_at: timestamp
notes: string
```

## Data rules
- Store money and quantities with suitable decimal precision.
- Use stable IDs; do not identify a security solely by display name when ISIN/exchange data is available.
- Preserve original import metadata and source references.
- Make derived positions reproducible from ledger + corporate actions.
- Define treatment of fees and taxes per transaction type.
- Represent missing price as missing, not as zero.
- Track timestamps and currencies explicitly.
- Avoid destructive in-place corrections; use audited correction/reversal workflows.

## Important calculation tests
- Multiple buys at different prices.
- Partial and full sells.
- Fees and taxes.
- Split and bonus events.
- Dividend with gross/net amounts.
- Duplicate import.
- Missing/stale price.
- Currency mismatch.
- Empty portfolio and zero cost basis.
- XIRR with irregular flows, invalid dates, and non-convergence.
