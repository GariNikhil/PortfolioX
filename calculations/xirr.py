"""Money-weighted annual return (XIRR) from dated cashflows.

XIRR answers "what annual rate turns these cashflows into my final
value" — the number a mutual-fund statement shows. Cashflows are signed
from the investor's perspective: money out (buys) negative, money in
(sells, terminal value) positive.
"""

from datetime import date, datetime


def xirr(cashflows, guess=0.1):
    """Annualized XIRR for [(date, amount), ...], or None when unsolvable.

    Solves sum(amount_i * (1 + rate) ** -t_i) == 0, where t_i is each
    cashflow's year fraction from the earliest date, by Newton-Raphson
    with a bisection fallback. Returns None when the flows do not change
    sign (nothing invested or nothing returned) or the solver fails —
    callers show a dash instead of a misleading number.
    """

    flows = sorted(
        (
            (_as_date(day), float(amount))
            for day, amount in cashflows
        ),
        key=lambda pair: pair[0],
    )
    if len(flows) < 2:
        return None

    origin = flows[0][0]
    terms = [
        (amount, (day - origin).days / 365.0)
        for day, amount in flows
    ]
    if not (any(amount < 0 for amount, _ in terms)
            and any(amount > 0 for amount, _ in terms)):
        return None  # all outflows or all inflows: no rate exists

    def npv(rate):
        return sum(amount * (1.0 + rate) ** -years
                   for amount, years in terms)

    def dnpv(rate):
        return sum(
            -years * amount * (1.0 + rate) ** (-years - 1.0)
            for amount, years in terms
        )

    # Newton-Raphson from the guess; fall back to bisection when the
    # derivative dies or the iterate escapes the meaningful domain.
    rate = guess
    for _ in range(100):
        if rate <= -1.0:
            break
        value = npv(rate)
        if abs(value) < 1e-9:
            return rate
        slope = dnpv(rate)
        if slope == 0:
            break
        next_rate = rate - value / slope
        if next_rate <= -1.0:
            break
        if abs(next_rate - rate) < 1e-12:
            return next_rate
        rate = next_rate

    low, high = -0.9999, 10.0
    low_value, high_value = npv(low), npv(high)
    if low_value * high_value > 0:
        return None
    for _ in range(200):
        middle = (low + high) / 2.0
        middle_value = npv(middle)
        if abs(middle_value) < 1e-9:
            return middle
        if low_value * middle_value < 0:
            high, high_value = middle, middle_value
        else:
            low, low_value = middle, middle_value
    return (low + high) / 2.0


def xirr_cashflows(transactions, market_value, valuation_date=None):
    """Cashflows for the dashboard XIRR card from transaction rows.

    Buys are money out (negative net amount), sells money in, and the
    current market value is the terminal inflow at the valuation date
    (today). Pass market_value=0 to signal "no prices yet" — the caller
    skips the XIRR computation in that case.
    """

    flows = []
    for row in transactions:
        net = float(row["net_amount"] or 0)
        if not net:
            continue
        sign = -1.0 if str(row["transaction_type"]).upper() == "BUY" else 1.0
        day = _as_date(row["trade_date"])
        flows.append((day, sign * net))

    if market_value:
        flows.append((
            valuation_date or date.today(),
            float(market_value),
        ))
    return flows


def _as_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    return date(int(text[:4]), int(text[5:7]), int(text[8:10]))
