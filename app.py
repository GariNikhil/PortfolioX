from database.schema import ensure_schema
from ui.main_window import PortfolioX


def main():
    """Create or migrate the database, then open the main window."""

    # Idempotent: guarantees a current schema exists on first run or a fresh
    # machine, and migrates an older (v1) database in place.
    ensure_schema()
    app = PortfolioX()
    app.mainloop()


if __name__ == "__main__":
    main()
