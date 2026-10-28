from database.schema import create_tables
from ui.main_window import PortfolioX

if __name__ == "__main__":
    # Idempotent: guarantees the schema exists on first run or a fresh machine.
    create_tables()
    app = PortfolioX()
    app.mainloop()
