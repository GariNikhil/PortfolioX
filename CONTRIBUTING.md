# Contributing to PortfolioX

Thanks for your interest in contributing to PortfolioX — a local desktop
portfolio ledger for Indian equity investing.

PortfolioX is a personal project maintained by Gari Nikhil
(@GariNikhil / GariNikhilGari). Contributions are welcome, but please keep
the project's scope and safety constraints in mind before opening a pull
request.

## How to contribute

### 1. Check the project scope first

PortfolioX is a **local desktop application** — it is not a web service,
does not execute trades, and does not store financial data online. Before
suggesting a feature, review:

* `docs/Architecture.md` — architecture constraints, including:
  * No order execution in the MVP
  * AI output must never be the source of truth
  * No broad rewrites of financial logic without tests and a migration plan
* `docs/code-review-phase1.md` — known constraints and review findings

If your proposal touches financial calculations, data import, or the storage
layer, it will need tests and a migration plan.

### 2. Open an issue first

Please open an issue to discuss your idea before writing code. This helps us
align on scope, approach, and whether the change fits the project.

### 3. Fork and branch

1. Fork the repository on GitHub.
2. Create a branch from `main`: `git checkout -b your-feature-name`
3. Make your changes.
4. Add or update tests for any new behavior.
5. Run the full test suite (see below).
6. Commit with a clear message and push to your fork.
7. Open a pull request against `main`.

## Development setup

```powershell
# Clone your fork
git clone https://github.com/GariNikhil/PortfolioX.git
cd PortfolioX

# Create a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
python -m pip install -r requirements.txt

# Run the test suite
.venv\Scripts\python.exe -m unittest discover
```

The project targets Python 3.13+. The full suite should report `Ran 487 tests`
`OK` (or the current count as tests are added).

## Financial data safety

**Never commit real financial data.** The following must never be tracked in
git:

* `data/` — live portfolio database
* `referance/` / `referance notes/` — broker statements, contract notes, ledgers
* `backups/` / `exports/` — generated reports
* `.env*`, `.pem`, `.key`, `.p12` — secrets and keys
* `*.bundle`, `*.log` — backups and logs

These paths are in `.gitignore`. Test fixtures use clearly fake/synthetic data
only.

## Pull request guidelines

* Keep PRs small and focused on one change.
* Include tests for new or changed behavior.
* Update documentation if your change affects users.
* Do not include secrets, personal data, or local file paths.
* Ensure the test suite passes before requesting review.

## Code of conduct

This project adheres to the [Code of Conduct](CODE_OF_CONDUCT.md). By
participating, you agree to abide by its terms.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License that covers this project.
