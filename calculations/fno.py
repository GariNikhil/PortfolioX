"""F&O symbol normalization across broker sources.

The same option arrives in several text shapes:

    BANKNIFTY 45500 PE 27 JUL 2023      (contract-note PDF, verbatim)
    BANKNIFTY45500PE27Jul2023           (PDF text extraction, no spaces)
    BANKNIFTY 45500 PE 2023-03-09       (already ISO-dated)
    NIFTY 19150 PE 03 AUG 2023          (IIFL Trade Listing)

canonical_symbol() maps every shape to one form -

    BANKNIFTY 45500 PE 2023-07-27

- so the same option from different sources aggregates into one holding.
  Non-F&O symbols pass through unchanged; unparseable text passes through
  unchanged too (never mangle what we cannot recognize).
"""

import re
from datetime import date

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

# "BANKNIFTY 45500 PE 27 JUL 2023" / "BANKNIFTY 45500 PE 2023-03-09"
_SPACED = re.compile(
    r"^(?P<underlying>[A-Za-z][A-Za-z0-9&\-]*)\s+"
    r"(?P<strike>\d+(?:\.\d+)?)\s+"
    r"(?P<option_type>CE|PE)\s+"
    r"(?P<date>\d{1,2}\s+[A-Za-z]{3}\s+\d{4}|\d{4}-\d{2}-\d{2})$",
    re.IGNORECASE,
)

# "BANKNIFTY45500PE27Jul2023" / "BANKNIFTY45500PE2023-07-27"
_NOSPACE = re.compile(
    r"^(?P<underlying>[A-Za-z]+[A-Za-z0-9&\-]*?)"
    r"(?P<strike>\d+(?:\.\d+)?)"
    r"(?P<option_type>CE|PE)"
    r"(?P<date>\d{1,2}[A-Za-z]{3}\d{4}|\d{4}-\d{2}-\d{2})$",
    re.IGNORECASE,
)


def canonical_symbol(symbol):
    """F&O text in one canonical shape; everything else verbatim."""

    normalized = normalize_fno_symbol(symbol)
    return normalized if normalized is not None else symbol


def normalize_fno_symbol(symbol):
    """Return 'UNDERLYING STRIKE CE|PE YYYY-MM-DD', or None if not F&O."""

    text = str(symbol or "").strip()
    match = _SPACED.match(text) or _NOSPACE.match(text)
    if not match:
        return None

    expiry = _parse_expiry(match.group("date"))
    if expiry is None:
        return None

    strike = match.group("strike")
    if strike.endswith(".0"):
        strike = strike[:-2]  # 45500.0 -> 45500

    return (
        f"{match.group('underlying').upper()} {strike} "
        f"{match.group('option_type').upper()} {expiry.isoformat()}"
    )


def _parse_expiry(text):
    """'27 JUL 2023' / '27Jul2023' / '2023-07-27' -> date, else None."""

    text = text.strip()
    iso = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    day_month = re.match(
        r"^(\d{1,2})\s*([A-Za-z]{3})\s*(\d{4})$" if " " in text
        else r"^(\d{1,2})([A-Za-z]{3})(\d{4})$",
        text,
    )
    if day_month:
        month = _MONTHS.get(day_month.group(2).upper())
        if month:
            try:
                return date(int(day_month.group(3)), month, int(day_month.group(1)))
            except ValueError:
                return None
    return None
