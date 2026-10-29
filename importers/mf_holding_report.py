"""Mutual-fund holding-report import (Excel / CSV snapshot).

A mutual-fund holdings statement lists the CURRENT folio position per
scheme: units, invested value and current value. Like the stock holding
report it is a snapshot, not a history, so rows are stored as
source='mf_holding_report' rows in manual_holdings and REPLACE the
transaction-derived position at rebuild time — independently of the
stock snapshot, so importing one never wipes the other.

Fund statements have no average-price column; the average cost is
derived as Invested Value / Units. The statement's Current Value /
Units gives the NAV per unit, which seeds the prices table
(source='mf_holding_report') so market value and returns light up.

Account details in the header (Name, Mobile Number, PAN, ...) are
extracted and auto-filled into the assigned account without
overwriting anything the user typed.
"""

from pathlib import Path

from importers.common import (
    ImportFileError,
    ImportResult,
    RowFailure,
    clean_symbol,
    extract_account_details,
    finish_import,
    is_blank_row,
    parse_number,
    read_tabular_rows,
    record_import,
)
from database import manager

SOURCE_KIND = "MF_HOLDING_REPORT"

# Column detection, in priority order: the first header cell matching an
# earlier pattern wins. Patterns are lowercase fragments matched against
# the normalized header cell.
_COLUMN_PATTERNS = {
    "scheme_name": (
        "scheme name", "scheme", "fund name", "fund",
    ),
    "units": (
        "units", "unit balance", "balance units",
    ),
    "invested_value": (
        "invested value", "invested amount", "amount invested",
        "total invested", "invested",
    ),
}

# Optional: when the statement also carries the current value we derive
# the NAV per unit and seed the prices table with it.
_OPTIONAL_COLUMN_PATTERNS = {
    "current_value": (
        "current value", "market value", "current amount",
        "present value", "portfolio value",
    ),
}

# A row qualifies as the header when at least these columns appear.
_HEADER_MATCH = ("scheme_name", "units", "invested_value")


def import_mf_holding_report(path, account_id=None):
    """Import a mutual-fund holding-report file and return an ImportResult.

    The report must be assigned to an existing account (a fund statement
    is per investor account by nature). File-level problems raise
    ImportFileError after recording a FAILED audit entry; row-level
    problems never abort the import.
    """

    source = Path(path)
    filename = source.name

    try:
        rows, failures = parse_mf_holding_report(source)
    except ImportFileError as error:
        record_import(filename, SOURCE_KIND, f"FAILED ({error})")
        raise

    if not rows:
        message = f"{filename} contains no importable fund rows"
        record_import(filename, SOURCE_KIND, f"FAILED ({message})")
        raise ImportFileError(message)

    # Auto-fill account details from label/value rows in the file
    # (e.g. 'PAN', 'AAAAA0000A'). Only fills account fields the user
    # has not filled themselves.
    details = extract_account_details(source)
    if details and account_id is not None:
        try:
            manager.fill_account_details_if_empty(account_id, **details)
        except Exception:  # auto-fill must never block the import
            pass

    result_failures = list(failures)
    import_id = None
    try:
        # Audit first so the snapshot rows can carry the audit row's id;
        # the status flips to SUCCESS/FAILED once the batch is committed.
        import_id = record_import(filename, SOURCE_KIND, "PENDING")
        imported = manager.replace_holding_report(
            rows, account_id, source="mf_holding_report",
            import_id=import_id,
        )
        # Seed market prices with the derived NAV per unit, BEFORE the
        # rebuild so market value and returns light up.
        for row in rows:
            nav = row.get("closing_price")
            if nav is not None:
                manager.set_price(
                    row["symbol"], nav, source="mf_holding_report",
                )
        manager.rebuild_holdings()
    except Exception as error:
        finish_import(import_id, f"FAILED ({error})")
        raise ImportFileError(f"database rejected the batch: {error}") from error

    result = ImportResult(filename=filename, failures=result_failures)
    result.imported = imported
    finish_import(import_id, "SUCCESS")
    return result


def parse_mf_holding_report(path):
    """Parse a mutual-fund holding-report file into (rows, failures).

    Rows are manager-ready mappings {symbol, quantity, average_price}
    with rupee floats, plus {closing_price} (the derived NAV) when the
    statement carries a current value; failures are RowFailure entries.
    Raises ImportFileError for unreadable files or a missing header.
    """

    source = Path(path)
    if not source.exists():
        raise ImportFileError(f"file not found: {source}")

    raw_rows = read_tabular_rows(source)

    columns = _locate_header(raw_rows)
    if columns is None:
        raise ImportFileError(
            "could not find a header row with scheme name, units and "
            "invested value columns"
        )

    scheme_index = columns["scheme_name"]
    units_index = columns["units"]
    invested_index = columns["invested_value"]
    current_index = columns.get("current_value")

    rows, failures = [], []
    for row_number, raw in enumerate(raw_rows, start=1):
        if row_number <= columns["header_row"]:
            continue
        if is_blank_row(raw):
            continue

        symbol = clean_symbol(_cell(raw, scheme_index))
        if not symbol:
            failures.append(RowFailure(
                row_number=row_number, reason="missing scheme name",
            ))
            continue
        try:
            units = parse_number(
                _cell(raw, units_index), "units", positive=True,
            )
            invested_value = parse_number(
                _cell(raw, invested_index), "invested value",
            )
        except ValueError as error:
            failures.append(RowFailure(row_number=row_number, reason=str(error)))
            continue

        entry = {
            "symbol": symbol,
            "quantity": units,
            # No average-price column exists in fund statements: the
            # average cost is the invested value spread over the units.
            "average_price": invested_value / units,
        }

        # The NAV is auxiliary: a bad value never fails the holding row,
        # it only skips the price seeding.
        if current_index is not None:
            current_cell = _cell(raw, current_index)
            if current_cell is not None and str(current_cell).strip():
                try:
                    current_value = parse_number(
                        current_cell, "current value",
                    )
                    entry["closing_price"] = current_value / units
                except ValueError:
                    failures.append(RowFailure(
                        row_number=row_number,
                        reason=(
                            f"{symbol}: invalid current value "
                            f"'{str(current_cell).strip()}' "
                            "(fund imported without its NAV)"
                        ),
                    ))

        rows.append(entry)

    return rows, failures


def _cell(raw, index):
    """Cell at index, or '' when the row is shorter (ragged CSV lines)."""

    return raw[index] if index < len(raw) else ""


def _locate_header(raw_rows):
    """Find the header row and map canonical columns to cell indexes.

    Returns {"header_row": int, "scheme_name": i, "units": i,
    "invested_value": i[, "current_value": i]} or None when no row
    qualifies. The current-value column is optional.
    """

    for row_number, raw in enumerate(raw_rows, start=1):
        normalized = [
            str(cell).strip().lower() if cell is not None else ""
            for cell in raw
        ]
        columns = {}
        for canonical, patterns in _COLUMN_PATTERNS.items():
            for index, cell in enumerate(normalized):
                if not cell:
                    continue
                if any(cell == pattern or pattern in cell for pattern in patterns):
                    columns[canonical] = index
                    break

        if all(name in columns for name in _HEADER_MATCH):
            for canonical, patterns in _OPTIONAL_COLUMN_PATTERNS.items():
                for index, cell in enumerate(normalized):
                    if not cell:
                        continue
                    if any(cell == pattern or pattern in cell for pattern in patterns):
                        columns[canonical] = index
                        break
            columns["header_row"] = row_number
            return columns

    return None
