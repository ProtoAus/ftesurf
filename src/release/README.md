# Prepare once, publish the verified bytes

This workflow is **release-only**. Ordinary feature work still uses `src/build.ps1`
and the relevant small falsifier; it does not build launchers, pack distributions,
run public-download checks or wait for release gates.

Use clean, inspected QC/engine/launcher commits in owned worktrees; see the
**Agent workspace lifecycle**, **Build**, **Linux build, test rig and release**,
**ship set allowlist**, and **Pi operations** sections of `AGENT_NOTES.md` first.
Do not ship another session's dirty source or overwrite an active player's install.

## 1. Cheap preflight before any compiler

From the selected QC checkout:

```powershell
pwsh -NoProfile -File src/release/release.ps1 -PreflightOnly -Bump patch
```

This checks declared release paths against the signed-update disk policy and
checks the template against the **actual receipt renderer's** Windows/Linux
maps. It selects the target version, but does not compile, stage, pack, sign,
write `VERSION`, probe R2 or contact the server. It is not build acceptance.

## 2. Prepare exactly one candidate

`PATCHNOTES.md` needs a `## next` section: the preflight refuses without one, and the
render names it this version in the page's `patchnotes.json` (P876).

Map media next (P1098): `python tools/mapmedia_refresh.py --atlas --export <release worktree>`
packs thumbnails fetched since the last release into a new atlas page and copies
`data/mapmeta.txt`, `data/mapdeps.txt` and `gfx/mapthumbs/` into the worktree, which the
ship set reads them from. Exit 2 means the table was refused: read the log first.

Use the existing Linux builder for the engine pin when needed:

```powershell
pwsh -NoProfile -File tools/linux/build-linux.ps1 -Commit <engine-sha> -FteRoot <engine-worktree> -ExpectSonames
pwsh -NoProfile -File src/release/release.ps1 -Bump patch -DryRun -BuildNumber <current-qcbuild> -FteRoot <engine-worktree> -LauncherRoot <launcher-worktree> -Linux dist/linux-build -PreviousUpdateFeed <saved-live-update.json>
```

The saved prior envelope must be the real signed predecessor, not reconstructed
JSON. A first-ever feed uses `-FirstUpdateFeed` with both platforms. Windows-only
preparation also needs `-PreviousUpdateObjects` for every retained Linux object.

- `-Bump` implies a QC-only build. The selected version is passed as
  `-ReleaseVersion` **before compiling**; preview never edits source `VERSION`.
- `-Build` alone is now **QC-only**, isolated with `-NoDeploy -PassThru` and no
  automatic native rebuild. Use `-BuildEngine` when native inputs need rebuilding;
  this implies `-Build` and a full native restamp. Normal feature builds are unchanged.
- Windows `build.ps1 -Engine` binds the Windows-inspected Git revision/date as
  make arguments, so MSYS CRLF dirtiness and `.git` files need no manual environment
  hacks. Keep `-Full` for header/flag changes; releases request it automatically.
- The Linux wrapper honors that selected Git database/commit, including detached
  worktrees. Its temporary refs are compare-and-swap cleaned; a nonblocking lock
  covers only the shared mirror/chroot build interval, not other feature work.
- Default `-DryRun` retains the existing R2 write/access probe. `-Offline` skips
  those probes for a local preview; it is **not** a network sandbox for dependency
  setup/build tools. Neither preview publishes archives, launchers, site or feed.

Existing archive/stage comparisons, deny tripwires, source/engine gates, notices,
signing and full local object validation still run. A complete, override-free
preview prints an `ftesurf-<version>.prepared.json` path, its **trusted SHA256**,
and the exact promotion command. Keep that hash separately from an untrusted copy.
The receipt binds the exact archives/sidecars, local provenance, both standalone
launchers, site, signed feed, full referenced object store and trusted publisher
code. These local receipts may name a build machine: **do not upload them**.

## 3. Publish that candidate, not a second build

```powershell
pwsh -NoProfile -File src/release/release.ps1 -PublishPrepared <prepared.json> -PreparedSha256 <trusted-sha> -DryRun
pwsh -NoProfile -File src/release/release.ps1 -PublishPrepared <prepared.json> -PreparedSha256 <trusted-sha> -VerifyFull
```

