"""Consent-gated Yahoo Finance price fetching - fallback for NSE.

Internet rule (project policy): NOTHING touches the network without the
user explicitly granting permission for that specific fetch.
fetch_yahoo_prices() takes a `consent` callable exactly like the NSE
fetcher; the caller asks before every run and nothing is fetched without
it.

Why a fallback: NSE sits behind aggressive bot protection that
intermittently 403s scripted requests (whole sessions, valid symbols
included). Yahoo Finance serves the same NSE-listed instruments under a
`.NS` suffix and tolerates scripted access, so the Prices page retries
there whatever NSE could not fetch. Mutual-fund scheme names are not
listed on either - they are excluded by the caller (their price comes
from the MF holding report).

The transport is injectable so tests never touch the real network.
"""

import json
import urllib.error
import urllib.request

from market_data.nse import nse_symbol

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}


class YahooFetchError(Exception):
    """A quote request failed at the transport level."""


def yahoo_symbol(stored):
    """Stored holding symbol -> Yahoo symbol ('<NSE ticker>.NS'), or None."""

    nse_name = nse_symbol(stored)
    return f"{nse_name}.NS" if nse_name else None


def fetch_yahoo_prices(symbols, consent, transport=None):
    """Fetch last-traded prices for `symbols` from Yahoo Finance.

    Same contract as fetch_nse_prices: consent is invoked BEFORE any
    network activity and a falsy result (or an exception) aborts with
    YahooFetchError. transport is an optional callable
    (url, headers) -> (status_code, body_text); tests inject a fake.

    Returns {"prices": {stored_symbol: rupee_price},
             "failures": {stored_symbol: reason}} keyed by the ORIGINAL
    stored symbol.
    """

    try:
        granted = consent()
    except Exception as error:
        raise YahooFetchError(
            f"Yahoo fetch refused: the consent check itself failed ({error})"
        ) from error

    if not callable(consent) or not granted:
        raise YahooFetchError(
            "Yahoo fetch refused: the user did not grant permission for "
            "this fetch"
        )

    if transport is None:
        transport = _urllib_transport

    prices, failures = {}, {}
    for stored in symbols:
        yahoo_name = yahoo_symbol(stored)
        if not yahoo_name:
            failures[stored] = "cannot map to a Yahoo symbol"
            continue

        try:
            status, body = transport(YAHOO_URL.format(symbol=yahoo_name), _HEADERS)
        except Exception as error:  # transport-level failure: report, continue
            failures[stored] = f"request failed: {error}"
            continue

        if status != 200:
            failures[stored] = f"Yahoo returned HTTP {status}"
            continue

        try:
            data = json.loads(body)
        except ValueError:
            failures[stored] = "Yahoo returned a non-JSON response"
            continue

        price = _extract_price(data)
        if price is None:
            failures[stored] = "no price in the Yahoo response"
            continue

        prices[stored] = price

    return {"prices": prices, "failures": failures}


def _extract_price(data):
    """Regular market price out of one chart payload, or None."""

    if not isinstance(data, dict):
        return None

    result = data.get("chart", {}).get("result")
    if not isinstance(result, list) or not result:
        return None

    meta = result[0].get("meta")
    if isinstance(meta, dict):
        value = meta.get("regularMarketPrice")
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _urllib_transport(url, headers):
    """Default transport: real urllib. Only reached with consent."""

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
