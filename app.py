"""Application entry point."""

import traceback
from datetime import datetime

from database.schema import ensure_schema
from paths import data_dir
from ui.main_window import PortfolioX

ERROR_LOG_NAME = "startup-error.log"


def report_startup_failure(error):
    """Record a startup crash on disk and show it in a dialog.

    A frozen build runs with ``console=False``, so an exception during
    ``ensure_schema()`` or window construction would otherwise close the
    process without a word. The traceback goes to ``data/startup-error.log``
    (append-only, so repeated launches keep their history), and a message
    box names the file. Both steps are best-effort: if the log cannot be
    written or tkinter cannot open a dialog, the original error is still
    what the caller sees.
    """

    folder = data_dir()
    log_path = folder / ERROR_LOG_NAME
    trace = "".join(
        traceback.format_exception(type(error), error, error.__traceback__)
    )

    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"\n=== {datetime.now():%Y-%m-%d %H:%M:%S} ===\n")
            handle.write(trace)
    except OSError:
        log_path = None

    if log_path is None:
        details = "The error details could not be written to disk."
    else:
        details = f"Details were written to:\n{log_path}"

    try:
        from tkinter import messagebox

        messagebox.showerror(
            "PortfolioX could not start",
            f"PortfolioX could not start.\n\n{error}\n\n{details}",
        )
    except Exception:
        # No display, or tkinter already torn down: the log is the fallback.
        pass


def main():
    """Create or migrate the database, then open the main window."""

    # Idempotent: guarantees a current schema exists on first run or a fresh
    # machine, and migrates an older (v1) database in place.
    try:
        ensure_schema()
        app = PortfolioX()
        app.mainloop()
    except Exception as error:
        report_startup_failure(error)
        raise


if __name__ == "__main__":
    main()
