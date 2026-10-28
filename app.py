from database.schema import ensure_schema
from ui.main_window import PortfolioX

if __name__ == "__main__":
    # Idempotent: guarantees a current schema exists on first run or a fresh
    # machine, and migrates an older (v1) database in place.
    ensure_schema()
    app = PortfolioX()
    app.mainloop()
