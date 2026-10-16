# P733 — unobtrusive update corner and real F2 binding repair

Claim: fetched both repositories and inspected patch headings plus untracked
pNNN claims across their worktrees: maximum732, so claim733 (2026-10-16 UTC).
QC base a0a040749ee3eedaf2340b22f90d1a9db69d93f2; engine documentation base
826f0e988368f560bd0aebfd23519b67365895b1. No native source/pin/tag change or
QC Build-number decision. No Friends/backend/protocol/evidence change.

## Problem / change

Remove the top-right rounded fill entirely. All three status/version lines now
share the same right edge,16 virtual units from the screen edge; text still
fits/truncates within320 units. F2's hint appears only for available, launcher,
or restart states with enabled consent, the menu-only trusted builtin present
and the actual F2 binding matching ui_updates. Current/checking/error/off and
in-progress states have no F2 prompt. Custom player bindings are preserved.

P731 created `bind F2 ui_updates` via ordinary menu localcmd, which runs at
RESTRICT_INSECURE30. keys.c skips Menu_InputEvent for F1..F15 and executes the
stored bind level; pr_menu.c then refuses insecure menu console commands. The
physical key therefore did nothing, despite P731's synthetic ui_key test
calling Menu_InputEvent directly and passing. This corrects that verification
limit; the old test now explicitly calls itself a QC-handler/binding-text test.

Use the existing menu-only localcmd_local builtin for the fixed literal bind,
and repair exactly empty, stock menu_save, or ui_updates bindings, including
already-persisted level30 ui_updates. No arbitrary text or remote VM gains a
trusted route. Do not weaken MP_ConsoleCommand/Cmd_IsInsecure or edit the owner's
saved config. Normal menu initialization queues the correction in memory.

## Verification

Evidence root: C:/FTESurf-worktrees/menu-20261016T015008Z/.
`src/build.ps1 -Jobs 8 -NoDeploy`: all three VMs zero warnings (build-corner-second).
Native-rendered product menu: rig/build-nodeploy-ae9c668368c04bafabf00c280158a158.

`tools/test_update_corner.py` final run: artifacts/update-corner-final, PASS:
- Windows WM_KEYDOWN/UP delivered only to a visible HWND rechecked against the
  retained owned Popen PID; no foreground/SendInput/owner-process control.
- Native F3 echo proves native Key_Event/binding dispatch acted in every arm;
  F4 performs the trusted diagnostic/capture/exit after F2. The cfg must finish
  before these keys: a trailing wait/quit list otherwise queues their commands
  behind quit (initial failed control retained, not a product pass).
- Original P731 product with legacy level30 bind: native F3/F4 act, F2 leaves
  screen0. New product with that SAME legacy bind opens screen7; native PNG
  visibly shows the Updates window. Empty F2 also opens7. A custom F2 echo
  acts once and stays screen0. The test excludes the echoed bind description
  when counting that custom action (an intermediate grading failure retained).
- A separately compiled NEVER-DEPLOYABLE status fixture redirects only
  MU_Status's read-only input values and instruments its actual text helper.
  Eleven states at1280x720 and800x600 draw33 text lines each; all share right
  edge1264 or784, width<=320. Only available/launcher/restart have [F2]; off and
  custom-binding negatives do not. This proves status layout/selection, NOT
  updater permission/HTTP/verification/restart authority. Fixture data are fake.
- PNGs inspected: actual native F2 window; bare right-aligned up-to-date corner;
  800x600 update-ready corner with [F2]. No backdrop or station-stack button.
- LSP reports no diagnostics but does not parse QC; compiler/native arms are the
  proof. Initial incorrect font-slot name failed compile and was corrected to
  existing ui_font_ui before the final zero-warning build.

## Clean build and delivery — 2026-10-16 UTC

Inspected product `8a8b605bdf1e31dba442710c0ce75a4a171feb7d` and engine notes
`93255c77848a49fd516295e09f34c960450e5ca4` were pushed by exact SHA. The clean
product-commit NoDeploy build has zero warnings and all three hashes equal the
native-tested subject. qwprogs/csprogs are byte-identical to P731; no fleet swap,
backend migration, CSQC deployment, engine build or process restart is needed.

At03:29:36Z, only menu.dat/menu.lno were staged and destination-hash verified in
BOTH Windows installs. Known predecessor menus were checked before any write;
each previous version is retained as .prev. Current server/client progs were
hash-checked unchanged. Both installed client executables have the SAME hash
as the engine used for native key controls. The owner's saved configuration
was read narrowly to identify the stale bind, never edited or saved by a rig.
Reload the menu (`menu_restart`) or restart the client to run its initialization
and repair that binding in memory. No owner process was controlled.

New menu SHA-256:
`ae77a2c2183e18299db126110ecf656aca8dcd654be520f43b8c80b5e850cbfa`.
Provenance: corner-windows-delivery.json and build-corner-clean.log in the owned
root. Final clean products: artifacts/update-corner-clean-build. Ignored compiler,
intermediate builds and caches were compressed with member-by-member hash
readback before retiring their disposable copies:
artifacts/update-corner-build-controls.zip / retained-corner-builds.json.
All16 new marker-owned runtime copies retired their assets/executable/menu;
configs, source-only status fixtures, logs and PNGs remain. No owned game process
remains. The published-clean engine-doc worktree is unregistered and empty, but
Windows denies removing its empty directory; retain exactly
C:/FTESurf-worktrees/menu-20261016T015008Z/engine-doc until its handle is released.
No lock was bypassed and no unrelated process was killed. Clean QC source and
bounded evidence are deliberately retained for the continuing UI/Friends work.
