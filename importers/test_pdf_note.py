"""Tests for the contract-note PDF importer.

PDF fixtures are built in-code: a minimal single-page PDF for the happy
paths and a pypdf-encrypted copy for the vault flow. The parser core is
also tested directly with contract-note text copied from the real broker
notes' layout.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.schema import ensure_schema
from security import vault
from security.vault import PasswordRequiredError
from importers.common import ImportFileError
from importers.pdf_note import (
    import_contract_note_pdf,
    parse_contract_note_lines,
    parse_contract_note_pdf,
)
from importers.support import ScratchDbTestCase

# Mirrors the real referance/stock/CONTRACT NOTE PDF layout: page furniture,
# the self-dating header, trade lines, and per-instrument totals.
NOTE_TEXT = """FUTURE & OPTIONS
Unique Client Code: 1234567890 Name: Demo Investor
Contract note no. CN/23-24/0000000000
Trade date 27-07-2023
Sir / Madam, I / We have this day done by your order and on your account:
Order
no.
1800000000000000 12:12:53 698000000 12:12:53 BANKNIFTY 45500 PE 27 Jul 2023 NSE B 60 20.20 20.20 -1212.00
1800000000000001 12:14:13 698417850 12:14:13 BANKNIFTY 45500 PE 27 Jul 2023 NSE S -60 23.30 23.30 1398.00
1800000120000000 12:20:00 699000000 12:20:00 RELIANCE NSE B 10 2500.00 25010.00
Total BANKNIFTY 45500 PE 27 Jul 2023 0 186.00
Net Total 186.00
"""

PDF_PASSWORD = "note-password"


def build_pdf(lines):
    """Build a minimal valid single-page PDF containing one line of text each."""

    text_ops = ["BT", "/F1 8 Tf", "40 750 Td", "12 TL"]
    for line in lines:
        escaped = (line.replace("\\", r"\\")
                        .replace("(", r"\(")
                        .replace(")", r"\)"))
        text_ops.append(f"({escaped}) Tj T*")
    text_ops.append("ET")
    stream = "\n".join(text_ops).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("latin-1") + body + b"\nendobj\n"
    xref_position = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin-1")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("latin-1")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_position}\n%%EOF"
    ).encode("latin-1")
    return bytes(out)


def write_pdf(directory, lines, name="contract note.pdf", password=None):
    from pypdf import PdfReader, PdfWriter
    import io

    raw = build_pdf(lines)
    if password is None:
        path = Path(directory) / name
        path.write_bytes(raw)
        return path

    reader = PdfReader(io.BytesIO(raw))
    writer = PdfWriter()
    writer.append(reader)
    writer.encrypt(password)
    buffer = io.BytesIO()
    writer.write(buffer)
    path = Path(directory) / name
    path.write_bytes(buffer.getvalue())
    return path


class VaultBackedTestCase(ScratchDbTestCase):
    """Adds the vault seams on top of the scratch-database base."""

    def setUp(self):
        super().setUp()
        self.temporary_vault = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temporary_vault.name) / "vault.json"
        self.keystore = {}
        self.patches = [
            patch.object(vault, "VAULT_PATH", self.vault_path),
            patch.object(vault, "_keyring_get", lambda: self.keystore.get("key")),
            patch.object(
                vault, "_keyring_set", lambda value: self.keystore.update(key=value)
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temporary_vault.cleanup)


class CoreParseTests(unittest.TestCase):
    def test_parses_real_note_text_with_self_date(self):
        rows, failures = parse_contract_note_lines(NOTE_TEXT)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 3)

        first = rows[0]
        self.assertEqual(first["trade_date"], "2023-07-27")
        self.assertEqual(first["symbol"], "BANKNIFTY 45500 PE 27 JUL 2023")
        self.assertEqual(first["transaction_type"], "BUY")
        self.assertEqual(first["quantity"], 60.0)
        self.assertEqual(first["price"], 20.20)
        self.assertEqual(first["exchange"], "NSE")
        # Net total -1212.00 == 60 * 20.20 exactly -> zero charges.
        self.assertEqual(first["brokerage"], 0.0)

    def test_sell_side_carries_positive_quantity(self):
        rows, _ = parse_contract_note_lines(NOTE_TEXT)

        sell = rows[1]
        self.assertEqual(sell["transaction_type"], "SELL")
        self.assertEqual(sell["quantity"], 60.0)
        self.assertEqual(sell["price"], 23.30)

    def test_brokerage_derived_from_net_total_not_column_position(self):
        rows, _ = parse_contract_note_lines(NOTE_TEXT)

        # 10 * 2500.00 = 25000.00 gross, net total 25010.00 -> 10.00 charges.
        # (Column position would have misread "25010.00" as a per-unit rate.)
        self.assertEqual(rows[2]["brokerage"], 10.0)
        self.assertEqual(rows[2]["symbol"], "RELIANCE")

    def test_lines_without_trade_shape_are_skipped_silently(self):
        furniture = [
            "Trade date 27-07-2023",
            "Order",
            "Total BANKNIFTY 45500 PE 27 Jul 2023 0 186.00",
            "Net Total 186.00",
            "Sir / Madam, I / We have this day done by your order",
        ]
        rows, failures = parse_contract_note_lines("\n".join(furniture))

        self.assertEqual(rows, [])
        self.assertEqual(failures, [])

    def test_bad_numbers_become_failures_with_line_numbers(self):
        text = (
            "Trade date 27-07-2023\n"
            "12345678901234 10:00:00 111 10:00:01 SYMBOL NSE B notanumber 5 100\n"
        )
        rows, failures = parse_contract_note_lines(text)

        self.assertEqual(rows, [])
        self.assertEqual(failures[0].row_number, 2)
        self.assertIn("Buy(B)/Sell(S)", failures[0].reason)

    def test_missing_net_total_becomes_failure(self):
        text = (
            "Trade date 27-07-2023\n"
            "12345678901234 10:00:00 111 10:00:01 SYMBOL NSE B 10 2500.00\n"
        )
        _, failures = parse_contract_note_lines(text)

        self.assertEqual(len(failures), 1)
        self.assertIn("no Net Total column", failures[0].reason)

    def test_missing_trade_date_header_rejects_file(self):
        with self.assertRaisesRegex(ImportFileError, "Trade date"):
            parse_contract_note_lines("no dates here at all")

    def test_negative_price_becomes_failure(self):
        text = (
            "Trade date 27-07-2023\n"
            "12345678901234 10:00:00 111 10:00:01 SYMBOL NSE B 10 -5.00 100.00\n"
        )
        _, failures = parse_contract_note_lines(text)

        self.assertIn("cannot be negative", failures[0].reason)


class FileTests(VaultBackedTestCase):
    def test_unencrypted_pdf_imports_end_to_end(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines())

        result = import_contract_note_pdf(source)

        self.assertEqual(result.imported, 3)
        self.assertEqual(result.failures, [])

        log = db.fetch_all("SELECT import_type, status FROM imports")
        self.assertEqual(log[0]["import_type"], "CONTRACT_NOTE_PDF")
        self.assertEqual(log[0]["status"], "SUCCESS")

    def test_encrypted_pdf_without_stored_password_prompts_once(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines(),
                           password=PDF_PASSWORD)

        with self.assertRaises(PasswordRequiredError):
            import_contract_note_pdf(source)

        # Awaiting the one-time password is not an import failure.
        self.assertEqual(db.fetch_all("SELECT * FROM imports"), [])

    def test_encrypted_pdf_with_stored_password_imports_automatically(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines(),
                           password=PDF_PASSWORD)
        vault.store_password("CONTRACT_NOTE_PDF", PDF_PASSWORD)

        result = import_contract_note_pdf(source)

        self.assertEqual(result.imported, 3)

    def test_wrong_stored_password_raises_for_a_new_one(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines(),
                           password=PDF_PASSWORD)
        vault.store_password("CONTRACT_NOTE_PDF", "not-the-password")

        with self.assertRaisesRegex(PasswordRequiredError, "rejected"):
            import_contract_note_pdf(source)

    def test_pattern_password_matches_the_file(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines(),
                           name="CONTRACT NOTE 1234567890-1.pdf",
                           password=PDF_PASSWORD)
        vault.store_password(
            "CONTRACT_NOTE_PDF", PDF_PASSWORD, file_pattern="*1234567890*"
        )

        result = import_contract_note_pdf(source)

        self.assertEqual(result.imported, 3)

    def test_reimport_skips_duplicates(self):
        source = write_pdf(self.temporary_directory.name, NOTE_TEXT.splitlines())

        first = import_contract_note_pdf(source)
        second = import_contract_note_pdf(source)

        self.assertEqual(first.imported, 3)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.duplicates, 3)

    def test_missing_file_raises(self):
        with self.assertRaisesRegex(ImportFileError, "file not found"):
            parse_contract_note_pdf(
                Path(self.temporary_directory.name) / "missing.pdf"
            )

    def test_non_pdf_file_raises_readable_error(self):
        not_a_pdf = Path(self.temporary_directory.name) / "fake.pdf"
        not_a_pdf.write_text("plain text", encoding="utf-8")

        with self.assertRaisesRegex(ImportFileError, "could not open"):
            parse_contract_note_pdf(not_a_pdf)


if __name__ == "__main__":
    unittest.main()