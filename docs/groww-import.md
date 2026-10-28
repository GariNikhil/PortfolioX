# PortfolioX - Groww Import System Documentation

## Phase 3: Groww Tradebook Import

### Overview
The Groww Import System (Phase 3) enables PortfolioX to parse Groww tradebook CSV/XLSX files and integrate the parsed data into the existing SQLite database layer established in Phase 2.

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
- pandas library
- openpyxl or xlrd (for XLSX reading)
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