# PortfolioX

PortfolioX is a local desktop portfolio ledger for Groww and Indian equity investing. It is designed to keep portfolio data on the user's computer while providing a foundation for trade imports, holdings calculations, dividend tracking, and reports.

## Project status

The project currently contains:

- A Phase 1 CustomTkinter application shell.
- Sidebar navigation for Dashboard, Import, Holdings, Transactions, Reports, and Settings.
- Placeholder pages for the areas that will be implemented in later phases.
- A local SQLite database layer with database helpers, schema, and manager functions.
- A tested holdings calculator for BUY and SELL transactions using moving weighted-average cost.
- A roadmap in [`phases.md`](phases.md).

The Groww import workflow, FIFO and tax calculations, live portfolio values, and finished reports are not complete yet. The holdings calculator is not a FIFO or tax calculation. The current UI is intentionally a basic shell; professional UI polish is planned for a later phase.

## Technology

- **Language:** Python 3.13+
- **GUI:** CustomTkinter
- **Database:** SQLite
- **Spreadsheet support:** openpyxl and pandas (planned/import workflows)
- **PDF parsing:** pdfplumber (planned)
- **Charts:** matplotlib (planned)
- **Packaging:** PyInstaller (planned)

PortfolioX is intended to work locally without login, cloud storage, subscriptions, or external services. Internet access may be added later as an optional source for market prices.

## Requirements

- Windows or another platform supported by Python and Tkinter.
- Python 3.13 or newer.
- CustomTkinter installed in the active Python environment.

The project may include a virtual environment at:

```text
.venv
```

Run the commands below from the project root. On Windows, use the virtual environment's Python executable shown below.

## Run the application

From the project root:

```powershell
Set-Location "<path-to-PortfolioX>"
& ".\.venv\Scripts\python.exe" app.py
```

The application opens on the Dashboard. Use the sidebar to switch between the available pages.

If the virtual environment is not available, create one and install the GUI dependency:

```powershell
Set-Location "<path-to-PortfolioX>"
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install customtkinter
& ".\.venv\Scripts\python.exe" app.py
```

## Validate the source

Compile the application and its packages without starting the GUI:

```powershell
Set-Location "<path-to-PortfolioX>"
& ".\.venv\Scripts\python.exe" -m compileall -q app.py ui database
```

Run the database tests. They use temporary databases and do not modify your portfolio data:

```powershell
& ".\.venv\Scripts\python.exe" -m unittest discover -v
```

You can also import-check the Phase 1 UI modules without opening a window:

```powershell
& ".\.venv\Scripts\python.exe" -c "from ui.main_window import PortfolioX; print('PortfolioX imports successfully')"
```

## Folder structure

```text
PortfolioX/
├── app.py                    # Application entry point
├── phases.md                 # Development roadmap
├── readme.md                # Project documentation
├── ui/                       # CustomTkinter windows and pages
│   ├── main_window.py        # Main window and sidebar navigation
│   ├── theme.py              # Shared colors, fonts, and dimensions
│   ├── dashboard.py          # Dashboard page
│   ├── import_page.py        # Import placeholder page
│   ├── holdings_page.py      # Holdings placeholder page
│   ├── transactions_page.py  # Transactions placeholder page
│   ├── reports_page.py       # Reports placeholder page
│   └── settings_page.py      # Settings placeholder page
├── database/                 # SQLite connection, schema, and manager code
├── data/                     # Local portfolio database files
├── importers/                # Future Groww import logic
├── calculations/             # Future holdings, FIFO, and P&L logic
├── reports/                  # Future report generation
├── exports/                  # Generated exports
├── backups/                  # Local database backups
└── assets/                   # Application assets
```

## Data and privacy

PortfolioX stores data locally. The SQLite database is created at `data/portfoliox.db` under the project directory, regardless of the current working directory used to launch the app. Do not commit real tradebooks, contract notes, exported reports, or other sensitive financial files to source control.

## Development roadmap

The planned sequence is documented in [`phases.md`](phases.md):

1. Basic application shell.
2. Database layer.
3. Groww import system.
4. Holdings calculations.
5. FIFO profit and loss.
6. Market prices.
7. Dashboard data integration.
8. Transactions, holdings, and dividends UI.
9. Reports and exports.
10. Settings, backups, and reliability.
11. Professional UI foundation.
12. Testing and release.

Financial calculations should be treated as assistive information only and verified independently before being used for tax or investment decisions.