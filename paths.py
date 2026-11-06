"""Where PortfolioX keeps the files it reads and writes at runtime.

Two ways of running the app exist, and they disagree about ``__file__``:

* from source, the project root is the folder holding ``app.py``;
* from a PyInstaller build, the modules live in a bundled (and temporary)
  folder, so ``__file__`` points somewhere that is deleted on exit.

The database, the password vault and the book cache must outlive a run,
so they are always resolved from :func:`app_root` instead of from a
module's own path. In a frozen build that is the folder holding the
executable, which also lets a user move the whole folder without
breaking their data.

``PORTFOLIOX_HOME`` overrides the root. It exists so a build can be
tested against a scratch folder instead of the real portfolio data.
"""

import os
import sys
from pathlib import Path

# Environment variable that relocates every writable folder at once.
HOME_ENV = "PORTFOLIOX_HOME"


def app_root():
    """The folder that holds ``data``, ``backups``, ``exports`` and ``referance``."""

    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def data_dir(root=None):
    """The folder holding the database, the vault and extract caches."""

    return Path(root or app_root()) / "data"


def books_dir(root=None):
    """The personal bookshelf. Gitignored, and never bundled into a build."""

    return Path(root or app_root()) / "referance" / "books"
