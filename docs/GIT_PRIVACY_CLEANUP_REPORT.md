# Git Privacy Cleanup Report — PortfolioX

**Repository:** `D:\projects\Ongoing\PortfolioX`
**Remote:** `https://github.com/GariNikhil/PortfolioX.git`
**Branch:** `main`
**Date:** 2026-11-08
**Cleanup performed:** History rewrite via `git filter-repo` v2.47.0

---

## 1. Repository identification

| Item | Value |
|------|-------|
| Root | `D:\projects\Ongoing\PortfolioX` |
| Remote | `origin` = `https://github.com/GariNikhil/PortfolioX.git` |
| Branch | `main` only |
| Tags | None |
| Stash | None |
| Worktrees | One (the main working copy) |
| Commits before rewrite | 54 on `main`, 73 across all refs (incl. 19 cline-only) |
| Commits after rewrite | 55 on `main` (54 rewritten + 1 post-cleanup commit) |
| Tracked files before | 157 |
| Tracked files after | 153 (removed: `.opencode/`, `.clinerules/`, `build_log.txt`, `build_output.txt`, `bypass`) |
| `.git` size before | 11.2 MB |
| `.git` size after | 0.5 MB |

---

## 2. Backup locations

Two backups were created **before** any destructive operation. Neither overwrites the earlier 2026-11-07 backups.

| Backup | Path | Contents | Size |
|--------|------|----------|------|
| Git bundle (all refs) | `D:\projects\Ongoing\PortfolioX-pre-cleanup-2026-11-08.bundle` | Complete history (all refs, including cline checkpoints) | ~1.09 MB |
| Working-copy copy | `C:\Users\Gari Nikhil\PortfolioX-backup-2026-11-08` | Full working tree incl. `.git`, `data/`, `referance/`, `.opencode/`, docs; excludes `.venv/`, `build/`, `dist/`, caches | ~134 MB |

Pre-existing backups (untouched):
- `D:\projects\Ongoing\PortfolioX-pre-rewrite-2026-11-07.bundle` (~10.9 MB)
- `C:\Users\Gari Nikhil\PortfolioX-backup-2026-11-07` (~13.2 MB)

Release artifacts (verified, untouched):
- `dist\PortfolioX\PortfolioX.exe` (10.2 MB)
- `dist\PortfolioX-1.0.0-win64.zip` (~33 MB)

---

## 3. Excluded / removed from history

### Paths purged via `--invert-paths`

These paths were removed from **all reachable history** (every commit, every ref):

| Path | Reason |
|------|--------|
| `.opencode/` | Vendored AI skills bundle (4,462 files / 33 MB) plus agent workflow notes and local settings. Contained `.claude/claudex/log`, local `C:\Users\...` paths, placeholder tokens. |
| `.clinerules/` | Two AI-workflow docs (`cline-skills.md`, `project-workflow.md`) from the baseline commit. |
| `build_log.txt` | PyInstaller build log containing local build paths (added in `8a559e2`). |
| `build_output.txt` | Duplicate PyInstaller build log (added in `8a559e2`). |
| `bypass` | 88-byte PowerShell helper (`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` + venv activation) added in `8a559e2`. |

### Stale refs deleted (before rewrite)

| Ref | Notes |
|-----|-------|
| `refs/cline/checkpoints/1793270603388_o1hvl/1` | Local-only cline checkpoint |
| `refs/cline/checkpoints/1793500031096_ce4hm/1` through `/5` | Local-only cline checkpoints (5 refs) |

These were local-only (never pushed to GitHub). Deleting them removed 19 commits that existed only on those refs.

---

## 4. Sanitized blob content (via `--replace-text`)

| Pattern | Replacement | Location(s) |
|---------|-------------|-------------|
| `GAXXXXL7@GMAIL.COM` | `<email>` | `importers/test_axis_statement.py` (fixture header) |
| `XXXXXX0010` | `<mobile>` | `importers/test_axis_statement.py` (fixture header) |
| `XXXXXXXXXX0339` | `<ckyc>` | `importers/test_axis_statement.py` (fixture header) |
| `garinikhil5@gmail.com` | `<email>` | `ui/published_by_content.py` (historical blobs only); **restored as-is in current tree** (see §7) |
| `D:\projects\Ongoing\PortfolioX` | `<repo>` | `installer/PortfolioX.iss` (Source lines), `installer/convert_icon.py` |
| `d:\projects\Ongoing\PortfolioX` | `<repo>` | `installer/convert_icon.py` |

