"""Tests for the runtime path helper.

These guard the one failure that would be invisible until a user's data
was gone: a frozen (PyInstaller) build must not resolve writable folders
from ``__file__``. Inside a bundle that points into a temporary folder
which is deleted on exit, so the database, the password vault and the
book cache would silently reset on every launch.
"""

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import paths
from books import library
from database import db
from security import vault

REPO_ROOT = Path(__file__).resolve().parent


class SourceCheckoutTest(unittest.TestCase):
    """Running from source keeps everything beside app.py."""

    def setUp(self):
        self.remove_home = mock.patch.dict(os.environ, {paths.HOME_ENV: ""})
        self.remove_home.start()
        self.addCleanup(self.remove_home.stop)

        # Some database tests assign db.DB_PATH to a scratch file directly and
        # leave it there. Re-evaluate the module so this test measures the
        # resolver rather than whatever ran before it.
        self.addCleanup(importlib.reload, db)
        importlib.reload(db)

    def test_app_root_is_the_repo_root(self):
        self.assertEqual(paths.app_root(), REPO_ROOT)

    def test_data_dir_sits_under_the_repo(self):
        self.assertEqual(paths.data_dir(), REPO_ROOT / "data")

    def test_books_dir_is_the_personal_shelf(self):
        self.assertEqual(
            paths.books_dir(), REPO_ROOT / "referance" / "books"
        )

    def test_explicit_root_overrides_the_running_app(self):
        elsewhere = REPO_ROOT / "elsewhere"

        self.assertEqual(paths.data_dir(elsewhere), elsewhere / "data")
        self.assertEqual(
            paths.books_dir(elsewhere), elsewhere / "referance" / "books"
        )

    def test_consumers_resolve_from_the_same_root(self):
        self.assertEqual(db.PROJECT_ROOT, REPO_ROOT)
        self.assertEqual(db.DB_PATH, REPO_ROOT / "data" / "portfoliox.db")
        self.assertEqual(vault.VAULT_PATH, REPO_ROOT / "data" / "vault.json")
        self.assertEqual(
            library.BOOKS_FOLDER, REPO_ROOT / "referance" / "books"
        )
        self.assertEqual(library.CACHE_FOLDER, REPO_ROOT / "data" / "book_text")


class FrozenBuildTest(unittest.TestCase):
    """A frozen build keeps writable data next to the executable."""

    def setUp(self):
        self.folder = Path(tempfile.gettempdir()).resolve() / "PortfolioX-build"
        self.other = Path(tempfile.gettempdir()).resolve() / "PortfolioX-home"

        for patcher in (
            mock.patch.object(sys, "frozen", True, create=True),
            mock.patch.object(sys, "executable", str(self.folder / "PortfolioX.exe")),
            mock.patch.dict(os.environ, {paths.HOME_ENV: ""}),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_app_root_is_the_executable_folder(self):
        self.assertEqual(paths.app_root(), self.folder)

    def test_data_is_not_inside_the_bundle(self):
        # The bundle temp folder is named _MEIxxxx; nothing writable may
        # land there, because PyInstaller deletes it on exit.
        self.assertNotIn("_MEI", str(paths.data_dir()))
        self.assertEqual(paths.data_dir(), self.folder / "data")

    def test_database_would_live_beside_the_executable(self):
        expected = self.folder / "data" / db.DB_FILE

        self.assertEqual(paths.data_dir() / db.DB_FILE, expected)
        self.assertEqual(expected, self.folder / "data" / "portfoliox.db")

    def test_vault_and_cache_live_beside_the_executable(self):
        self.assertEqual(
            paths.data_dir() / "vault.json", self.folder / "data" / "vault.json"
        )
        self.assertEqual(
            paths.data_dir() / "book_text", self.folder / "data" / "book_text"
        )

    def test_books_are_looked_for_beside_the_executable(self):
        self.assertEqual(
            paths.books_dir(), self.folder / "referance" / "books"
        )

    def test_home_override_beats_the_executable_folder(self):
        os.environ[paths.HOME_ENV] = str(self.other)

        self.assertEqual(paths.app_root(), self.other)
        self.assertEqual(paths.data_dir(), self.other / "data")


class InstalledPackageTest(unittest.TestCase):
    """A pip-installed copy keeps writable data outside site-packages.

    site-packages is read-only for non-admin installs and is wiped on
    upgrade, so resolving the database there would either fail on first
    run or delete the user's portfolio during a package upgrade.
    """

    def setUp(self):
        temp = Path(tempfile.gettempdir()).resolve()
        self.site_file = (
            temp / "venv" / "Lib" / "site-packages" / "paths.py"
        )
        self.local = temp / "LocalAppData"

        for patcher in (
            mock.patch.object(paths, "__file__", str(self.site_file)),
            mock.patch.dict(
                os.environ,
                {paths.HOME_ENV: "", "LOCALAPPDATA": str(self.local)},
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_app_root_leaves_site_packages(self):
        root = paths.app_root()

        self.assertNotIn("site-packages", str(root))
        self.assertEqual(root, self.local / paths.APP_NAME)

    def test_writable_folders_are_per_user(self):
        root = self.local / paths.APP_NAME

        self.assertEqual(paths.data_dir(), root / "data")
        self.assertEqual(paths.books_dir(), root / "referance" / "books")

    def test_home_override_beats_the_install_folder(self):
        elsewhere = self.local / "scratch"
        os.environ[paths.HOME_ENV] = str(elsewhere)

        self.assertEqual(paths.app_root(), elsewhere)

    def test_without_localappdata_falls_back_to_home(self):
        home = self.local / "home"
        os.environ.pop("LOCALAPPDATA", None)
        with mock.patch.object(Path, "home", return_value=home):
            self.assertEqual(
                paths.app_root(), home / ".local" / "share" / paths.APP_NAME
            )


if __name__ == "__main__":
    unittest.main()
