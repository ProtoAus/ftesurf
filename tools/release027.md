# 0.1.27 — download with surf_boreas (P783-P791) and the 18 Oct features

Released **0.1.27+b89.p785** at 2026-10-18T13:05Z (built 13:01:17Z), requested by
Lex. Build stays 89. No overrides. Lobbies were not restarted.

## Sources

- QC `0e711082` = main `5ae3e780` plus the shipguard deny below.
- Engine `70d794dd3` (tag `patch-783`). ENGINE.txt's pin `7d3db9ccd` and engine
  main `b18c4b48f` differ from it only in `ENGINE_PATCHES.md`. The receipt's
  `p785` is that file's top heading at this commit: a label, not a code change.
- Native Windows products reused from the `-Full` restamp build
  (`git-7448-patch-783-0-g70d794dd3`): exe `e19f681d`, hl2 `de079afd`, imgui
  `58385607`; gate 3 matched all three against `engine\release`. The Linux drop
  was built at the same commit, and all 10 gates pass. Its stamp names
  `patch-782-2`, with the same count and commit as the Windows stamp.
- Launcher `646c8d1`, unchanged since 0.1.26.

## What the preview caught

- `data/friends_toasted.txt` (P788): runtime state with no shipguard entry.
  It is denied in `0e711082`.
- A fresh worktree has no `src/fteqcc64.exe`, since it is gitignored. It was copied
  from the checkout; hash `7ccb93d1`, the same compiler 0.1.26 used.
- A fresh worktree also lacks the ignored generated inputs. They were copied from
  `C:\FTESurf`: `data/*.txt`, `particles/`, `gfx/mapthumbs`, `gfx/thumbnails`,
  and `maps/zones/local` (648 files, none changed since 0.1.26). `mapwr.txt` was
  regenerated read-only from the Pi's database: 1,167 rows, up from 740.
  All hashes are in the root's `generated-inputs.sha256`.

## Checks

- 0 warnings in all three QC builds. Gates 1-4 pass, and so do the Linux gates.
- Windows `.7z`: 40.7 MB, sha256 `91D0E113...03C7F3`.
  Linux `.tar.xz`: 40.6 MB, sha256 `60E1C25E...AFC50`.
  Both rehash after a full CDN download; all 760 signed objects round-trip;
  the page and feed are byte-exact and served no-cache.
- `release_smoke.py`: new launchers installed fresh from public HTTPS.
  Windows rehashed 850 files and Linux 847, and 3 sentinels were kept on each.
  No game was launched.
- The 0.1.26 launchers, unmodified, installed 0.1.27 from the live feed
  (`--yes --no-launch`, exit 0, VERSION.txt 0.1.27). Existing players need no
  new launcher this time.
- Shipped `qwprogs`/`csprogs` match the lobbies' (`fa94eb5d`/`75b75a77`).
  `menu.dat` differs from the installs' by one byte, the version string.
- Lobbies: all 12 units active since 12:36Z, and all 12 answered `status`.

`test_shipguard` has 2 errors on main (`self.root` is unset in `setUpClass`).
They come from `bf64f45a`, not this release.

Owned root: `C:\FTESurf-worktrees\release-0127-20261018T124954Z\` (OWNER.md).
Retained as evidence. `launcher/target/ftesurf-linux/cargo-home/registry` is a
link into the shared Cargo registry: unlink it before removing the root, and never
delete it recursively.
