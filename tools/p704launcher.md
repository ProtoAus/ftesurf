# P704 — small logo-only Windows launcher, detached launch and dev guard

## Scope / source

Launcher product source: ProtoAus/Quakers-Launcher, based on inspected main
`2b1376d8e0f81dc444291cad952d10d6a43121a3` (P696). That source already removed
the wave and centered the full-width logo; the installed 13.38 MB P694 preview
was stale. P704 changes only startup policy/handoff and documents the correct
release build. Engine product code/pin/tag, QC Build, public version/feed, player
settings/data and fleet are unchanged.

- Source checkouts with a `.git` directory or worktree file skip public release
  updates, including saved consent/--yes/--enable-updates/--verify. Saved permission
  is not rewritten. Incomplete bootstrap/in-game update transactions fail closed
  before launch rather than promoting release files into development source.
- Windows successful game spawn returns immediately with DETACHED_PROCESS and
  CREATE_NEW_PROCESS_GROUP, null standard handles, exact forwarded args and CWD.
  A standalone or Explorer batch console closes; an existing interactive shell
  is never killed. Spawn failure remains an error; later game exit/crash status
  is no longer attributed to the launcher. Non-Windows handoff stays unchanged.
- Use `cargo build --release --locked --bin ftesurf-launcher`, not target/debug.
  The existing optimized/LTO/stripped profile yields **3,583,488 bytes** versus
  **13,379,584** (73.2% smaller), without removing TLS/signature checks/dependencies.

## Verification

- Windows `cargo test --release --locked --offline --lib -- --test-threads=1`:
  **42 passed**, zero failures; optimized build, zero new warnings. Existing UI
  test acts on logo-only/full-width centering and compact layout. Plain preview
  inspected; no illustration. LSP reports no recorded diagnostics (not a build
  or Windows acceptance substitute).
- `tools/test_launcher_dev_handoff.py`: `.git` file AND directory, saved opt-in,
  --yes/--enable-updates/--verify make **zero loopback HTTP requests** and preserve
  executable/consent bytes. Pending bootstrap/in-game sentinels ACT refusals.
  Non-source player control requests once and refuses an unsigned feed.
- Native hidden-console input sends real Enter. The old installed launcher ACTS
  waiting for a persistent synthetic actor. New direct AND actual ftesurf.bat
  launches exit0, close their unique console window, and keep the actor alive
  without a console; forwarded args (including a space) and CWD match exactly.
  Invalid executable spawn is refused. No existing player game/terminal is killed.
- Full `tools/test_update_launcher.py` suite passes against the final optimized
  binary: signed update/repair, invalid signatures/versions, held locks, whole
  recovery preflight, corrupt ledger/object, linked metadata/junctions, in-game
  pending recovery and offline fallback retain their existing behavior.
- `tools/test_reccheck.py`: **306 checks, 0 failed**. No evidence/reader semantics
  changed and no live recording corpus was opened/rewritten by these tests.
- Harness history retained separately: compiler initially lacked its private bin
  directory on PATH; baseline initially omitted its launch Enter; batch first-run
  lacked an opt-out fixture and paused before launching. These are not passes.
  Corrected fresh final matrix is independent, with owned child-process cleanup.

## Windows installation / dev recovery

The accidental updater changed six primary product binaries. For each, its
updater `previous/` bytes exactly match the untouched second install and the
independent earlier delivery receipts:

| Artifact | Verified development SHA256 |
|---|---|
| ftesurf64.exe | 51e1109faea5d0fee6aa96720d9dbabc5628650e93ffa928479f2b7e7d8ece4c |
| fteplug_hl2_x64.dll | b4734c83cf7c8a19726f9709af8dbd6a37802242cef2a28a97529168553e122c |
| fteplug_ui_imgui_x64.dll | c776331b3564f1f5012be50a9671be370210690d82e9f83a5bb7261377a47233 |
| ftesurf/csprogs.dat | a6ce950d7c61d14e4198fc4182227f6b2c86a26309ac835b4e25234d84a7c072 |
| ftesurf/qwprogs.dat | 890fb0a08798d1d29b76c1aba31e32080cd8d273c3e8fe74f4061f7d31e25f94 |
| ftesurf/menu.dat | b07df1f95ba71db09ebbb0b35a6989a1e1597388a03466f313b9eae649eeb198 |

Windows disk delivery **PASS**: the optimized launcher from inspected product
commit `4a002784eee05c208ba5f6336270d15e42318be9` is installed at
`C:/FTESurf/ftesurf-launcher.exe`, SHA256
`29d3d87ee9c1e5bccdfd73cdb69410a252688265ed39e26f0f1bfd148f26d791`.
The exact six-file development set above is restored in the primary install and
matches the unchanged second install. No owner engine/launcher was active at
promotion; the normal install lock was held. Displaced public binaries and old
launcher are retained under unique same-directory `.pre704-20261014T140310Z`
names and immutable artifact backups, not destroyed. Existing `.prev` backups
and updater metadata are unchanged. The real installed launcher `--yes
--no-launch` probe exits0 and acts on the development-checkout guard without
network/game launch. This proves installed disk bytes, not an owner's new game
session or fresh native engine acceptance.

Installation and recovery are separately recorded in the owned task root
`C:/FTESurf-worktrees/launchfix-20261014T140310Z/`. Recovery must guard the entire
six-file set and hold the normal install lock before any promotion; an active
game/lock is a blocker, never permission to kill it. Preserve displaced public
bytes and existing backups. Only the launcher belongs at the primary Surf
entrypoint; the second install's `fteqw64.exe` is the untouched matching control,
not renamed/copied to masquerade as an archive bootstrap install. No owner cfg,
installed.lst, generated text, updater ledger, player data or Pi changes.

Limits: no official release/archive/feed publication, Linux runtime or physical
desktop/game-start acceptance. Hidden native Windows consoles and synthetic
actors prove process/window lifetime without starting the owner's real game.
