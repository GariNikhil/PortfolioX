# PortfolioX - Phase 3 Product Requirements Document (PRD)

## Document Information

- **Document Name**: PRD.md
- **Feature**: Groww Import System (Phase 3)
- **Status**: Draft
- **Created**: 2024

## 1. Overview

The Groww Import System (Phase 3) enables PortfolioX to parse Groww tradebook CSV/XLSX files and integrate the parsed data into the existing SQLite database layer established in Phase 2. This system will allow users to import their transaction history from Groww, a popular Indian brokerage platform.
## 2. Goals and Non-Goals

### Goals
- Parse Groww tradebook CSV format
- Parse Groww tradebook XLSX format
- Validate imported data against database schema
- Map Groww columns to PortfolioX transactions table schema
## 3. User Stories

### US-3.1: Import Groww CSV Tradebook
- As a user, I want to upload a Groww tradebook CSV file
- So that my transaction history can be imported into PortfolioX
- Acceptance Criteria:
  - CSV file is selected via file dialog
## 4. Requirements

### 4.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-3.1 | Parse Groww CSV tradebook format with columns: Date, Symbol, Quantity, Price, Buy/Sell, Trade Type, Status, Product, Delivery/Intraday | High |
| FR-3.2 | Parse Groww XLSX tradebook format with same columns as CSV | High |
### 4.2 Database Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| DR-3.1 | Import data into transactions table | High |
| DR-3.2 | Transaction table schema: id, symbol, qty, price, buy_sell, trade_type, status, product, date, timestamp | High |
| DR-3.3 | Idempotent import: skip rows where transaction already exists (based on symbol + date + qty) | High |
| DR-3.4 | Maintain data integrity with existing database | High |
### 4.3 Data Mapping Groww → Database

| Groww Column | Database Field | Type | Notes |
|--------------|----------------|------|-------|
| Date | date | TEXT (YYYY-MM-DD) | Convert from DD-MM-YYYY format |
| Symbol | symbol | TEXT | Stock symbol/name |
| Quantity | qty | REAL | Number of shares |
### 4.4 Validation Rules

| Rule | Description |
|------|-------------|
| RQ-3.1 | Date must be a valid date in supported formats |
| RQ-3.2 | Symbol must not be empty and should match stock symbol pattern |
| RQ-3.3 | Quantity must be a positive number |
### 4.5 Error Handling

| Error Type | Description | Handling |
|------------|-------------|----------|
| Invalid Date Format | Date cannot be parsed | Skip row, add to failures list |
| Missing Required Field | Required column is empty | Skip row, add to failures list |
| Invalid Quantity | Quantity is not a valid positive number | Skip row, add to failures list |
| Invalid Price | Price is not a valid positive number | Skip row, add to failures list |
## 5. Acceptance Criteria

### MVP Acceptance Criteria
- [ ] Groww CSV tradebook can be parsed and imported to database
- [ ] Groww XLSX tradebook can be parsed and imported to database
- [ ] Required field validation works (date, symbol, quantity, price, trade type)
- [ ] Idempotent import: re-importing same file skips already-imported transactions
- [ ] Import summary report shows success/failure counts
## 6. Dependencies

### External Dependencies
- Python 3.9+
- pandas library (for DataFrame operations)
- openpyxl or xlrd (for XLSX reading)
- Existing database layer (Phase 2) with transactions table

## 7. Out of Scope (Future Phases)

- CustomTkinter import UI (Phase 5)
- Multiple broker platform support (Phase 9)
- FIFO profit/loss calculations (Phase 8)
- Data export functionality (Phase 6)
### Internal Dependencies
- database/schema.py - table definitions
- database/manager.py - CRUD operations
- calculations/holdings.py - holdings calculator (for post-import validation)
- [ ] Error messages are user-friendly

### Stretch Acceptance Criteria
- [ ] Support for all Groww tradebook column variations
- [ ] Multiple date format handling without user intervention
- [ ] XLSX files with multiple sheets
- [ ] Preview of data before import confirmation
| Duplicate Transaction | Transaction already exists in database | Skip row idempotently, no error |
| RQ-3.4 | Price must be a positive number |
| RQ-3.5 | Trade Type must be "Intraday" or "Delivery" |
| RQ-3.6 | Buy/Sell must be "Buy" or "Sell" |
| Price | price | REAL | Price per share |
| Buy/Sell | buy_sell | TEXT | "Buy" or "Sell" |
| Trade Type | trade_type | TEXT | "Intraday" or "Delivery" |
| Status | status | TEXT | "Square off" or "Open" |
| Product | product | TEXT | "Equity" or "F&O" |
| FR-3.3 | Validate required fields: Date, Symbol, Quantity, Price, Trade Type | High |
| FR-3.4 | Map Groww column names to database schema fields | High |
| FR-3.5 | Check for duplicate transactions and skip idempotently | High |
| FR-3.6 | Handle multiple date formats (DD-MM-YYYY, MM/DD/YYYY, YYYY-MM-DD) | Medium |
| FR-3.7 | Convert numeric fields (Quantity, Price) to appropriate types | Medium |
| FR-3.8 | Generate import summary report | Medium |
| FR-3.9 | Provide user-friendly error messages for invalid data | Medium |
| FR-3.10 | Support both absolute and relative file paths | Low |
  - File is parsed and validated
  - Transactions are stored in the database
  - Already-imported transactions are skipped

### US-3.2: Import Groww XLSX Tradebook
- As a user, I want to upload a Groww tradebook XLSX file
- So that my transaction history can be imported into PortfolioX
- Acceptance Criteria:
  - XLSX file is selected via file dialog
  - File is parsed and validated
  - Transactions are stored in the database
  - Already-imported transactions are skipped

### US-3.3: View Import Results
- As a user, I want to see import results
- so that I can verify which transactions were successfully imported and which failed
- Acceptance Criteria:
  - Success count is displayed
  - Failure count is displayed
  - List of failed row numbers/reasons is shown
- Implement idempotent import logic (skip already-imported transactions)
- Generate import result reports (successes, failures, warnings)

### Non-Goals (for Phase 3)
- CustomTkinter UI for import (Phase 5)
- XLSX format with complex formatting
- Multiple broker platform support (Phase 9)
- Advanced holdings calculations (Phase 8)