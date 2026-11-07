"""Where PortfolioX keeps the files it reads and writes at runtime.

Three ways of running the app exist, and they disagree about ``__file__``:

* from source, the project root is the folder holding ``app.py``;
* from a PyInstaller build, the modules live in a bundled (and temporary)
  folder, so ``__file__`` points somewhere that is deleted on exit;
* from a pip install, ``__file__`` points into site-packages, which is
  usually read-only and is replaced whenever the package is upgraded.

The database, the password vault and the book cache must outlive a run,
so they are always resolved from :func:`app_root` instead of from a
module's own path. In a frozen build that is the folder holding the
executable, which also lets a user move the whole folder without
breaking their data. A pip install keeps its data in the per-user folder.

``PORTFOLIOX_HOME`` overrides the root. It exists so a build can be
tested against a scratch folder instead of the real portfolio data.
"""

import os
import sys
from pathlib import Path

# Environment variable that relocates every writable folder at once.
HOME_ENV = "PORTFOLIOX_HOME"

# Folder name used under %LOCALAPPDATA% by a pip-installed copy.
APP_NAME = "PortfolioX"

# Folder names that mean "this code was imported from an installed package".
_INSTALL_FOLDERS = {"site-packages", "dist-packages"}


def _installed_root():
    """Writable per-user folder for a copy imported from site-packages."""

    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local).expanduser().resolve() / APP_NAME
    return Path.home().resolve() / ".local" / "share" / APP_NAME


def app_root():
    """The folder that holds ``data``, ``backups``, ``exports`` and ``referance``."""

    override = os.environ.get(HOME_ENV)
    if override:
        return Path(override).expanduser().resolve()

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    here = Path(__file__).resolve().parent
    if _INSTALL_FOLDERS & {part.lower() for part in here.parts}:
        return _installed_root()

    return here


def data_dir(root=None):
    """The folder holding the database, the vault and extract caches."""

    return Path(root or app_root()) / "data"


def books_dir(root=None):
    """The personal bookshelf. Gitignored, and never bundled into a build."""

    return Path(root or app_root()) / "referance" / "books"
