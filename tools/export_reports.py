"""Export portfolio reports to files (CSV + text summary).

Writes three files into --out (default: ./reports):
- holdings.csv    every open position (machine-readable)
- transactions.csv  every recorded trade, newest first
- portfolio.txt   human-readable summary with Indian-grouped rupees

``--db PATH`` points the run at a scratch database; without it the tool
reads the live data/portfoliox.db (read-only - exports never write).
"""

import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(PROJECT_ROOT))

from database import db
from database.manager import get_holdings, get_portfolio_summary, get_transactions
from reports.writer import holdings_csv, portfolio_text_report, transactions_csv


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Export holdings/transactions reports as CSV and text."
    )
    parser.add_argument(
        "--out",
        default=str(PROJECT_ROOT / "reports_out"),
        help="output directory (default: ./reports_out)",
    )
    parser.add_argument(
        "--db",
        help="database file to read (default: data/portfoliox.db)",
    )
    args = parser.parse_args(argv)

    if args.db:
        db.DB_PATH = Path(args.db)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = get_portfolio_summary()
    holdings = get_holdings()
    transactions = get_transactions()

    written = {
        "holdings.csv": holdings_csv(holdings),
        "transactions.csv": transactions_csv(transactions),
        "portfolio.txt": portfolio_text_report(summary, holdings),
    }
    for name, content in written.items():
        path = out_dir / name
        path.write_text(content, encoding="utf-8")
        print(f"wrote {path}")

    print(
        f"\n{summary['total_holdings']} holdings, "
        f"{summary['total_transactions']} transactions exported."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
