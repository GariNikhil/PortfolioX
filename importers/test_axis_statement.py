"""Tests for the Axis Bank statement importer (PDF text parsing)."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.manager import (
    find_account_by_name,
    get_accounts,
    get_bank_transactions,
    update_account_details,
)
from database.schema import ensure_schema
from importers.axis_statement import import_axis_statement, parse_axis_pages
from importers.common import ImportFileError

# Fixture shaped like the real statement (referance/stock/bank
# accounts&statements/statement.pdf): wrapped
# particulars, single-line rows, a bracketed-interest row, a failed-
# transfer reversal pair, and the statement's own totals.
#
# Chain: opening 1000.00; debits 100 + 10 + 80 + 200 = 390.00;
# credits 50 + 21 + 200 = 271.00; closing 881.00.
_PAGES = ["""
DEMO INVESTOR
Joint Holder :- -
ADDRESS LINE ONE,
DEMOCITY Customer ID :900000001
ANDHRA PRADESH-INDIA IFSC Code :UTIB0004088
Registered Mobile No :<mobile> Nominee Name :SOME NAME
Registered Email ID:<email> PAN :ABCDE1234F
Scheme :NRO MARINER SAVINGS ACCOUNT CKYC NUMBER :<ckyc>
Statement of Axis Account No :000000000000001 for the period (From : 18-08-2025  To : 18-10-2025)
Tran Date Chq No Particulars Debit Credit Balance Init.
Br
OPENING BALANCE            1000.00
18-08-2025
UPI/P2M/000000000000/DEMO PAYEE ONE
SAMITY   /UPI/SBI PAYMENT SERVICES
              
100.00              900.00 4088
18-08-2025 Avg bal Chgs Incl GST                10.00              890.00 4088
20-08-2025
UPI/P2A/000000000000/DEMO PAYEE TWO
/UPI/Kotak Mahindra Bank                80.00              810.00 4088
01-10-2025
NEFT/SBIN000000000000/ITDTAX REFUND
2024-25 ABCDE/STATE BANK OF
INDIA//ATTN//INB                50.00              860.00 248
01-10-2025 Int on SB AC [27.00] Tax[6.00]                 21.00              881.00 4088
""", """
   
          
Legends :
ICONN				-		Transaction trough Internet Banking
CWDR				-		Cash Withdrawal through ATM
 
This is a system generated output and requires no signature.
          
05-10-2025
UPI/P2A/000000000000/DEMOINVST/Punjab
Na/Payment/ 
              
200.00             1081.00 4088
05-10-2025
UPI/P2A/000000000000/Demo Payee Three
/UPI/HDFC BANK LTD
              
200.00              881.00 4088
TRANSACTION TOTAL
              
390.00
                  
271.00
CLOSING BALANCE             881.00
++++ End of Statement ++++
Request From: 10.9.71.13
"""]


class AxisParserTests(unittest.TestCase):
    def test_parses_rows_signs_and_details(self):
        rows, failures, meta = parse_axis_pages(_PAGES)

        self.assertEqual(failures, [])
        self.assertEqual(len(rows), 7)

        first, last = rows[0], rows[-1]
        self.assertEqual(first["txn_date"], "2025-08-18")
        self.assertEqual(first["amount"], -100.0)
        self.assertEqual(
            first["description"],
            "UPI/P2M/000000000000/DEMO PAYEE ONE SAMITY /UPI/SBI PAYMENT SERVICES",
        )
        self.assertEqual(first["balance"], 900.0)
        self.assertEqual(last["txn_date"], "2025-10-05")
        self.assertEqual(last["amount"], -200.0)  # reversal debit
        self.assertEqual(last["balance"], 881.0)

        # Sign resolution via the running balance.
        by_description = {row["description"]: row for row in rows}
        self.assertEqual(
            by_description[
                "NEFT/SBIN000000000000/ITDTAX REFUND 2024-25 ABCDE/"
                "STATE BANK OF INDIA//ATTN//INB"
            ]["amount"],
            50.0,  # credit
        )
        # Bracketed figures stay in the description, not the amounts.
        interest = by_description["Int on SB AC [27.00] Tax[6.00]"]
        self.assertEqual(interest["amount"], 21.0)

        self.assertEqual(meta["opening_balance"], 1000.0)
        self.assertEqual(meta["closing_balance"], 881.0)
        self.assertEqual(meta["details"], {
            "holder_name": "Demo Investor",
            "account_number": "000000000000001",
            "pan": "ABCDE1234F",
        })

    def test_totals_and_closing_validate(self):
        # The fixture's own TRANSACTION TOTAL / CLOSING BALANCE agree
        # with the parsed rows, so no extra failures appear.
        _rows, failures, _meta = parse_axis_pages(_PAGES)
        self.assertFalse(
            any("TRANSACTION TOTAL" in failure.reason
                or "CLOSING BALANCE" in failure.reason
                for failure in failures),
        )

    def test_unreconcilable_row_is_reported_not_guessed(self):
        pages = ["""
