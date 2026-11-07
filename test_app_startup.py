"""Tests for the startup failure handler in ``app.py``.

A frozen build runs with ``console=False``, so a crash before the main
window exists has no visible output at all. These guard the log file and
the dialog that take the console's place.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class StartupFailureTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.folder = Path(self.temporary_directory.name) / "data"

        show_error_patch = mock.patch("tkinter.messagebox.showerror")
        self.show_error = show_error_patch.start()
        self.addCleanup(show_error_patch.stop)

        self.data_dir_patch = mock.patch.object(
            app, "data_dir", return_value=self.folder
        )
        self.data_dir_patch.start()
        self.addCleanup(self.data_dir_patch.stop)

    def fail(self, message):
        try:
            raise RuntimeError(message)
        except RuntimeError as error:
            app.report_startup_failure(error)

    def test_traceback_is_appended_to_the_log(self):
        self.fail("schema is broken")
        self.fail("schema is broken")

        text = (self.folder / app.ERROR_LOG_NAME).read_text(encoding="utf-8")

        self.assertEqual(text.count("RuntimeError: schema is broken"), 2)
        self.assertIn("Traceback (most recent call last)", text)

    def test_dialog_names_the_log_file(self):
        self.fail("boom")

        title, body = self.show_error.call_args.args
        self.assertEqual(title, "PortfolioX could not start")
        self.assertIn("boom", body)
        self.assertIn(str(self.folder / app.ERROR_LOG_NAME), body)

    def test_unwritable_folder_still_reports_the_error(self):
        blocker = Path(self.temporary_directory.name) / "not-a-folder"
        blocker.write_text("x", encoding="utf-8")
        with mock.patch.object(app, "data_dir", return_value=blocker / "data"):
            self.fail("cannot write")

        body = self.show_error.call_args.args[1]
        self.assertIn("cannot write", body)
        self.assertIn("could not be written to disk", body)


if __name__ == "__main__":
    unittest.main()
