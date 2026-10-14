# Presentation publication (not a release)

`present.py` is a separate Linux/POSIX transaction for a **complete** static-site
presentation generation. It does not render, sign, upload, rebuild archives,
change release versions or prune history. Do not use the legacy `sitepage.ps1`
publication path for an existing immutable release. `publish.sh` and
`release.ps1` remain unchanged and authoritative for new signed releases.

## Caller preparation

An operator must explicitly authorize publication and prepare these ordinary,
nonlinked paths on the same filesystem:

- absolute site root, with existing `.publish.lock` (the release publisher's lock);
- `.incoming/` and `presentations/` directories;
- current `static` symlink targeting exactly `releases/MAJOR.MINOR.PATCH` or
  `presentations/<safe-generation>`;
- fresh `.incoming/<safe-generation>/` containing a complete copy of the current
  static tree, including every nested file. No symlinks, hardlinked files or
  special files. Generation IDs are 1–80 ASCII alphanumeric/underscore/hyphen
  characters, starting with an alphanumeric; destinations must not exist.

Save the exact predecessor pointer and a JSON dictionary of **every current
file's relative POSIX path to lowercase SHA256**, including `version.json`,
`update.json` and `update-verified.json`. `manifest(Path(...))` is the public
Python API for a local snapshot. Capture coherent source bytes and pointer
under `.publish.lock`; do not synthesize expected hashes from a modified
candidate or assume a public HTTP listing is a complete filesystem manifest.

Render `index.html` using existing PowerShell `Get-ReceiptTokens` and the exact
sanitized published receipt (for the current site, `version.json` 0.1.25), not a
new release receipt or missing local dist output. Preserve original receipt
and feed bytes. The only permitted changed/added paths are:

```
index.html                 anticheat.html              site.css
apple-touch-icon.png       favicon.svg                 og-worldofsurf.png
worldofsurf-192.png         worldofsurf-512.png          worldofsurf-wordmark.svg
```

All other existing files remain byte-identical; no files may be removed.
This is a path allowlist, not a content/privacy sanitizer: reviewed PUBLIC
presentation bytes are the caller's responsibility. Do not stage secrets.
Quiesce candidate writes and ensure **all publication writers honor the lock**.
The tool is not a defense against an adversarial local writer racing path
checks. Destination ancestors must already be traversable by nginx. Setup,
staging and manifest acquisition are outside this transaction.

## Transaction

```sh
python3 -B present.py --site /absolute/synthetic-or-approved-site \
  --generation brand-20261014 --expected-pointer releases/0.1.25 \
  --manifest /absolute/saved-current-manifest.json --dry-run
```

Remove `--dry-run` only after review/authorization. No SSH is performed by this
command. Dry run locks the existing lock read-only, checks all content/path and
predecessor gates, and writes no files or permissions. Actual publication:

1. Locks the same `.publish.lock`; verifies exact pointer and whole manifest.
2. Validates candidate types, mandatory index, token-free presentation text,
   explicit nine-file allowlist, unchanged protected bytes and no removals.
3. Sets directories 0755/files 0644, reads permissions back, and rechecks content
   and predecessor. DrvFS/no-op chmod fails closed; Linux `renameat2` is required.
4. Exclusively creates a unique temporary symlink; renames the complete candidate
   with `RENAME_NOREPLACE` to `presentations/<generation>`; rechecks content,
   predecessor and temporary-link ownership; atomically replaces `static` last.

The JSON result contains target, rollback pointer, file count and at most nine
changed-file SHA256s, not file contents. Errors produce a clear refusal on stderr
and nonzero exit. This preserves release history and prior presentation trees.
An error after the generation rename can leave an **unadvertised** immutable
presentation generation; do not retry that ID or delete it automatically.
Pre-swap errors leave the old pointer intact. No durability/fsync or protection
against external noncooperating writers is claimed.

Rollback is a separately authorized, locked atomic pointer replacement to the
returned `rollback_pointer`, after checking the current pointer and both trees.
Do not rerun a same-generation publish or reconstruct feeds for rollback. No
rollback/pruning command is added here.

A later ordinary release publisher reads prior feeds through `static` and moves
to a new `releases/<version>` pointer as before. Its pruning excludes feed-bearing
release directories. This tool retains every presentation; storage cleanup is
an owner decision, never part of publication. Legacy `sitepage.ps1` assumptions
are not repaired or silently invoked by this interface.

## Offline synthetic tests

```sh
python3 -B src/release/test_present.py --work-root /absolute/fresh-owned-test-root
```

Use a native Linux filesystem and publicly traversable synthetic ancestors;
mode/FIFO controls are not supported by ordinary DrvFS. The suite creates OWNER
before its fixtures, uses synthetic feed/receipt text only, and has no HTTP,
SSH, signing or runtime product dependency. Retire only the exact owned fixture
root after retaining results. Tests cover old/new pointer action, second
presentation/history preservation, nine-path success, stale pointer/feed/whole
manifest, concurrent guard/lock serialization, unknown/removal/receipt changes,
linked roots/ancestors/descendants/hardlinks/FIFO, tokens, existing and racing
immutable destinations, permission/setup/swap failures, dry-run nonmutation and
foreign temporary-link retention.
