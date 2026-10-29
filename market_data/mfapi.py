"""Consent-gated mutual-fund NAV fetching via mfapi.in.

Internet rule (project policy): NOTHING touches the network without the
user explicitly granting permission for that specific fetch.
fetch_mf_navs() takes a `consent` callable exactly like the NSE and
Yahoo fetchers; the caller asks before every run and nothing is fetched
without it.

Why mfapi.in: mutual-fund schemes are not exchange-listed, so neither
NSE nor Yahoo has a quote for them. mfapi.in is a free, no-auth mirror
of AMFI's official NAV data. It needs two requests per scheme:

    GET /mf/search?q=<words>   ->  [{"schemeCode": 119060, "schemeName": "..."}]
    GET /mf/{schemeCode}       ->  {"meta": {...}, "data": [{"date", "nav"}, ...]}

The codes are mfapi's own (NOT AMFI numbers), so the code always comes
from the search result, never from the stored name. The `data` rows are
newest-first, so data[0] carries the latest NAV.

Scheme matching is local: mfapi's search does substring matching, so
the query drops generic words (FUND, DIRECT PLAN, GROWTH...) and the
candidates are then scored by token overlap. The fund family's first
token must anchor the match and at least half of the stored tokens
must appear - generic words must never match unrelated schemes. Among
survivors, fewer extra tokens wins ties, so a stored "DIRECT ... GROWTH"
prefers the Direct Plan over the Regular Plan. The transport is
injectable so tests never touch the real network.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

MF_SEARCH_URL = "https://api.mfapi.in/mf/search?q={query}"
MF_SCHEME_URL = "https://api.mfapi.in/mf/{scheme_code}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
}

# Words that carry no identifying power in a scheme name; dropping them
# from the search query avoids substring misses against mfapi's
# punctuated names ('... Fund - Direct Plan - Growth Option').
_GENERIC_TOKENS = {"FUND", "PLAN", "DIRECT", "REGULAR", "GROWTH", "IDCW", "OPTION"}


class MfapiFetchError(Exception):
    """The fetch failed at the transport level or was refused."""


def fetch_mf_navs(schemes, consent, transport=None):
    """Fetch the latest NAV for mutual-fund `schemes` from mfapi.in.

    Same contract as fetch_nse_prices / fetch_yahoo_prices: consent is
    invoked BEFORE any network activity and a falsy result (or an
    exception) aborts with MfapiFetchError. transport is an optional
    callable (url, headers) -> (status_code, body_text); tests inject
    a fake.

    Returns {"prices": {stored_scheme: nav}, "failures": {stored_scheme:
    reason}} keyed by the ORIGINAL stored scheme name.
    """

    try:
        granted = consent()
    except Exception as error:
        raise MfapiFetchError(
            f"mfapi fetch refused: the consent check itself failed ({error})"
        ) from error

    if not callable(consent) or not granted:
        raise MfapiFetchError(
            "mfapi fetch refused: the user did not grant permission for "
            "this fetch"
        )

    if transport is None:
        transport = _urllib_transport

    prices, failures = {}, {}
    for stored in schemes:
        try:
            prices[stored] = _fetch_one(stored, transport)
        except _SchemeError as error:
            failures[stored] = str(error)

    return {"prices": prices, "failures": failures}


class _SchemeError(Exception):
    """One scheme's lookup failed; reported per scheme, never raised out."""


def _fetch_one(stored, transport):
    """Search, match, and fetch the latest NAV for one stored scheme."""

    query = _search_query(stored)
    if not query:
        raise _SchemeError("nothing left to search for")

    url = MF_SEARCH_URL.format(query=urllib.parse.quote(query))
    status, body = _request(url, transport)
    if status != 200:
        raise _SchemeError(f"mfapi search returned HTTP {status}")

    try:
        hits = json.loads(body)
    except ValueError:
        raise _SchemeError("mfapi search returned a non-JSON response")

    if not isinstance(hits, list) or not hits:
        raise _SchemeError("no mfapi scheme matched")

    match = match_scheme(stored, hits)
    if match is None:
        raise _SchemeError("no mfapi scheme matched")

    status, body = _request(
        MF_SCHEME_URL.format(scheme_code=match["schemeCode"]), transport,
    )
    if status != 200:
        raise _SchemeError(f"mfapi returned HTTP {status}")

    try:
        detail = json.loads(body)
    except ValueError:
        raise _SchemeError("mfapi returned a non-JSON response")

    data = detail.get("data") if isinstance(detail, dict) else None
    if not isinstance(data, list) or not data:
        raise _SchemeError("no NAV history in the mfapi response")

    # data is newest-first (verified against the live API).
    nav_text = data[0].get("nav") if isinstance(data[0], dict) else None
    try:
        nav = float(nav_text)
    except (TypeError, ValueError):
        raise _SchemeError("no usable NAV in the mfapi response")

    if nav <= 0:
        raise _SchemeError("no usable NAV in the mfapi response")

    return nav


def _request(url, transport):
    """One transport call, converting transport exceptions to errors."""

    try:
        return transport(url, _HEADERS)
    except Exception as error:
        raise _SchemeError(f"request failed: {error}") from error


def _tokens(name):
    """Uppercase alphanumeric tokens of a scheme name, in order."""

    text = "".join(
        char if char.isalnum() else " " for char in str(name or "").upper()
    )
    return text.split()


def _search_query(stored):
    """Stored scheme name -> mfapi search query without generic words."""

    tokens = _tokens(stored)
    significant = [token for token in tokens if token not in _GENERIC_TOKENS]
    return " ".join(significant or tokens)


def match_scheme(stored, hits):
    """Best mfapi search hit for a stored scheme name, or None.

    The fund family's first token must appear in the candidate name and
    at least half of the stored tokens must match. Among survivors the
    best hit shares the most tokens, with fewer extra tokens winning
    ties (the Direct Plan beats the Regular Plan when the stored name
    says DIRECT).
    """

    stored_tokens = _tokens(stored)
    if not stored_tokens:
        return None

    anchor = stored_tokens[0]
    needed = max(1, len(stored_tokens) // 2)

    best, best_key = None, None
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        name = hit.get("schemeName")
        if not name:
            continue
        row_tokens = _tokens(name)
        row_set = set(row_tokens)
        if anchor not in row_set:
            continue
        shared = len(set(stored_tokens) & row_set)
        if shared < needed:
            continue
        extra = len(row_set - set(stored_tokens))
        key = (shared, -extra)
        if best_key is None or key > best_key:
            best, best_key = hit, key

    return best


def _urllib_transport(url, headers):
    """Default transport: real urllib. Only reached with consent."""

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
