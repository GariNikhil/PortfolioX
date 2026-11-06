"""Secure password vault for encrypted broker files.

Stores file passwords (contract-note PDFs, encrypted statements, ...) so
that imports run automatically after the password has been provided once:

1. The user enters a password the first time an encrypted file is imported
   (the importers raise PasswordRequiredError; the UI/script prompts).
2. The password is encrypted with AES-GCM and persisted to the vault file
   (data/vault.json, gitignored).
3. The AES key itself never touches disk: it is a random 32-byte key kept
   in the operating-system credential store (Windows Credential Manager
   via the `keyring` package). Losing the keyring entry means losing the
   vault contents, which is the correct failure direction for secrets.

Threat model and limitations, stated plainly:
- This protects secrets at rest against casual disk access (the vault file
  is useless without the OS keystore entry). It does NOT protect against
  another process running as the same Windows user, which could read the
  keystore — that requires OS-level account security, not application code.
- Decrypted passwords exist as Python str values; Python cannot reliably
  zeroize memory, so secrets are handled like any runtime string and never
  logged, echoed, or written to the audit trail.
- The vault file location and keyring access are module-level seams
  (VAULT_PATH, _keyring_get/_keyring_set) so tests never touch the real
  keystore.
"""

import base64
import json
import os
import secrets
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path

import keyring
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from paths import data_dir

# The encrypted vault lives beside the database, next to the executable
# in a frozen build (see paths.app_root).
VAULT_PATH = data_dir() / "vault.json"

KEYRING_SERVICE = "PortfolioX"
KEYRING_ACCOUNT = "vault-key"

_NONCE_BYTES = 12
_KEY_BYTES = 32
_VAULT_VERSION = 1


class VaultError(Exception):
    """Raised when the vault cannot store or retrieve a password."""


class PasswordRequiredError(VaultError):
    """Raised when an encrypted file needs a password the vault does not have.

    This is the UI's single prompt point: catch it, ask the user once,
    store the password with vault.store_password(), and retry the import.
    """


def _keyring_get():
    return keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)


def _keyring_set(password):
    keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, password)


def status():
    """Report vault health for the settings page (never includes secrets)."""

    try:
        backend = type(keyring.get_keyring()).__name__
    except Exception:  # pragma: no cover - backend listing is best-effort
        backend = "unavailable"
    try:
        entries = _load()["entries"]
    except VaultError:
        entries = []
    return {
        "backend": backend,
        "key_configured": _load_key() is not None,
        "vault_file": str(VAULT_PATH),
        "entries": len(entries),
    }


def list_entries():
    """Vault entries as {kind, file_pattern, updated_at} (no secrets)."""

    return [
        {
            "kind": entry["kind"],
            "file_pattern": entry["file_pattern"],
            "updated_at": entry["updated_at"],
        }
        for entry in _load()["entries"]
    ]


def store_password(kind, password, file_pattern=None):
    """Encrypt and store one password, replacing the same (kind, pattern)."""

    if not password or not str(password).strip():
        raise VaultError("password must not be empty")
    if not kind or not str(kind).strip():
        raise VaultError("password kind must not be empty")

    key = _load_key()
    nonce = os.urandom(_NONCE_BYTES)
    encrypted = AESGCM(key).encrypt(nonce, str(password).encode("utf-8"), None)

    vault = _load()
    vault["entries"] = [
        entry
        for entry in vault["entries"]
        if not (entry["kind"] == kind and entry["file_pattern"] == file_pattern)
    ]
    vault["entries"].append(
        {
            "kind": kind,
            "file_pattern": file_pattern,
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(encrypted).decode("ascii"),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _save(vault)


def get_password(kind):
    """The stored password for a kind (pattern-less entry preferred), or None."""

    entries = _load()["entries"]
    matching = [entry for entry in entries if entry["kind"] == kind]
    if not matching:
        return None

    def patternless(entry):
        return entry["file_pattern"] is None

    matching.sort(key=lambda entry: not patternless(entry))
    return _decrypt(matching[0])


def password_for(path, kind):
    """Password for one file: kind+pattern match, then pattern match, then kind.

    Resolution order lets a broker-wide password (no pattern) coexist with
    per-file overrides, and lets a pattern-only entry cover several files
    of the same kind.
    """

    name = Path(path).name
    entries = _load()["entries"]

    for entry in entries:  # most specific: kind AND filename pattern
        if entry["kind"] == kind and entry["file_pattern"] \
                and fnmatch(name, entry["file_pattern"]):
            return _decrypt(entry)
    for entry in entries:  # broker-wide default for the kind
        if entry["kind"] == kind and not entry["file_pattern"]:
            return _decrypt(entry)
    for entry in entries:  # any pattern entry that matches the file
        if entry["file_pattern"] and fnmatch(name, entry["file_pattern"]):
            return _decrypt(entry)
    return None


def delete_password(kind, file_pattern=None):
    """Remove entries for a kind (optionally only one stored pattern)."""

    def matches(entry):
        if entry["kind"] != kind:
            return False
        return True if file_pattern is None else entry["file_pattern"] == file_pattern

    vault = _load()
    vault["entries"] = [entry for entry in vault["entries"] if not matches(entry)]
    _save(vault)


def _load_key():
    """The vault AES key, creating (and keystore-storing) it on first use."""

    stored = _keyring_get()
    if stored:
        return bytes.fromhex(stored)

    key = secrets.token_bytes(_KEY_BYTES)
    _keyring_set(key.hex())
    return key


def _load():
    if not VAULT_PATH.is_file():
        return {"version": _VAULT_VERSION, "entries": []}
    try:
        vault = json.loads(VAULT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VaultError(f"vault file is unreadable ({VAULT_PATH}): {error}") from error
    if "entries" not in vault:
        raise VaultError(f"vault file is malformed: {VAULT_PATH}")
    return vault


def _save(vault):
    try:
        VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
        VAULT_PATH.write_text(
            json.dumps(vault, indent=2), encoding="utf-8"
        )
    except OSError as error:
        raise VaultError(f"could not write vault file {VAULT_PATH}: {error}") from error


def _decrypt(entry):
    """Decrypt one vault entry; a lost/mismatched key raises VaultError."""

    try:
        key = _load_key()
        nonce = base64.b64decode(entry["nonce"])
        ciphertext = base64.b64decode(entry["ciphertext"])
        plain = AESGCM(key).decrypt(nonce, ciphertext, None)
        return plain.decode("utf-8")
    except (InvalidTag, ValueError, KeyError) as error:
        raise VaultError(
            "stored password cannot be decrypted with the keyring key "
            "(the vault may have been created under a different OS account)"
        ) from error