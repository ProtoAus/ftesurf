# 0.1.26 / P738 — alpha download and launcher publication

## Scope and approved rollout

Owner requested the latest committed download and launcher release. The original
public release was0.1.25/P687; the inspected source advanced through P736 and the
concurrently published P737 renderer correction. Build remains89.

The full preview caught two real omissions before any upload:

- P729's fixed-origin curated runtime zone cache needed a narrow documented
  shipguard classification. Published tooling commit2b7e941 fixes that; hiding
  shipped local zones still produces7 real misses.
- P723's shipped `ftesurf/maps/tiers.txt` was outside publisher, launcher and
  native managed-file policies. All three now permit EXACTLY that authored file;
  arbitrary maps, aliases and player data remain refused.

The owner explicitly approved requiring a new launcher download for alpha users.
The old P708 launcher actually rejects a correctly signed tier fixture before
installing it. This is an intentional rollout boundary, not backward-compatible
self-update. Existing users close game/launcher, replace `ftesurf-launcher.exe`
(or Linux `ftesurf-launcher`, executable) in the existing game folder, then run it.
The public page links verified standalone launchers; fresh archives include them.

## Frozen sources

- Engine `9c95128bb53a5513b869a7f5ec9592b18e33e67f`, annotated
  `patch-738-release`: merges already-published P737 and P738 source histories.
  Earlier published `patch-738` remains its original updater-source commit; no
  published tag/history is rewritten.
- Launcher `646c8d111fe0efd5e40697e195f05044034df2eb`.
- Product parent5cdfc89 includes P737's committed delivery notes. Product release
  source/receipt SHA is recorded by the release tool and completion update below.

## Acting checks

- Exact native C disk policy compiled with `-Wall -Wextra -Werror`: tier and
  existing assets accepted;12 neighboring/player paths refused. Removing the
  new entry acts and returns the expected rejection.
- Rust library42 tests and Python publisher13 tests pass. Signed tier object
  round-trips by hash; neighboring tier names/aliases remain unmanaged.
- New actual Windows launcher passes the complete existing integration suite,
  including tier installation, corruption repair, rollback/refusal, linked paths,
  held locks, interrupted recovery and protected sentinels. P708 is an acted
  negative control, not claimed compatible.
- Shipguard13 tests and missing-local-zone mutant pass. Release helper/template
  tests cover platform-specific standalone links and preserve legacy receipts.
- Merged actual renderer collector:4 Werror variants and acting controls pass;
  this does not replace the P737 human visual gate.
- Linux production entrypoint passes all10 gates at the frozen engine SHA,
  `git-7355-patch-738-release-0-g9c95128bb`.

## Build/publication evidence

Owned root: `C:\FTESurf-worktrees\publish-20261016T082323Z-0eaac\` (OWNER.md).
Original preview/unstamped/plugin failures are retained, not promoted. The final
Windows build uses the documented explicit worktree SVN_VERSION/SVNREVISION and
`src/build.ps1 -Engine -Full -NoDeploy -Jobs8`; Full is required after flag changes.
The release uses the normal `src/release/release.ps1 -Bump patch -DryRun` first,
then live entrypoint with full archive and signed-object round-trip verification.
Menu is compiled for target0.1.26 without changing qcbuild89.

Local Windows installs were independently changed to P737 by the concurrent
renderer task, with the owner's game active. They are NOT overwritten/stopped;
this release's public artifacts come only from clean isolated committed sources.
No NanoPi lobby restart, player/config/save write, or unrelated worktree cleanup.

## Completion

Publication and final public provenance pending the final full preview/live run.