The fake PAN `ABCDE1234F` in the Axis test fixture was left unchanged (it is already clearly synthetic).

---

## 5. Sanitized commit messages (via `--replace-message`)

| Pattern | Replacement | Commits affected |
|---------|-------------|------------------|
| `<account-number>` (real bank account number) | `<account-number>` | `b31ec54`, `b021659`, `6c8c94c` (all rewritten) |
| `d:\projects\working\PortfolioX` | `<repo>` | `169cd4a` |
| `D:\projects\working\PortfolioX` | `<repo>` | `311b98b` |
| `🤖 Generated with [Claude Code](https://claude.com/claude-code)` | removed | 7 commits |
| `🤖 Generated with OpenCode` | removed | 1 commit (`48ad3f2`) |
| `Co-Authored-By: Claude <noreply@anthropic.com>` | removed | 8 commits |
| `Co-Authored-By: OpenCode <noreply@opencode.ai>` | removed | 1 commit (`48ad3f2`) |

Note: The real account number was already published in the original commit bodies before this cleanup. File-level sanitization does not retroactively erase it from GitHub caches, forks, or clones that existed before the force-push.

---

## 6. Author identity normalization (via `--mailmap`)

| Old identity | New identity | Commits |
|-------------|--------------|---------|
| `Gari Nikhil <gari.nikhil@local>` | `Gari Nikhil <GariNikhil@users.noreply.github.com>` | 9 commits |

All 55 commits on `main` now share the identity `Gari Nikhil <GariNikhil@users.noreply.github.com>`.

---

## 7. Comments reviewed / decisions

| Item | Decision | Rationale |
|------|----------|-----------|
| `ui/published_by_content.py` (name `Mudappagari Nikhil`, email `garinikhil5@gmail.com`, links) | **Kept as-is** | Intentional in-app "Published by" credit. Name is required attribution in `LICENSE`. User-approved. The email was scrubbed from historical blobs but restored in the current tree. |
| `ui/about_content.py` (historical, renamed to `published_by_content.py`) | Scrubbed from history | Only exists in pre-rename commits; its blob content was sanitized like all others. |
| `importers/test_axis_statement.py` identifiers | Scrubbed | Masked real email/mobile/CKYC replaced with `<email>`/`<mobile>`/`<ckyc>`. Test logic unchanged (uses `nikhil@example.com`, not real values). |
| `installer/PortfolioX.iss` | Rewritten | Absolute local paths removed; packages `dist\PortfolioX\*`; per-user `{localappdata}` install; lowest privileges; correct exe reference. |
| `installer/convert_icon.py` | Fixed | `d:\projects\...` hard-coded paths replaced with `Path(__file__).resolve().parent.parent`-relative resolution. |
| `.clinerules/` (2 AI-workflow docs) | Purged from history | Not project source; contained agent workflow notes. |
| `.opencode/settings.json` (live token, untracked) | Not in git; on disk only | Never tracked. **Recommend rotating the token regardless.** |

---

## 8. Branches and tags

| Item | Before | After |
|------|--------|-------|
| Local branches | `main` | `main` |
| Remote tracking | `origin/main` | `origin/main` (re-added after filter-repo removed it) |
| Tags | None | None |
| Deleted refs | 6 `refs/cline/checkpoints/*` | Gone (local-only, never on GitHub) |

All commit hashes on `main` changed due to the history rewrite. Anyone with an existing clone must `git fetch` and `git reset --hard origin/main` (or reclone) after the force-push.

---

## 9. Secrets (redacted)

| Secret | Status | Recommendation |
|--------|--------|----------------|
| Old `sk-...` API token | Removed from reachable history by prior rewrite; still in 2026-11-07 bundle | **Assume exposed — rotate/revoke.** Was published before the prior rewrite. |
| Live token-like value in `.opencode/settings.json` | Never tracked; on disk only | **Rotate.** Not in git, but present on disk. |
| Real bank account `<account-number>` | Scrubbed from commit bodies | **Already public.** Was in 3 commit bodies before cleanup. Monitor; assume exposed. |
| `sk-abcdefg…` / `sk-ant-aaa…` (vendored bundle) | Placeholder-only, not real | Purged with the bundle; no action needed. |
| Masked identifiers `GAXXXXL7@GMAIL.COM` / `XXXXXX0010` / `XXXXXXXXXX0339` | Scrubbed from blobs | Replaced with `<email>`/`<mobile>`/`<ckyc>`. |

