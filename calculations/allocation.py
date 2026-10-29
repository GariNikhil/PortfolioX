"""Portfolio allocation and tax-period summaries (pure functions).

These feed the dashboard's Portfolio Analysis section and the Tax page.
They take plain dict rows shaped like database.manager's getters return
(amounts in rupees) so they are unit-testable without a database.
"""

from collections import defaultdict

from calculations.fno import normalize_fno_symbol


def asset_allocation(holdings):
    """Split holdings into asset classes by invested amount (rupees).

    Equity vs F&O for now: a holding whose symbol parses as an F&O
    contract counts as F&O, everything else as Equity. Mutual funds,
    bonds and US stocks arrive with their own importers and will join
    the split then. Returns (label, amount) pairs sorted by amount
    descending, zero classes omitted.
    """

    amounts = defaultdict(float)
    for holding in holdings:
        symbol = str(holding.get("symbol") or "")
        label = "F&O" if normalize_fno_symbol(symbol) else "Equity"
        amounts[label] += float(holding.get("invested_amount") or 0)

    return sorted(
        ((label, amount) for label, amount in amounts.items() if amount),
        key=lambda pair: pair[1],
        reverse=True,
    )


# Market-cap category thresholds in rupees. SEBI's official split is
# rank-based (AMFI's top-100 / 101-250 lists); these absolute cutoffs
# are the common approximation and only shift at the edges.
LARGE_CAP_MIN = 1_00_000 * 10**7   # >= Rs 1,00,000 crore
MID_CAP_MIN = 25_000 * 10**7       # >= Rs 25,000 crore


def market_cap_category(market_cap):
    """Market cap in rupees -> 'Large Cap' / 'Mid Cap' / 'Small Cap'."""

    if market_cap >= LARGE_CAP_MIN:
        return "Large Cap"
    if market_cap >= MID_CAP_MIN:
        return "Mid Cap"
    return "Small Cap"


def metadata_allocation(holdings, metadata, classify):
    """Split holdings by a metadata-derived label, by invested amount.

    metadata maps symbol -> metadata rows (sector / market_cap);
    classify(symbol, row) returns the label for one holding. Symbols
    with no metadata row get the classify(None, None) fallback label
    ('Unclassified' in practice). Returns (label, amount) pairs sorted
    by amount descending, zero amounts omitted.
    """

    amounts = defaultdict(float)
    for holding in holdings:
        symbol = str(holding.get("symbol") or "").upper()
        row = metadata.get(symbol)
        amounts[classify(symbol, row)] += float(
            holding.get("invested_amount") or 0
        )

    return sorted(
        ((label, amount) for label, amount in amounts.items() if amount),
        key=lambda pair: pair[1],
        reverse=True,
    )


def split_holdings_by_class(holdings):
    """Split holdings into (stocks, funds) tables.

    Funds are locally classified Mutual Fund symbols (the name
    heuristics in fund_or_fno_label); everything else - plain stocks,
    ETFs and F&O contracts - stays in the stocks table. Returns two
    lists in the input order.
    """

    stocks, funds = [], []
    for holding in holdings:
        label = fund_or_fno_label(str(holding.get("symbol") or ""))
        (funds if label == "Mutual Fund" else stocks).append(holding)
    return stocks, funds


def sector_allocation(holdings, metadata):
    """Sector split by invested amount (rupees).

    Funds and ETFs carry their own sector label ('Mutual Fund' / 'ETF')
    from the metadata; stocks carry their fetched sector; symbols with
    no metadata land in 'Unclassified'.
    """

    return metadata_allocation(holdings, metadata, _sector_label)


def _sector_label(symbol, row):
    if row is None:
        return fund_or_fno_label(symbol) or "Unclassified"
    return row["sector"] or "Unclassified"


def market_cap_allocation(holdings, metadata):
    """Market-cap-category split by invested amount (rupees).

    Stocks land in Large / Mid / Small Cap by their cached market cap
    (approximate SEBI thresholds); funds / ETFs / derivatives have no
    market cap and keep their own label so the split still sums to the
    portfolio.
    """

    def classify(symbol, row):
        if row is not None and row["market_cap"] is not None:
            return market_cap_category(row["market_cap"])
        return fund_or_fno_label(symbol) or "Unclassified"

    return metadata_allocation(holdings, metadata, classify)


def fund_or_fno_label(symbol):
    """Label for symbols that are not plain stocks, or None.

    Local heuristics, no metadata needed: F&O contracts by their symbol
    shape, mutual funds and ETFs by name patterns common in broker
    holding statements ('ELSS ... FUND DIRECT GROWTH', 'GROWWAMC - ...').
    """

    if normalize_fno_symbol(symbol):
        return "F&O"
    upper = symbol.upper()
    if "ELSS" in upper or " FUND " in f" {upper} " or "FUND DIRECT" in upper:
        return "Mutual Fund"
    if "ETF" in upper or "AMC" in upper:
        return "ETF"
    return None


def financial_year_of(trade_date):
    """ISO date 'YYYY-MM-DD' -> the FY label it falls in (April-March).

    FY 2023-24 covers 2023-04-01 .. 2024-03-31.
    """

    year, month = int(trade_date[:4]), int(trade_date[5:7])
    start = year if month >= 4 else year - 1
    return f"FY {start}-{(start + 1) % 100:02d}"


def financial_year_summary(transactions):
    """Per-FY trading summary, newest year first.

    Returns (label, stats) pairs where stats is a dict with buy_count,
    sell_count, buy_turnover and sell_turnover (rupees, gross qty*price
    before charges — the turnover tax reports start from).
    """

    years = {}
    for row in transactions:
        label = financial_year_of(str(row["trade_date"]))
        stats = years.setdefault(label, {
            "buy_count": 0, "sell_count": 0,
            "buy_turnover": 0.0, "sell_turnover": 0.0,
        })
        quantity = float(row["quantity"] or 0)
        gross = quantity * float(row["price"] or 0)
        if str(row["transaction_type"]).upper() == "BUY":
            stats["buy_count"] += 1
            stats["buy_turnover"] += gross
        else:
            stats["sell_count"] += 1
            stats["sell_turnover"] += gross

    return sorted(years.items(), reverse=True)
