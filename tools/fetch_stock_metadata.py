"""Fetch stock metadata (sector, market cap) for held symbols.

The dashboard's Market Cap / Sector Allocation cards need per-symbol
metadata that the imported broker files never carry. This tool fetches
it once from Yahoo Finance (via yfinance) for the symbols held, and
caches it in the stock_metadata table, so the dashboard works offline
from the cache afterwards. Nothing in the app fetches on its own.

Classification without the network:

- Mutual funds (ELSS / '... FUND DIRECT GROWTH' names), ETFs
  ('GROWWAMC - ...', '... ETF') and F&O contracts carry no stock
  market capitalization; they are labelled locally and stored with a
  NULL market cap so the cap split still covers the whole portfolio.
- Plain stocks need a Yahoo ticker. A built-in map covers common
  Indian large caps whose names do not suggest their ticker
  ('PUNJAB NATIONAL BANK' -> PNB, 'VEDANTA' -> VEDL); anything else
  falls back to a condensed form of the name, and --map SYMBOL=TICKER
  overrides any guess. Tickers get the .NS suffix.

Usage:
    python tools/fetch_stock_metadata.py            # all held symbols
    python tools/fetch_stock_metadata.py --symbol RELIANCE
    python tools/fetch_stock_metadata.py --map "SOME FUND=X.NS"
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from database import db
from database.manager import (
    get_holdings,
    get_stock_metadata,
    set_stock_metadata,
)
from database.schema import ensure_schema
from calculations.fno import normalize_fno_symbol

try:
    import yfinance
except ImportError:
    yfinance = None

# Display names whose NSE ticker is not a simple condensation of the
# name. Everything else falls back to a condensed form of the name.
KNOWN_TICKERS = {
    "PUNJAB NATIONAL BANK": "PNB",
    "VEDANTA": "VEDL",
    "COAL INDIA LTD": "COALINDIA",
    "RELIANCE": "RELIANCE",
}

# rupee thresholds for the approximate SEBI cap split (Large = top-100
# AMFI list; Mid = 101-250; Small = beyond). >= Rs 1,00,000 crore large,
# >= Rs 25,000 crore mid.
LARGE_CAP_MIN = 1_00_000 * 10**7
MID_CAP_MIN = 25_000 * 10**7


def classify_symbol(symbol):
    """Label symbols that are not plain stocks, or None.

    Local heuristics, no network: mutual funds and ETFs by the name
    patterns the broker holding statements produce ('ELSS ... FUND
    DIRECT GROWTH', 'GROWWAMC - ...', '... ETF'), F&O contracts by
    their symbol shape.
    """

    if normalize_fno_symbol(symbol):
        return "Derivative"
    upper = str(symbol).upper()
    if "ELSS" in upper or "FUND" in upper:
        return "Mutual Fund"
    if "ETF" in upper or "AMC" in upper:
        return "ETF"
    return None


def resolve_ticker(symbol, overrides=None):
    """Yahoo ticker for a stock symbol, or None if it is not a stock."""

    if classify_symbol(symbol) is not None:
        return None
    overrides = overrides or {}
    base = overrides.get(symbol) or KNOWN_TICKERS.get(symbol)
    if base is None:
        condensed = "".join(
            token for token in str(symbol).upper().split()
            if token.replace(".", "").isalpha()
        )
        base = condensed[:8] or None
    return f"{base}.NS" if base else None


def held_symbols():
    """Distinct canonical symbols held anywhere in the portfolio."""

    symbols = set()
    for holding in get_holdings():
        symbol = str(holding.get("symbol") or "").strip().upper()
        if symbol:
            symbols.add(symbol)
    return sorted(symbols)


def fetch_metadata(symbol, ticker):
    """(sector, market_cap_rupees) from Yahoo Finance, or None."""

    if yfinance is None:
        raise SystemExit(
            "fetching stock metadata requires the yfinance package "
            "(pip install -r requirements.txt)"
        )
    try:
        info = yfinance.Ticker(ticker).info or {}
    except Exception as error:
        print(f"  fetch failed for {ticker}: {type(error).__name__}: {error}")
        return None

    sector = info.get("sector") or info.get("sectorDisp")
    market_cap = info.get("marketCap")
    if not sector and market_cap is None:
        print(f"  no sector or marketCap returned for {ticker}")
        return None
    return sector, market_cap


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch sector and market cap for held symbols and "
                    "cache them in stock_metadata (explicit network use)."
    )
    parser.add_argument("--symbol",
                        help="fetch just this holding symbol")
    parser.add_argument("--map", action="append", default=[],
                        metavar="SYMBOL=TICKER",
                        help="ticker override for a symbol (repeatable)")
    parser.add_argument("--force", action="store_true",
                        help="refetch symbols that already have metadata")
    parser.add_argument("--db", help="database file (default: data/portfoliox.db)")
    parser.add_argument("--yes", action="store_true",
                        help="allow writing the live data/portfoliox.db")
    args = parser.parse_args(argv)

    if args.db:
        db.DB_PATH = Path(args.db)
    elif not args.yes:
        parser.error(
            "refusing to write the live data/portfoliox.db without --yes "
            "(use --db for a scratch database)"
        )

    ensure_schema()

    overrides = {}
    for entry in args.map:
        if "=" not in entry:
            parser.error(f"--map entry must be SYMBOL=TICKER: {entry}")
        alias, ticker = entry.split("=", 1)
        overrides[alias.strip().upper()] = ticker.strip().upper()

    symbols = [args.symbol.upper()] if args.symbol else held_symbols()
    existing = {row["symbol"] for row in get_stock_metadata()}

    fetched = stored = 0
    for symbol in symbols:
        if not args.force and symbol in existing:
            print(f"  cached: {symbol}")
            continue
        label = classify_symbol(symbol)
        if label is not None:
            set_stock_metadata(symbol, sector=label, market_cap=None,
                               source="local_classification")
            stored += 1
            print(f"  classified locally: {symbol} -> {label}")
            continue
        ticker = resolve_ticker(symbol, overrides)
        if ticker is None:
            print(f"  no ticker for {symbol}; pass --map to supply one")
            continue
        print(f"  fetching {symbol} as {ticker} ...")
        fetched_result = fetch_metadata(symbol, ticker)
        if fetched_result is None:
            continue
        sector, market_cap = fetched_result
        set_stock_metadata(symbol, sector=sector, market_cap=market_cap,
                           source="yahoo")
        stored += 1
        fetched += 1
        print(f"  stored: {symbol} -> {sector}, "
              f"market cap {market_cap / 1e7:,.0f} cr")

    print(f"\ndone: {fetched} fetched, {stored} stored")


if __name__ == "__main__":
    main()
