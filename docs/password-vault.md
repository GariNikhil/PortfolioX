# Password Vault (secure encrypted-file handling)

PortfolioX keeps broker passwords for encrypted files (contract-note PDFs,
encrypted statements) in a local encrypted vault, so imports run
automatically after each password has been provided **once**.

## How the once-only flow works

1. An import hits an encrypted file. The importer raises
   `security.vault.PasswordRequiredError` — this is *not* a failure; no
   audit entry is written and nothing is inserted.
2. The UI (or operator script) prompts the user for the password once,
   calls `vault.store_password(kind, password)`, and retries the import.
3. Every later import of similarly protected files resolves the password
   from the vault and runs with no user interaction.

`PasswordRequiredError` subclasses `VaultError`, so a UI can catch the base
class to handle any vault problem uniformly.

## Storage design

- **Vault file**: `data/vault.json` (inside the gitignored `data/` folder —
  it can never be committed). JSON entries carry `kind`, an optional
  `file_pattern`, the AES-GCM nonce, the ciphertext, and an `updated_at`
  timestamp. Plaintext passwords never touch disk.
- **Key**: a random 32-byte AES key. It never touches disk either — it is
  stored in the operating-system credential store (Windows Credential
  Manager) via the `keyring` package, service `PortfolioX`, account
  `vault-key`. The key is created on first use and reused afterwards.
- **Encryption**: AES-256-GCM (`cryptography` package) with a fresh 12-byte
  nonce per entry. GCM's auth tag means a wrong/lost key fails loudly
  (`VaultError`) instead of returning garbage.

## Password resolution order

`vault.password_for(path, kind)` tries, in order:

1. an entry with matching `kind` **and** a `file_pattern` that matches the
   file name (fnmatch, e.g. `*5874818698*`),
2. the pattern-less entry for that `kind` (the broker-wide default),
3. any pattern entry that matches the file name regardless of kind.

This lets one broker-wide password coexist with per-file overrides.

## Threat model, stated plainly

- Protects secrets **at rest** against casual disk access: the vault file
  is useless without the OS keystore entry.
- Does **not** protect against another process running as the same Windows
  user — such a process could read the keystore. That requires OS-level
  account security, not application code.
- Decrypted passwords exist as Python strings at runtime; Python cannot
  reliably zeroize memory. They are never logged, echoed, or written to the
  audit trail.

## Failure directions (by design)

- **Keystore entry lost** (Credential Manager wiped, different Windows
  account): decryption raises `VaultError`. Re-enter the passwords once;
  a new key is generated and the old ciphertext entries are replaced on
  the next `store_password` call.
- **Vault file corrupted**: `VaultError` with a readable message. Re-enter
  passwords once.

## API summary

| Function | Purpose |
|---|---|
| `store_password(kind, password, file_pattern=None)` | Encrypt + store/replace one entry |
| `get_password(kind)` | Pattern-less entry for a kind, or `None` |
| `password_for(path, kind)` | Full resolution order for one file |
| `delete_password(kind, file_pattern=None)` | Remove entries |
| `list_entries()` | Metadata only — no secrets |
| `status()` | Health report for a settings page (backend, key, entry count) |

## Tests

`security/test_vault.py` stubs the keyring seam with an in-memory dict and
points `VAULT_PATH` at a temporary file, so tests never touch the real
Windows Credential Manager. `importers/test_pdf_note.py` exercises the full
encrypted-PDF → vault → automatic-import flow with a pypdf-encrypted
fixture.
