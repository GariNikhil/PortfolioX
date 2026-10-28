import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db


class DatabaseConnectionTests(unittest.TestCase):
    def test_connection_creates_database_at_configured_absolute_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database_path = Path(temporary_directory) / "nested" / "test.db"
            with patch.object(db, "DB_PATH", database_path):
                connection = db.create_connection()
                try:
                    self.assertTrue(database_path.is_file())
                    self.assertEqual(
                        tuple(connection.execute("SELECT 1").fetchone()), (1,)
                    )
                finally:
                    connection.close()


if __name__ == "__main__":
    unittest.main()