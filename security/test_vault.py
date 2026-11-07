"""Tests for the secure password vault.

The real OS keystore and the real vault file are never touched: the keyring
seam is stubbed with an in-memory dict and VAULT_PATH points at a temporary
file.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security import vault
from security.vault import (
    PasswordRequiredError,
    VaultError,
    delete_password,
    get_password,
    list_entries,
    password_for,
    status,
    store_password,
)


class VaultTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.vault_path = Path(self.temporary_directory.name) / "vault.json"
        self.keystore = {}

        self.patches = [
            patch.object(vault, "VAULT_PATH", self.vault_path),
            patch.object(
                vault, "_keyring_get", lambda: self.keystore.get("key")
            ),
            patch.object(
                vault, "_keyring_set", lambda value: self.keystore.update(key=value)
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.temporary_directory.cleanup)


class StoreAndRetrieveTests(VaultTestCase):
    def test_roundtrip_and_overwrite(self):
        store_password("CONTRACT_NOTE_PDF", "s3cret-pan")
        self.assertEqual(get_password("CONTRACT_NOTE_PDF"), "s3cret-pan")

        store_password("CONTRACT_NOTE_PDF", "updated")
        self.assertEqual(get_password("CONTRACT_NOTE_PDF"), "updated")
        self.assertEqual(len(list_entries()), 1)

    def test_passwords_never_touch_disk_in_plain_text(self):
        store_password("CONTRACT_NOTE_PDF", "s3cret-pan")

        raw = self.vault_path.read_text(encoding="utf-8")
        self.assertNotIn("s3cret-pan", raw)
        self.assertIn("ciphertext", raw)

    def test_entries_are_json_with_metadata(self):
        store_password("CONTRACT_NOTE_PDF", "pw", file_pattern="*.pdf")
        entry = list_entries()[0]
        self.assertEqual(entry["kind"], "CONTRACT_NOTE_PDF")
        self.assertEqual(entry["file_pattern"], "*.pdf")
        self.assertIn("updated_at", entry)

    def test_empty_values_rejected(self):
        with self.assertRaisesRegex(VaultError, "must not be empty"):
            store_password("CONTRACT_NOTE_PDF", "   ")
        with self.assertRaisesRegex(VaultError, "must not be empty"):
            store_password("  ", "pw")

    def test_vault_file_created_on_demand(self):
        self.assertEqual(list_entries(), [])
        self.assertFalse(self.vault_path.exists())


class PatternResolutionTests(VaultTestCase):
    def test_password_for_prefers_kind_plus_pattern(self):
        store_password("CONTRACT_NOTE_PDF", "broker-wide")
        store_password("CONTRACT_NOTE_PDF", "specific",
                       file_pattern="*1234567890*")

        hit = password_for("CONTRACT NOTE 1234567890-1.pdf", "CONTRACT_NOTE_PDF")
        miss_kind = password_for("other.pdf", "CONTRACT_NOTE_PDF")
        self.assertEqual(hit, "specific")
        self.assertEqual(miss_kind, "broker-wide")

    def test_password_for_falls_back_to_pattern_only_match(self):
        store_password("STATEMENT_PDF", "shared", file_pattern="DEMO*")

        self.assertEqual(
            password_for("DEMO_ledger.pdf", "UNKNOWN_KIND"), "shared"
        )
        self.assertIsNone(password_for("unrelated.pdf", "UNKNOWN_KIND"))

    def test_missing_password_returns_none(self):
        self.assertIsNone(get_password("CONTRACT_NOTE_PDF"))
        self.assertIsNone(password_for("a.pdf", "CONTRACT_NOTE_PDF"))


class FailureModeTests(VaultTestCase):
    def test_lost_keystore_key_raises_not_crashes(self):
        store_password("CONTRACT_NOTE_PDF", "pw")
        self.keystore.clear()  # as if the credential store entry was wiped

        with self.assertRaisesRegex(VaultError, "cannot be decrypted"):
            get_password("CONTRACT_NOTE_PDF")

    def test_corrupt_vault_file_raises(self):
        store_password("CONTRACT_NOTE_PDF", "pw")
        self.vault_path.write_text("{not json", encoding="utf-8")

        with self.assertRaisesRegex(VaultError, "unreadable"):
            get_password("CONTRACT_NOTE_PDF")

    def test_key_is_created_once_and_reused(self):
        store_password("A", "pw1")
        first_key = self.keystore["key"]
        store_password("B", "pw2")

        self.assertEqual(self.keystore["key"], first_key)
        self.assertEqual(get_password("A"), "pw1")
        self.assertEqual(get_password("B"), "pw2")

    def test_failed_write_keeps_the_previous_vault(self):
        # The swap is the last step; a failure before it must leave the old
        # file (and the passwords in it) untouched rather than truncated.
        store_password("CONTRACT_NOTE_PDF", "old-pw")
        before = self.vault_path.read_bytes()

        with patch.object(vault.os, "replace", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(VaultError, "could not write"):
                store_password("CONTRACT_NOTE_PDF", "new-pw")

        self.assertEqual(self.vault_path.read_bytes(), before)
        self.assertEqual(get_password("CONTRACT_NOTE_PDF"), "old-pw")

    def test_save_leaves_no_temporary_file_behind(self):
        store_password("A", "pw1")

        self.assertEqual(
            [path.name for path in self.vault_path.parent.iterdir()],
            ["vault.json"],
        )


class DeleteAndStatusTests(VaultTestCase):
    def test_delete_removes_kind_entries(self):
        store_password("A", "pw1")
        store_password("A", "pw2", file_pattern="*.pdf")
        store_password("B", "pw3")

        delete_password("A")

        self.assertEqual([entry["kind"] for entry in list_entries()], ["B"])

    def test_delete_single_pattern_keeps_other_entries(self):
        store_password("A", "pw1")
        store_password("A", "pw2", file_pattern="*.pdf")

        delete_password("A", file_pattern="*.pdf")

        self.assertEqual(len(list_entries()), 1)
        self.assertIsNone(list_entries()[0]["file_pattern"])

    def test_status_reports_health_without_secrets(self):
        store_password("CONTRACT_NOTE_PDF", "pw")

        report = status()
        self.assertTrue(report["key_configured"])
        self.assertEqual(report["entries"], 1)
        self.assertNotIn("pw", json.dumps(report))

    def test_password_required_error_is_a_vault_error(self):
        # The UI catches the base class to handle any vault problem.
        self.assertTrue(issubclass(PasswordRequiredError, VaultError))


if __name__ == "__main__":
    unittest.main()
