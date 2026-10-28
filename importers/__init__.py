"""Importers convert broker files into PortfolioX transactions.

Phase 3 covers the Groww tradebook (CSV and XLSX). Every importer obeys the
data-foundation contract in docs/data-foundation.md: dates are normalized to
ISO-8601 before insert, money is handed to database.manager as rupees (stored
as exact INTEGER paise), and batches go in atomically through
database.manager.add_transactions.
"""
