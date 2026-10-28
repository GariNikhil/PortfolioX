"""Tests for the pre-import database backup (scratch directories only)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from database.backup import backup_database


class BackupDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.db_path = self.temp / "data" / "portfoliox.db"
        self.db_path.parent.mkdir(parents=True)
        self.db_path.write_bytes(b"sqlite-fake-content")

    def test_backup_copies_the_database(self):
        target = backup_database(self.db_path, backup_dir=self.temp / "backups")

        self.assertIsNotNone(target)
        self.assertTrue(target.exists())
        self.assertEqual(target.read_bytes(), b"sqlite-fake-content")

    def test_timestamped_name(self):
        target = backup_database(self.db_path, backup_dir=self.temp / "backups")

        # portfoliox-YYYYMMDD-HHMMSS.db
        self.assertRegex(target.name, r"^portfoliox-\d{8}-\d{6}\.db$")

    def test_missing_database_returns_none(self):
        missing = self.temp / "data" / "nope.db"

        self.assertIsNone(backup_database(missing, backup_dir=self.temp / "backups"))

    def test_same_second_backups_get_distinct_names(self):
        folder = self.temp / "backups"
        first = backup_database(self.db_path, backup_dir=folder)
        second = backup_database(self.db_path, backup_dir=folder)

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists() and second.exists())

    def test_old_backups_are_pruned(self):
        folder = self.temp / "backups"
        backup_database(self.db_path, backup_dir=folder, keep=3)
        backup_database(self.db_path, backup_dir=folder, keep=3)
        backup_database(self.db_path, backup_dir=folder, keep=3)
        backup_database(self.db_path, backup_dir=folder, keep=3)
        backup_database(self.db_path, backup_dir=folder, keep=3)

        backups = list(folder.glob("portfoliox-*.db"))

        self.assertEqual(len(backups), 3)


if __name__ == "__main__":
    unittest.main()
