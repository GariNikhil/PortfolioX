# Income tax estimate settings

## Overview

Add settings that define how PortfolioX estimates income tax on SELL activity.
The setting is for informational estimates only. PortfolioX must never persist
the estimate into transaction records or change broker-reported charges.

## User value

Users can choose an estimate method that matches their workflow and review a
tax estimate without corrupting their transaction ledger or confusing income
tax estimates with brokerage, STT, or other transaction charges.

## Functional requirements (EARS)

- When the user opens Settings, the system shall show an income-tax estimate
  mode with `Fixed amount` and `Percentage` choices.
- When `Fixed amount` is selected, the system shall accept a non-negative
  currency amount and apply it only to SELL transactions.
- When `Percentage` is selected, the system shall accept a non-negative rate
  and a basis of either trade value or realized gain.
- When the percentage basis is trade value, the system shall calculate the
  estimate from `quantity × sale price` for the SELL transaction.
- When the percentage basis is realized gain, the system shall calculate the
  estimate from that SELL's FIFO-matched realized gain, with no negative tax
  estimate for a realized loss.
- When income-tax estimation is enabled, the system shall calculate an
  estimate for SELL transactions according to the selected mode and basis.
- When income-tax estimation is disabled, the system shall not calculate or
  display an income-tax estimate.
- The system shall keep income-tax estimates separate from transaction
  brokerage and taxes fields.
- The system shall not save an income-tax estimate as a transaction, tax, or
  other ledger entry.
- When a setting value is invalid or incomplete, the system shall explain the
  validation error and shall not apply the invalid setting.
- When the user saves valid settings, the system shall retain them across
  application restarts.

## Non-functional requirements

- Estimates are informational only and must be labeled as estimates, not tax
  owed or tax advice.
- The calculation must be deterministic for a given transaction and settings
  snapshot.
- Settings and estimates must not require network access.
- Fixed currency values and percentage rates must be validated as finite and
  non-negative.
- Persist only the user's configuration; do not create or mutate financial
  ledger records to represent an estimate.

## Acceptance criteria (Given/When/Then)

1. **Fixed amount applies to sells only**
   - Given estimation is enabled in fixed-amount mode with amount `25`,
   - When a SELL estimate is calculated,
   - Then its income-tax estimate is `25`, and BUY transactions receive no
     income-tax estimate.
2. **Percentage of trade value**
   - Given percentage mode is enabled at `1.5%` with trade-value basis,
   - When a SELL of 10 units at 100 per unit is estimated,
   - Then the income-tax estimate is 15.
3. **Percentage of realized gain**
   - Given percentage mode is enabled at `10%` with realized-gain basis,
   - When FIFO matching returns a gain of 200,
   - Then the income-tax estimate is 20.
4. **No estimate on a loss**
   - Given percentage mode uses realized-gain basis,
   - When FIFO matching returns a loss or zero gain,
   - Then the income-tax estimate is zero.
5. **Ledger remains unchanged**
   - Given an income-tax estimate is calculated for a SELL,
   - When the estimate is returned or displayed,
   - Then the transaction's brokerage, taxes, and net amount remain unchanged
     and no new ledger entry is created.
6. **Disabled state**
   - Given income-tax estimation is disabled,
   - When a SELL is processed,
   - Then no income-tax estimate is produced.
7. **Invalid configuration**
   - Given a rate or fixed amount is negative, non-finite, or missing when
     required,
   - When the user attempts to save,
   - Then the system rejects the configuration with a clear validation error.
8. **Persistence**
   - Given valid settings are saved,
   - When PortfolioX restarts,
   - Then the saved mode, amount/rate, basis, and enabled state are restored.

## Error handling

| Condition | Expected behavior |
|---|---|
| Negative, non-numeric, NaN, or infinite amount/rate | Reject save and identify the invalid field |
| Percentage basis missing in percentage mode | Reject save and request a basis selection |
| Realized-gain basis requested before FIFO result exists | Do not guess; report that the estimate is unavailable |
| Settings storage cannot be read or written | Keep ledger untouched and show a clear settings error |
| BUY transaction passed to the estimate calculation | Return no income-tax estimate |

## Boundaries

### Always

- Keep income-tax estimates separate from broker-reported charges.
- Treat estimate outputs as informational and label them clearly.
- Cover fixed mode, both percentage bases, losses, invalid settings, and
  non-mutation of transaction records with tests.

### Ask first

- Adding jurisdiction-specific tax rates, exemptions, holding-period rules,
  surcharge, cess, or statutory reporting.
- Automatically writing any tax estimate into the transaction ledger.
- Changing the meaning or storage of the existing transaction `taxes` field.

### Never

- Present an estimate as a confirmed tax liability or professional tax advice.
- Silently mutate recorded transactions when settings change.

## Implementation checklist

- [ ] Add a validated settings model and local persistence using existing
      project conventions.
- [ ] Add pure fixed-amount and percentage estimate calculations.
- [ ] Connect realized-gain basis to FIFO sale results without ledger writes.
- [ ] Add Settings UI controls for enabled state, mode, value, and percentage
      basis.
- [ ] Add unit tests for formulas, validation, persistence, and ledger
      non-mutation.
- [ ] Update README with the estimate-only behavior and limitations.
- [ ] Run the complete unittest suite, compilation check, and UI import check.

## Dependencies and assumptions

- Realized-gain percentage mode depends on FIFO realized P&L results.
- The current project has no settings persistence layer; implementation should
  inspect the existing settings-page and storage conventions before choosing
  one.
- The existing transaction `taxes` field remains reserved for recorded
  transaction charges and is never used to store this estimate.