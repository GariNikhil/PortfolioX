"""Consent-gated NSE market-data fetching.

Internet rule (project policy): NOTHING touches the network without the
user explicitly granting permission for that specific fetch. fetch_nse_prices()
therefore takes a `consent` callable; the fetcher asks it before every run
and refuses to proceed when it returns False. There is no default consent,
no cached consent, and no code path that reaches the network without it.

NSE blocks scripted access lightly (cookies + headers), so the flow is:
warm-up GET on the homepage to collect cookies, then one quote request per
symbol. The transport is injectable so tests never touch the real network.

Symbol mapping: stored holding symbols are verbose display names
("COAL INDIA LTD", "RELIANCE POWER L"); NSE wants its own trading symbols
("COALINDIA", "RPOWER"). Mapping is mechanical (strip non-alphanumerics),
plus an AMC-prefix rule for fund-house display names ("GROWWAMC -
GROWWGOLD" -> "GROWWGOLD") and an explicit overrides table for the cases
neither can get right. Mutual-fund scheme names are skipped outright -
NSE has no quote for them. Failures are reported per symbol, never
raised per symbol - a delisted name (VEDANT) must not block the other
quotes.
"""

import gzip
import http.cookiejar
import json
import re
import urllib.error
import urllib.request

NSE_HOME = "https://www.nseindia.com"
QUOTE_URL = (
    "https://www.nseindia.com/api/quote-equity?symbol={symbol}"
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://www.nseindia.com/",
}

# Stored symbol -> NSE trading symbol, for cases mechanical mapping
# cannot know (delistings, renames, name-format differences).
SYMBOL_OVERRIDES = {
    # Vedanta delisted from NSE cash market in 2024 (went private);
    # mechanical mapping would still produce VEDANTA and 404.
    "VEDANTA": None,
    "COAL INDIA LTD": "COALINDIA",
    "RELIANCE POWER L": "RPOWER",
    "PUNJ. NATIONLBAK": "PNB",
    "TV18BRDCST": "TV18BRDCST",
}

# Words that mark an AMFI scheme name (a mutual fund, not a listed
# instrument). NSE's quote API has no entry for these - their price
# comes from the MF holding report, not the exchange.
_MF_MARKERS = (
    " FUND ",        # 'HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH'
    "DIRECT PLAN",
    "REGULAR PLAN",
    " DIRECT",
    " IDCW",
)


def is_mutual_fund_scheme(stored):
    """True when the stored name is an MF scheme, not an NSE instrument."""

    text = f" {str(stored or '').strip().upper()} "
    if any(marker in text for marker in _MF_MARKERS):
        return True
    return text.strip().endswith((" GROWTH", " IDCW"))


class NseFetchError(Exception):
    """A quote request failed at the transport level."""


class ConsentRequired(Exception):
    """Raised when a fetch is attempted without explicit user consent."""


def nse_symbol(holding_symbol):
    """Stored holding symbol -> NSE trading symbol, or None if unmappable."""

    text = str(holding_symbol or "").strip().upper()
    if not text:
        return None

    if text in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[text]

    # Fund-house display names carry the AMC as a prefix
    # ('GROWWAMC - GROWWGOLD'); the NSE ticker is the part after it.
    if " - " in text:
        text = text.rsplit(" - ", 1)[1].strip()

    # Mechanical mapping: drop everything that is not a letter or digit.
    return re.sub(r"[^A-Z0-9]", "", text) or None


def fetch_nse_prices(symbols, consent, transport=None):
    """Fetch last-traded prices for `symbols` from NSE.

    consent: zero-argument callable, invoked once per fetch call BEFORE any
        network activity. Returning False (or raising) aborts with
        ConsentRequired - nothing is fetched.
    transport: optional callable (url, headers) -> (status_code, body_text).
        Defaults to urllib; tests inject a fake here so no test ever
        touches the network.

    Returns a result dict:
        {"prices": {stored_symbol: rupee_price},
         "failures": {stored_symbol: reason}}
    keyed by the ORIGINAL stored symbol, so callers can map straight back
    to holdings rows.
    """

    try:
        granted = consent()
    except Exception as error:
        raise ConsentRequired(
            f"NSE fetch refused: the consent check itself failed ({error})"
        ) from error

    if not callable(consent) or not granted:
        raise ConsentRequired(
            "NSE fetch refused: the user did not grant permission for this fetch"
        )

    if transport is None:
        transport = _UrllibTransport()  # one cookie jar for the whole fetch

    # One cookie warm-up per fetch call, not per symbol.
    transport(NSE_HOME, _HEADERS)

    prices, failures = {}, {}
    for stored in symbols:
        # Mutual-fund schemes are not exchange-listed: skip before any
        # request instead of getting a confusing 403 from NSE.
        if is_mutual_fund_scheme(stored):
            failures[stored] = (
                "mutual fund scheme - NSE has no quote; "
                "the price comes from the MF statement"
            )
            continue

        nse_name = nse_symbol(stored)
        if not nse_name:
            failures[stored] = "cannot map to an NSE symbol"
            continue

        try:
            status, body = transport(QUOTE_URL.format(symbol=nse_name), _HEADERS)
        except Exception as error:  # transport-level failure: report, continue
            failures[stored] = f"request failed: {error}"
            continue

        if status != 200:
            failures[stored] = f"NSE returned HTTP {status}"
            continue

        try:
            data = json.loads(body)
        except ValueError:
            failures[stored] = "NSE returned a non-JSON response"
            continue

        price = _extract_price(data)
        if price is None:
            failures[stored] = "no price in the NSE response"
            continue

        prices[stored] = price

    return {"prices": prices, "failures": failures}


def _decode(response):
    """Response body as text, transparently un-gzipping when compressed."""

    raw = response.read()
    if response.headers.get("Content-Encoding", "").lower() == "gzip":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8", "replace")


def _extract_price(data):
    """Last-traded price out of one quote-equity payload, or None."""

    if not isinstance(data, dict):
        return None

    price_info = data.get("priceInfo")
    if isinstance(price_info, dict):
        for key in ("lastPrice", "lastPriceWithCurrency"):
            value = price_info.get(key)
            if isinstance(value, (int, float)):
                return float(value)
            if isinstance(value, str):
                cleaned = re.sub(r"[^\d.]", "", value)
                try:
                    return float(cleaned)
                except ValueError:
                    pass
    return None


class _UrllibTransport:
    """Default transport: real urllib, keeping cookies between requests.

    NSE only serves the quote API to requests carrying the cookies its
    homepage sets, so one instance per fetch call holds a cookie jar:
    the warm-up request populates it and every quote request reuses it.
    A stateless transport (fresh opener per request) gets HTTP 403 even
    for perfectly valid symbols. Only reached with consent.
    """

    def __init__(self):
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar)
        )

    def __call__(self, url, headers):
        request = urllib.request.Request(url, headers=headers)
        try:
            with self._opener.open(request, timeout=15) as response:
                return response.status, _decode(response)
        except urllib.error.HTTPError as error:
            return error.code, _decode(error)