---

## 10. Verification results

| Check | Result |
|-------|--------|
| Purged paths absent from all reachable trees | `.opencode/`, `.clinerules/`, `build_log.txt`, `build_output.txt`, `bypass` — all confirmed absent |
| Sensitive patterns absent from blobs | `<account-number>`, `GAXXXXL7@GMAIL.COM`, `XXXXXX0010`, `XXXXXXXXXX0339`, `D:\projects\`, `d:\projects\` — all absent |
| AI trailers absent from commit messages | `🤖 Generated with`, `Co-Authored-By: Claude`, `Co-Authored-By: OpenCode` — all removed |
| Author email normalization | All 55 commits: `Gari Nikhil <GariNikhil@users.noreply.github.com>` |
| Test suite | `Ran 487 tests` / `OK` (PyInstaller build smoke tests also previously passed) |
| `git fsck --full` | Clean (no dangling, missing, or corrupt objects) |
| `git gc --prune=now` | Complete; pack reduced from 11.03 MiB to 405.78 KiB |
| Physical data directories intact | `data/`, `referance/`, `backups/`, `exports/`, `.opencode/` — all present on disk |
| `.gitignore` hardened | `.opencode/`, `.clinerules/`, `.cline/`, `.claude/`, `.codex/`, `.gemini/`, `.cursor/`, build logs, `/bypass`, `installer/Output/`, `*.log`, `*.bundle`, `.env*` (with `!.env.example`), Python caches, IDE state, OS files |

---

## 11. GitHub status

**No force-push has been performed.** The local `main` is now 55 commits with entirely new hashes, diverging from `origin/main` (`f9cf27b`).

The planned command (pending separate user approval):

```
git push --force-with-lease=refs/heads/main:f9cf27b8c9d662b5647ad4b4bb5c201ef0e865ce origin main
```

This will **not** use plain `--force`. `--force-with-lease` ensures no remote changes are overwritten if `origin/main` has advanced.

### After force-push, collaborators must:
- Reclone, or
- `git fetch origin && git reset --hard origin/main`

---

## 12. Remaining exposure risks

1. **GitHub caches / PR refs:** Force-push rewrites `main` but GitHub may retain old objects in cached packfiles, pull request refs, or the events API. This is not fully controllable.
2. **Forks and clones:** Any existing forks or clones retain the old history. Force-push does not affect them.
3. **Old backups:** The 2026-11-07 bundle and working-copy backup contain pre-cleanup data including the real bank account number and old token. These are intentional safety backups and should be deleted only after confirming the cleanup is satisfactory.
4. **Real bank account (`<account-number>`):** Was published in 3 commit bodies before this cleanup. Scrubbing from git history does not undo prior publication. Treat as exposed and monitor.
5. **`.opencode/settings.json` (untracked, live token):** Never in git, but present on disk. Rotate the token.
6. **`ui/published_by_content.py`:** Contains real name and personal email by design (intentional published-by credit). This is in the current tree and will be pushed to GitHub.

---

## 13. Manual actions for the user

1. **Rotate** the old `sk-...` API token (was published before the prior rewrite).
2. **Rotate** the token-like value in `.opencode/settings.json` (untracked, on disk).
3. **Decide whether to delete** the 2026-11-07 backups after confirming the cleanup is satisfactory.
4. **Review and approve** the GitHub force-push (separate approval required). The command is in §11.
5. **Notify collaborators** to reclone or reset after the force-push.
6. **Monitor** for the real bank account number (`<account-number>`) in case it appears in caches or forks.

---

## 14. Commits in rewritten history

The 54 rewritten commits (plus 1 post-cleanup commit) are all attributed to `Gari Nikhil <GariNikhil@users.noreply.github.com>`. Full list available via `git log --oneline HEAD`. Key rewritten commits include the 8 that previously carried AI attribution trailers and the 3 that contained the real bank account number in their bodies.