The first command validates exact bytes and pinned signatures locally, without
compiler/packer/Cargo/signing key or remote mutation. The second uses those same
bytes. It never chooses a version or rebuilds, repacks, rerenders or resigns.
Later source HEAD changes do not relabel the candidate; `-Tag`, if requested,
creates the tag at its frozen QC commit, not current HEAD. The original inspected
publisher tooling **bytes** must still match; use that tool version to publish.

Do **not** repeat `-Bump -DryRun` or run the old build command again after a passing
preview. An existing sealed candidate refuses that rebuild. Preserve failed
transactions, diagnose the actual seam, then retry exact-candidate publication.
No stale-prior, signature, object-roundtrip, ownership or no-overwrite checks are
waived. Publication still checks current R2/HTTPS bytes and rechecks the **actual
live predecessor under the server publication lock**. `-SkipUpload` still verifies
the remote objects; it is not a proof bypass.

All candidate paths are relative to its receipt folder: it can move without source,
Cargo cache or stages. Keep **every indexed file and sealed tree**. Reparse points,
extra files, missing/modified bytes and substituted publisher code refuse. Do not
put logs or bytecode in sealed trees. Fresh local/remote proofs and downloads live
in `publication-<version>-<seal-prefix>/`, outside the immutable graph.
Override or archive-only controls are local previews, not promotable releases.

## 4. Default-HTTPS acceptance without starting a game

Publication prints this command with the trusted local receipt hash filled in:

```powershell
python tools/release_smoke.py --receipt <ftesurf-version.json> --receipt-sha256 <hash-from-prepared-index> --work-root <owned-task-root>/public-smoke
```

This downloads the canonical live metadata/feed and standalone launchers, binds
them to the local verified receipt, and runs the actual Windows/WSL Linux launchers
with `--yes --no-launch` in **fresh synthetic installs**. It rehashes all non-overridden
managed files against the pinned signed feed and checks settings/data/edited-zone
sentinels. No alternate manifest URL, insecure mode, game process, owner install
or player data is used. Keep its proof/logs; retire only its verified disposable
payloads. A failure after promotion means **published but not accepted**, not a
silent rollback or permission to mint another version. Visual/play acceptance is
separate and may use a small owner check recorded in `lextest.md`.

After successful publication/acceptance, record the released `VERSION` and UTC
provenance in the source release commit, and add `## <version> <yyyy-mm-dd>` to
PATCHNOTES.md under the patches that shipped (the sealed `site-<v>/patchnotes.json`
lists them; any added to `## next` since stay above it). The next preflight refuses
a missing heading. Promotion itself does not edit a possibly advanced working tree. Do not bump qcbuild without the owner's Build NN decision.
Tooling-only maintenance is not a new product patch, version or public release.

## Version-pinned public metadata

The site snippet exposes retained, already-published metadata at:

```text
https://proto.bar/ftesurf/releases/<version>/version.json
https://proto.bar/worldofsurf/releases/<version>/version.json
```

These GET/HEAD routes serve only `version.json` from the numeric version's
retained site directory, not the rolling `static` link or neighboring files.
Successful responses are immutable-cacheable; missing future versions are not.
Signed-feed release directories are retained by `publish.sh`. Pruned legacy
versions remain 404: this does not reconstruct missing history or establish
signatures/source provenance that old metadata never carried.

Only the sanitized public site metadata belongs here. Never copy local full
release/prepared receipts into the public tree to backfill a missing version.
Installing the snippet is separate from preparing/publishing a release and still
requires the normal administrator config check/reload. Tooling source/tests do
not prove that the public route has been installed.

## Maintenance acceptance — 2026-10-16

- Actual local preparation compiled the selected 0.1.27 menu with zero QC warnings
  while source VERSION stayed 0.1.26, compared both archives to their stages,
  verified 760 signed objects and sealed 795 files. It reused read-only, previously
  verified P738 native/Linux inputs; this was not a new public release.
- That exact candidate moved to a source/cache-free courier folder. After source
  HEAD advanced, the real prepared-only entrypoint passed with source VERSION
  absent and PATH exposing only Python plus denial shims. Only Python ran;
  there was no compiler, packer, signing or remote mutation. VERSION was restored.
- Separate native Windows/Linux builds verified automatic metadata and all ten
  Linux production gates; the real NoDeploy regression preserved 70 witnesses.
  Windows retained the same 74 baseline compiler warning headers, zero new.
- The new canonical-HTTPS smoke accepted live 0.1.26: Linux 847 and Windows 850
  non-overridden signed file hashes and three protected sentinels per platform,
  actual launchers, no game launch. In-game/visual acceptance was not claimed.
