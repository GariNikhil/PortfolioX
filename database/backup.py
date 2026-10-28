"""Automatic database backups taken before any import that can write.

The database uses the default rollback journal (no WAL), so a plain file
copy taken while no transaction is open is a consistent snapshot. Every
caller (CLI and UI) backs up before the first write attempt; a failed
import attempt that wrote nothing does not need a second backup.
"""

import shutil
from datetime import datetime
from pathlib import Path

from database import db

BACKUP_DIR_NAME = "backups"
KEEP_BACKUPS = 20


def backup_database(db_path=None, backup_dir=None, keep=KEEP_BACKUPS):
    """Copy the database file into the backup folder; return the copy's path.

    Returns None when the database file does not exist yet (nothing to
    protect on a fresh machine). Names are timestamped
    (portfoliox-YYYYMMDD-HHMMSS.db); a same-second collision gets a
    counter suffix. Older backups beyond `keep` are pruned.
    """

    source = Path(db_path or db.DB_PATH)
    if not source.exists():
        return None

    folder = Path(backup_dir) if backup_dir else source.parent / BACKUP_DIR_NAME
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = folder / f"{source.stem}-{stamp}{source.suffix}"
    counter = 1
    while target.exists():
        target = folder / f"{source.stem}-{stamp}-{counter}{source.suffix}"
        counter += 1

    shutil.copy2(source, target)
    _prune(folder, source.stem, source.suffix, keep)
    return target


def _prune(folder, stem, suffix, keep):
    """Delete the oldest backups beyond the keep limit."""

    backups = sorted(
        (path for path in folder.glob(f"{stem}-*{suffix}") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old in backups[keep:]:
        old.unlink()
