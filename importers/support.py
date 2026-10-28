"""Shared test support for importer tests (not discovered as tests itself).

Provides a TestCase base that runs every test against a throwaway database,
mirroring the setUp in test_groww.py.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from database import db
from database.schema import ensure_schema


class ScratchDbTestCase(unittest.TestCase):
    """Every test runs against a throwaway database."""

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "portfoliox.db"
        self.database_patch = patch.object(db, "DB_PATH", self.database_path)
        self.database_patch.start()
        ensure_schema()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary_directory.cleanup)