OPENING BALANCE            1000.00
18-08-2025
UPI/P2M/1/SHOP
              
100.00              900.00 4088
19-08-2025
UPI/P2M/2/TEA
              
77.00              800.00 4088
"""]

        rows, failures, _meta = parse_axis_pages(pages)

        # 77.00 fits neither 900->800 (100) nor its negative: reported.
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn("do not reconcile", failures[0].reason)

    def test_unterminated_row_is_reported(self):
        pages = ["""
OPENING BALANCE            1000.00
18-08-2025
UPI/P2M/1/SHOP
19-08-2025
UPI/P2M/2/TEA
              
50.00              950.00 4088
"""]

        rows, failures, _meta = parse_axis_pages(pages)

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(failures), 1)
        self.assertIn("unterminated", failures[0].reason)

    def test_missing_opening_balance_raises(self):
        with self.assertRaises(ImportFileError):
            parse_axis_pages(["no statement here"])


class AxisImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "p.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)

    def _import(self):
        with patch.object(axis_module(), "read_pdf_pages", return_value=_PAGES):
            return import_axis_statement("statement.pdf")

    def test_first_import_creates_the_bank_account(self):
        result = self._import()

        self.assertEqual(result.imported, 7)
        self.assertEqual(result.duplicates, 0)
        self.assertIn("Created account 'Axis Bank' (PERSONAL)", result.notes)

        account = find_account_by_name("Axis Bank")
        self.assertEqual(account["kind"], "PERSONAL")
        self.assertEqual(account["account_number"], "000000000000001")
        self.assertEqual(account["pan"], "ABCDE1234F")
        self.assertEqual(account["holder_name"], "Demo Investor")
        # Raw account rows carry paise.
        self.assertEqual(account["current_balance"], 88100)
        self.assertEqual(
            len(get_bank_transactions(account_id=account["id"])), 7,
        )

    def test_reimport_detects_the_account_and_deduplicates(self):
        self._import()
        result = self._import()

        self.assertEqual(result.imported, 0)
        self.assertEqual(result.duplicates, 7)
        self.assertNotIn(
            "Created account 'Axis Bank' (PERSONAL)", result.notes,
        )
        self.assertEqual(
            len([a for a in get_accounts() if a["name"] == "Axis Bank"]), 1,
        )

    def test_pan_on_a_broker_account_does_not_capture_bank_rows(self):
        # Regression: the live Main broker carries the user's PAN (from
        # the Groww import). PAN matching would have filed the Axis
        # statement under it instead of creating 'Axis Bank'.
        broker = find_account_by_name("Main broker")
        update_account_details(broker["id"], pan="ABCDE1234F")

        result = self._import()

        self.assertIn("Created account 'Axis Bank' (PERSONAL)", result.notes)
        self.assertEqual(
            len(get_bank_transactions(account_id=broker["id"])), 0,
        )
        self.assertEqual(
            len(get_bank_transactions(
                account_id=find_account_by_name("Axis Bank")["id"],
            )), 7,
        )

    def test_explicit_account_choice_wins_over_detection(self):
        personal = find_account_by_name("Main personal")
        with patch.object(axis_module(), "read_pdf_pages", return_value=_PAGES):
            result = import_axis_statement(
                "stmt.pdf", account_id=personal["id"],
            )

        self.assertIn(f"Account: {personal['name']}", result.notes)
        self.assertNotIn(
            "Created account 'Axis Bank' (PERSONAL)", result.notes,
        )
        self.assertEqual(
            len(get_bank_transactions(account_id=personal["id"])), 7,
        )
        # The personal account's own details are not overwritten by the
        # bank statement's (holder name stays whatever it was).
        self.assertIsNone(find_account_by_name("Axis Bank"))


def axis_module():
    import importers.axis_statement as module
    return module


if __name__ == "__main__":
    unittest.main()
