import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.database_path = (
            Path(self.temporary_directory.name) / "nested" / "test.db"
        )
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)

    def connect(self):
        connection = db.create_connection()
        self.addCleanup(connection.close)
        return connection

    def test_connection_creates_database_at_configured_absolute_path(self):
        connection = self.connect()

        self.assertTrue(self.database_path.is_file())
        self.assertEqual(
            tuple(connection.execute("SELECT 1").fetchone()), (1,)
        )

    def test_foreign_keys_are_enforced(self):
        # SQLite ignores REFERENCES unless the pragma is set per connection.
        connection = self.connect()
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute(
            "CREATE TABLE child ("
            "id INTEGER PRIMARY KEY, "
            "parent_id INTEGER REFERENCES parent(id))"
        )

        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO child (parent_id) VALUES (99)")

    def test_locks_wait_instead_of_failing_at_once(self):
        connection = self.connect()

        self.assertEqual(
            connection.execute("PRAGMA busy_timeout").fetchone()[0], 5000
        )
        self.assertEqual(
            connection.execute("PRAGMA foreign_keys").fetchone()[0], 1
        )

    def test_fetch_all_closes_its_connection(self):
        with db.transaction() as connection:
            connection.execute("CREATE TABLE sample (value INTEGER)")
            connection.execute("INSERT INTO sample (value) VALUES (7)")

        rows = db.fetch_all("SELECT value FROM sample")

        self.assertEqual([row["value"] for row in rows], [7])
        # On Windows an open SQLite file cannot be deleted, so this only
        # succeeds when fetch_all released its connection.
        self.database_path.unlink()


if __name__ == "__main__":
    unittest.main()
