# PortfolioX - Holdings Calculator Documentation (Phase 4)

## Moving Weighted-Average Cost Algorithm

### Overview
The holdings calculator implements a moving weighted-average cost algorithm for calculating portfolio positions after trades are imported.

### Algorithm Logic
1. When a new "Buy" trade is imported:
   - Calculate new weighted average cost: `(old_qty * old_avg_cost + new_qty * new_price) / (old_qty + new_qty)`
   - Update total shares quantity: `old_qty + new_qty`

2. When a "Sell" trade is imported:
   - Reduce quantity by the sold amount
   - Maintain the weighted average cost for remaining shares
   - Calculate realized P&L if needed

### Key Functions
- `calculate_holdings(transactions)`: Main entry point
- `update_average_cost()`: Update cost basis after new trades
- `calculate_realized_pl()`: Calculate profit/loss on sales

### Error Handling
- `ValueError`: Raised when invalid price or quantity data is encountered
- Missing required fields trigger validation errors
- Idempotent imports skip duplicate transactions gracefully

### Output
- Current portfolio holdings with average cost
- Total portfolio value
- Per-symbol breakdown
- Transaction history with running totals