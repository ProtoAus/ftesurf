# AGENT_NOTES.md

Detailed working notes, moved out of Pi's always-loaded AGENTS.md. The short
AGENTS.md is the startup contract; read relevant sections here BEFORE changing
that subsystem. Older references to AGENTS.md's detailed sections refer here.
Keep new operational findings here, not in the startup brief. No historical
findings were removed in the split.

Working notes for coding-agent sessions in this repo. Read CONTRIBUTING.md too
(git identity, `git clean -x`, line endings, `.src` ordering).
Pi subagent setup and its read-only smoke workflow are documented in
`.pi/README.md`. Native roles inherit the parent session's selected model via
`.pi/settings.json`; delegation still requires an operator request. Runtime
state under `.pi/` is ignored, not material to commit or publish.
Keep code comments concise; long-form reasoning belongs in ENGINE_PATCHES.md
essays, not in source files. See CLAUDE.md for the comment-style rules.
Beta phase, not release: building, deploying and restarting the Pi lobbies are
routine — do not hesitate when a change needs it.

## Pi startup contract

Start Pi from `C:\FTESurf` (or `pwsh -NoProfile -File
C:\FTESurf\tools\pi-start.ps1`) so this brief and `.pi/settings.json` load.
Pi has NO built-in `/add-dir`: its tools can use absolute paths outside cwd;
that access does NOT auto-load sibling instructions and is NOT a sandbox.

This work spans three directories:

- `C:\msys64\home\Lex\fteqw` — engine C/C++, ENGINE_PATCHES.md.
- `C:\FTESurf-private` — private anti-cheat plan, samples and reports.
- `C:\FTESurf` — QC, tools, deployment and the prebuilt engine.

The engine is required for anti-cheat, movement or renderer work. Before edits,
inspect Git status in every affected checkout and read any sibling instructions
that exist. For anti-cheat also read the private plan named below, on demand;
never copy it, exploit recipes, credentials or raw private tool output into a
public commit, agent artifact or shared/exported session. `C:\FTEQuake` is the
second install for client-vs-server tests; use its absolute path when needed.

Use LSP for engine symbol navigation and post-edit diagnostics; see `.pi/README.md`
for clangd's compilation database and smoke checks. clangd does NOT understand
QuakeC: QC must be checked with fteqcc and the project's runtime falsifiers.
A clean LSP report is not a build or physics/security verification.

Direct execution is the default; use agents only when the operator asks for
delegation/review/parallel work. Native roles inherit the selected model. Never
silently fall back to external CLIs or another provider after a child failure.

Context-fold defaults are intentional. A folded/compacted claim is not source
truth: reread the cited code or private document before acting on it. At a long
workstream boundary keep an explicit checkpoint (commit/ref, owned paths,
commands/results, control vs subject, unresolved questions and next step);
private anti-cheat checkpoints stay in the private tree. Do not turn unknowns
into findings or completed tests into claims about an unverified deployed build.

## Repository layout

- `ftesurf64.exe` — prebuilt FTE engine binary (Windows x64). Engine C code is
  NOT here: separate checkout at `C:/msys64/home/Lex/fteqw` (`engine/…`), which
  also holds `ENGINE_PATCHES.md`.
- `ftesurf/` — the gamedir: `cfg/` (incl. `cfg/test/`, `cfg/lobby/`,
  `cfg/maps/`), `data/` (saves, runs), `logs/`, `screenshots/`, `glsl/`,
  compiled progs (`csprogs.dat`, `qwprogs.dat`, `menu.dat`).
- `src/` — all QuakeC and the build script (`build.ps1`, `fteqcc64.exe`).
- `surfd/` — Python (Flask/gunicorn) directory + join broker; runs on the Pi.
- `src/release/` — packaging (`release.ps1`, `publish.sh`, `install.sh`, nginx +
  page template); the ROOT `release/` is only its untracked staging output
  (`stage-0.1.N/`). `ENGINE.txt` — pin of the engine commit/patch this tree
  expects.
- `.gitignore` IS AN ALLOWLIST: `/*` ignores everything at the root, then
  `!/name` un-ignores. A new ROOT file is invisible to git until you add it
  there — that is how AGENTS.md and CLAUDE.md first went untracked (both are
  allowlisted now, `.gitignore:125-126`). Check a surprise with
  `git check-ignore -v <path>`. `dist/` and the root `release/` must stay
  ignored.

## QuakeC sources → artifacts

- `src/server/*.qc` + `sv_progs.src` → `qwprogs.dat` (server progs).
- `src/client/*.qc` + `cl_progs.src` → `csprogs.dat` (CSQC: HUD, boards,
  replays, saveloc client half).
- `src/menu/*.qc` + `m_progs.src` → `menu.dat` (menu VM: picker, join flow).
  Menu is client-local: never deployed to servers.
- `src/shared/`, `src/defs/` — defs is GENERATED, do not hand-edit.
- `.src` file order is load-bearing (compile order = declaration order; QC has
  no forward references — add a prototype `void() Foo;` or reorder).

## Build

**Native isolation pitfall (measured P541).** `build.ps1 -Engine -NoDeploy`
only suppresses QC deployment: the BuildEngine branch still copies native
outputs to its product root AND QuakeDir. For an isolated engine build, the
product root must be an isolated worktree and pass `-QuakeDir <private path>`
explicitly (a nonexistent path skips the second native deployment). Do not
assume NoDeploy protects C:\FTEQuake. A guarded `.prev` restoration is required
if those files were accidentally copied; preserve any peer replacement. The
script itself remains a follow-up in BACKLOG.


From `src/`, with pwsh 7 (NOT `powershell`):

    pwsh -NoProfile -Command "./build.ps1 -Jobs 8"

- Default: compiles all three progs + plugin, deploys to `C:\FTESurf` AND
  `C:\FTEQuake` (dual deploy is mandatory).
- `-Engine`: also rebuilds the engine from the fteqw checkout; add `-Full`
  after any engine header change. Plugin rebuild is automatic. It builds the
  engine WORKING TREE, and `release.ps1` ships whatever it built. 0.1.8 went out
  with another session's uncommitted Patch 362, so commit engine edits before
  anyone cuts a release. The same holds for the progs: `release.ps1` packs the
  install's .dat, and its dirty gate cannot see uncommitted QC source -- build
  HEAD's progs in a clean worktree and copy them in. fteqcc output varies with
  the checkout path, so compare .dat hashes only between builds from one path.
- `-Pi`: ships qwprogs+csprogs to the Pi lobbies and restarts them.
- `src/release/release.ps1`: ALWAYS `-Bump patch -DryRun`. A bare `-DryRun`
  targets the PUBLISHED version and rewrites its stage, archive, receipt and
  page. A run that fails after its upload cannot be re-run (each pack stamps a
  new `built` time, so the md5 no longer matches R2): scp `dist\site-<v>\*` to
  the Pi's `ftesurf-site/.incoming/<v>/` and run `publish.sh <v>`, or bump.
  - A RELEASE THAT KEEPS THE LAST ENGINE (0.1.21): `git worktree add --detach`
    the engine at ENGINE.txt's `tag` (the engine that shipped), copy
    `release\stage-<prev>\ftesurf64.exe` and the plugin into its
    `engine\release\` (as `fteqw64.exe`), copy the same pair into the install
    after backing up the dev pair, run with `-FteRoot` = the worktree, then put
    the dev pair back. Byte-identical binaries, no rebuild. The receipt's patch is
    the worktree's highest ENGINE_PATCHES.md heading, and gate 3 only compares the
    two copies of the same exe -- so a worktree at the PIN (481 since 4 Oct) would
    stamp 481 on the 467 binary and pass. The tag is what makes it true.
  - THE QC BUILD NUMBER: `-BuildNumber <n>`. The script derives it from a
    `Build NN:` commit subject and HARD-FAILS when the last one is more than 200
    commits back (Build 89 was 228). It now takes the number explicitly, because
    the authority is the operator, not the log -- AGENTS.md's "only on the user's
    Build NN commit" is about WHO decides, and `-BuildNumber` is that person
    typing it. It still has to agree with ENGINE.txt's `qcbuild` (a Warn, not a
    Fail, as before). Build 89 = Patches 434-438.
    THE SWITCH IS NOT NAMED `-QcBuild`, and that cost an hour: PowerShell variable
    names are case-insensitive, so `$qcBuild = $null` and a `$QcBuild` parameter
    are ONE variable -- the switch bound 89, that line reset it to 0, and the run
    died 45 lines later on "You cannot call a method on a null-valued expression"
    with no mention of the switch. `grep -in` both spellings before adding a
    parameter.
  - **GATE L2 IS A `-Linux` GATE, NOT A GENERAL ONE** (`if ($Linux) { … }`, and
    its hard failures are BUILDINFO/soname checks). So a QC-only batch needs no
    engine work at all: omit `-Linux` and the receipt carries `linux: null`.
    Earlier note here claimed L2 blocked a QC-only release; that was reading the
    gate's comment rather than its scope.
  - WHAT REMAINS TRUE about the engine identity, and it is a receipt question not
    a gate: without `-Linux` nothing records which engine commit the shipped exe
    came from. ENGINE.txt's `commit` line is NOT that (it pins `45174b9d4` =
    Patch 427 while the 0.1.12 exe carries stamp
    `git-6891-patch-266-102-ga72183e6b` = Patch 419), so do not "reconcile" a
    release by rebuilding `-Engine` from the pin: it yields a DIFFERENT exe
    (measured `279841f7…` against 0.1.12's `1950288f…`) and nothing would record
    the swap. Read the stamp out of the binary if you need the commit.
  - `menu.dat`'s hash is path-dependent (fteqcc), so it will differ from an older
    receipt with `src/menu/` untouched -- measured `46ab6af4` against 0.1.12's
    `d8fe56aa`. That is not dirt: gate 1 compares the ship set against GIT, and
    it passes clean. Reproduce it from a clean `git worktree` anyway if you want
    the archive to match a from-scratch clone.
  - `-NoDeploy` on a worktree build leaves the .dat in the WORKTREE's `ftesurf/`,
    never in `C:\FTESurf` -- copy them in, and copy the shipped pair back after.
    That is also how a control build is made when this tree's source already holds
    the patch (`cfg/test/p439smoke.cfg`'s RESULT block records the recipe and the
    hash that proved which build ran).
- CSPROGS SITS AT FTEQCC'S GLOBAL LIMIT (131,072). Patch 474's ten 1,000-float
  arrays took it to 131,418 and the build died with `Too many globals`, reported
  as `Error in client/cl_main.qc on line 0`. Big tables go in `memalloc`'d memory
  (`cl_lines.qc`, `cl_online.qc` `Online_Alloc`), not in global arrays.
- QC-only change → default build is enough. Treat "0 warnings" as the bar, but
  check whether a warning is yours: this tree usually carries other people's
  uncommitted work (`cl_hud.qc:2007`, a 9-arg sprintf, is a standing example).

- ON A MACHINE WITH ONLY MSYS2 MINGW64 (the holiday laptop, 2026-09-29):
  `C:\msys64\ucrt64\bin` can exist and be EMPTY, and then every `make` step
  dies on "command not found". Put `C:\msys64\mingw64\bin;C:\msys64\usr\bin` on
  PATH and set `C_INCLUDE_PATH=C:\msys64\mingw64\include\opus` (the Makefile's
  `-I/usr/include/opus` misses the mingw64 package). The plugin link needs
  `pacman -S zip`; TTF fonts need `mingw-w64-x86_64-freetype` BEFORE the build
  (without it the Makefile silently adds `-DNO_FREETYPE`, and a later install
  needs a clean rebuild). `build.ps1 -Engine` then dies at plugins-rel on box3d's
  missing library -- build `NATIVE_PLUGINS="hl2 cod"` by hand and copy the exe and
  the hl2 DLL. That build links its libraries dynamically: copy libjpeg, libpng,
  libopus, libspeex(dsp), libvorbis(file), libogg, zlib1 and the freetype chain
  beside `ftesurf64.exe` (all git-ignored), and put mingw64\bin on PATH for
  `fteqcc64.exe` as well.

## Run and test

- Normal launch: `./ftesurf64.exe` (or `ftesurf.bat`).
- Headless: `./ftesurf64.exe -WindowStyle Minimized +exec <name>` with cfgs in
  `ftesurf/cfg/test/`; output in `ftesurf/logs/<log_name>.log` and
  `ftesurf/screenshots/`. Verify by reading logs and screenshots.
  CWD MUST BE `C:\FTESurf` — the basedir is the cwd and Start-Process inherits the
  caller's, so a shell left in `ftesurf/` produces NO log at all and the run just
  sits there: two 200 s timeouts read as a hang before the cwd was the answer.
  Pass `-WorkingDirectory "C:\FTESurf"` rather than trusting the shell's.
- AN ARM NEEDS A CONTROL BUILD AND A DETECTOR PROVEN TO HAVE FIRED. "Not flagged"
  is also what a subject that never fired prints, so an arm with no pre-change
  build beside it measures nothing — p411push printed a textbook flip on a pad
  that never armed. AND THE CONTROL IS NOT `git checkout -- <file>` ONCE THE TREE
  HOLDS A BATCH: that reverts one patch and leaves the others in, so the
  "control" still contains the fix. Build it from a `git worktree` at the
  pre-batch commit with `-NoDeploy`, copy its .dat in, and prove which build ran
  by hash (recipe and the hash that proved it: `cfg/test/p439smoke.cfg`'s RESULT
  block). Prove the subject ACTED before believing any verdict: its own
  dprint, or a latch carrying its authored number (p412speed used `tkspd 2060`,
  the pad's own horizontalspeed). Expect the pre-registered detector to be the
  wrong one and say so when it is. Control recipe — NOT `git stash`, which would
  take the other session's files: copy the file aside, `git checkout -- <file>`,
  build, run, copy back, rebuild, and diff the diffstat against the saved one.
  WHEN A CONCURRENT SESSION'S UNCOMMITTED FILE DOES NOT COMPILE, do not touch it and
  do not stash it: build the control anyway by `touch`ing that file's already-valid
  `.o` in `engine/release/<target>/` forward, so make skips it. The two binaries then
  differ ONLY in the files under test, which is a *better* control than a full
  rebuild, and the peer's work is never at risk. Verify the `.o` you are advancing is
  from a build that succeeded, and say in the entry which file was skipped and why.
- AN ARM WHOSE PREMISE IS AN ABSOLUTE ROW INDEX BREAKS ON AN UNRELATED FIX, and it
  reads as a failure of the thing you changed. `p477rewind` R5C loaded its at-rest
  save as `sl_goto 4` and R8 asserted `saves: 5/5`; Patch 499 stopped a resume row
  being dropped across a run boundary, one row earlier in the list then survived,
  and both arms failed on a build that was correct -- R5C loaded somebody else's
  row and R7/R8 failed behind it. Address a row by a PROPERTY (`sl_goto 9999`
  clamps to the count, i.e. the newest row) with the property CHECKED (the save's
  own row number beside the count), and keep an absolute count out of an arm whose
  subject is not the count.
- Test-cfg recipe: `cfg_save_auto 0` FIRST -- the engine writes ftesurf.cfg on
  every disconnect and map change (`CL_ClearState`), not only at quit, and a
  harness's `cl_maxfps 100` then lands in the owner's config (measured: an
  unguarded jit01 wrote `cl_maxfps "0"` over `"1000"`). `python tools/cfgguard.py`
  lists any test cfg without it, and exits 1. Then `cl_idlefps 0` AND
  `cl_maxfps 100` (uncapped fps starves async loads); `menu_restart` before any menu-VM command in a `+exec` run
  (menu.dat loads lazily); `set <cvar> <v>` for cvars not registered yet.
- The engine's BUILTIN menu is open from boot and `togglemenu` only OPENS;
  `ui_close` is the way back. Until it closes `notmenu=0` skips the whole HUD
  stack, so every screenshot harness needs `menu_restart` + `ui_close`.
- This machine's archived `ftesurf/ftesurf.cfg` overrides `default.cfg` (it
  archives `hud_energy_ref` and `hud_timer_size` among others, and the values
  drift — read the file rather than trusting a number quoted here). A headless
  test must `set` every cvar its measurement depends on, not assume a default.
  An install that ran 0.1.9 or earlier saved Momentum Mod's binds and some
  settings into its ftesurf.cfg (fixed by Patch 377, not undone): a player with
  odd binds, no chat on ENTER or a dead restart key should delete that file.
- DRIVING A RUN: the clock starts when you LEAVE THE START BOX. `+jump` hops in
  place (~80 u in 4 s on a bhop map) and never starts it; `+forward` walks at
  `sv_maxspeed` (260 in `default.cfg` — the move values are 450 precisely so
  they cap nothing) and clears the box in about a second — BUT NOT ALWAYS, AND A
  JUMP IS THE WRONG GESTURE: on surf_4am a straight `+forward` from `zone_goto`
  STOPS 32 u inside the region (y 96 against a boundary at 64) so no run ever
  starts and there is no sidecar; the start rule refuses a chain ("hopped start --
  one jump out of the start, or walk out"); and `+right` alone only TURNS.
  SINCE PATCH 445 THAT TAG IS STICKY AND ONLY `!r` TAKES IT BACK — which is the
  thing to know when an arm reads `hopped 1` three sections after the jump that
  earned it. `run_rearmhop` (build 21's extra forgiveness: stand
  `run_prestrafe_time` grounded and the tag lifts) **now defaults to 0**, and an
  ARM no longer forgives either, so nothing a harness does incidentally will clear
  it. The clears are the `!r`/`!m`/`!s`/`!b`/**`zone_goto`** gesture (all reach
  `SV_ZoneMoveAt`, and `zone_goto` is the warp this file tells harnesses to use, so
  a harness DOES clear it incidentally — round 6's correction), the ground dwell at
  `run_rearmhop 1`, and a respawn. All three zero the velocity, which is why they are
  safe. A `retry` does NOT clear it: `hopped` is in the save format, restored
  raise-only. **Patch 448 added a fourth: crossing a ZONE_END** — the tag dies with
  the run it described, so the next attempt starts clean. That one does NOT zero the
  velocity (players coast past the line) and carries its own argument at the call
  site; round 8 found it had to live at the ZONE_END site rather than inside
  `SV_TimerFinish`, because that function's other caller is a stage boundary that
  hands the next stage over at speed. **Patch 477 added a fifth and a raise**
  (`SV_SaveLoadTag`): a load that leaves the body at rest outside a run, with no
  trigger or delayed output still owed to it, forgives; an IDLE load faster than
  a walk or a jump (horizontal over sv_maxspeed, vertical over pm_jumpvelocity)
  raises it, and an armed, finished or running one only when it is that fast
  AND its file says hopped -- on bhop-mode maps a box entered from anything but
  IDLE never runs the rest test that forgives a load's tag after the arm. That
  rest-test forgiveness (`run_t_finfgv`) belongs only to a tag the load itself
  raised: a hop chain's stays `!r`'s, and `!r` or a raise-only restore drops a
  pending one. **The tag still survives a cancel zone, a map
  teleport and a stage-boundary finish**, so an arm can read `hopped 1` many sections
  after the jump that earned it; there is a chat reminder on each later fluffed start
  but nothing on the HUD. Walk out, then
  prove the run with `cmd timer` reading
  `running / recording 1` before anything depends on it, and read the body with
  `cmd viewpos` — since Patch 435 it also prints `velocity … horizontal N`, the
  ONLY server-side speed read there is (the hold publishes the SAVE's, the
  recorder's samples exist only after a close, the client's is a prediction).
  `timer` prints the client latches, `cmd timer` the server's.
- MEASURING A DRAW: with no console dump, take two screenshots with exactly one
  variable changed between them and diff the numbers — a frozen column beside a
  live readout that moved is a measurement, one picture is not.
  A minimized harness draws slowly: wait ~500 ms after a change before
  `screenshot` (100 ms captured the previous state in p390mouse).
- MOUSE: `spectate look <dx> <dy>` pushes one IE_MOUSEDELTA through the input
  chain; `mousepad` counts the deltas it saw. Real ones can reach a starting
  harness window, so a mouse arm checks that count before it counts.
  **IT DOES NOT AIM, and this line used to read as though it did.** Measured
  2026-09-27: `spectate look 800 0` twice, 500 ms apart, gave `took 0` and
  `aim 0 0 0` both times — CSQC declines the event and the engine applies no
  synthetic delta to the view. It delivers an EVENT, which is all a mouse arm
  needs; it does not turn the player. **To turn a headless player, use the
  keyboard:** `+left`/`+right` aim at exactly `cl_yawspeed` (measured:
  `+left` 700 ms at 210 gave `aim 0 148.05 0`). Someone read this bullet as
  "a mouse delta through the chain, therefore it aims" and built on it.
- Client-vs-server (prediction) tests need a REAL socket, not a listen server:
  run `C:\FTEQuake\fteqwsv64.exe +set sv_port <p> +exec cfg/test/<sv>` from
  `C:\FTESurf` (`ftesurf64.exe -dedicated` crashes after prop lighting), with
  `sv_public 0` or it heartbeats to public masters.
  It writes nothing to stdout: pass `+set log_enable 1 +set log_dir logs +set
  log_name <n>`, run it via `Start-Process -WindowStyle Minimized -PassThru` +
  `WaitForExit`, then read `ftesurf/logs/<n>.log`. A cfg's own `log_name`
  line overrides the `+set`.
  - After EVERY csprogs rebuild run `python tools/seed_csprogs.py`, then RESTART
    the dedicated server. A stale `downloads/csprogsvers/<hash>.dat` silently
    runs the OLD code (no download line, no error); a server left running holds
    the old progs in memory and the client then logs "no client game" with every
    QC command reading "Unknown command" (panels absent, screenshots empty).
    The advertised hash is the folded MD4 of csprogs.dat (`CalcHashInt(hash_md4)`,
    digest bytes XORed by `i%4`); seeding by hand, STRIP LEADING ZEROS — the
    engine spells the filename `%x`.
  - A client whose csprogs.dat differs from the server's downloads the server's
    copy to `downloads/csprogsvers/` (clients before 0.1.8 use
    `<gamedir>_downloads/`). That only works against an engine at Patch 362 or
    later; a rollback below it leaves every uncached client with no HUD after a
    progs deploy. To test a join with no cache, delete that file first
    (`cfg/test/p362csqc.cfg`). With no CSQC, nothing sends `rechid`/`inprof`,
    so a community run flagged 2560 (TF_NOJOURNAL|TF_NOPROFILE) means the HUD
    never loaded, not something the player did.
  - Warp with `cmd zone_goto`, NOT `setpos`: setpos forces MOVETYPE_NOCLIP
    server-side and desyncs the two simulations. It also taints the run
    (`cheated`), which is fine once no measurement depends on the clock. And it
    writes NO `warp` record — the only placement in the mod that records nothing
    (`sv_player.qc`: setorigin + SV_ClearCarrier + SV_TimerWarped) — so a replay
    cannot follow it and pm_verify HOLDs `no finish` on any run a harness drove
    with it. On maps
    with no zone data, setpos + `cmd noclip` TWICE lands in WALK — prove it with
    a viewpos z-drop; ONE toggle leaves you in NOCLIP (level flight). Each
    `noclip` is processed twice — engine `SV_Noclip_f` flips to WALK, then the
    mod's QC handler flips back and prints "noclip ON" — so the printed state
    lies; trust the z-drop, not the console.
  - CSQC-registered cvars (`cl_trigdebug`, `cl_triggers`) must be set AFTER
    `connect`: registercvar resets a pre-connect `set` to default.
- No QC unit tests. surfd's tests are plain scripts, run on the Pi (Flask is
  not on Windows): `SURFD_HOME=$(mktemp -d) python3 surfd/test_x.py`.
  `test_recplot.py` is stdlib only and runs anywhere.
- TEST AN ENGINE CHANGE WITHOUT DEPLOYING IT: with `C:\msys64\ucrt64\bin;
  C:\msys64\usr\bin` on PATH, `make -j8 -C <fteqw>/engine sv-rel m-rel
  FTE_TARGET=win64`, then run `engine\release\fteqwsv64.exe` or `fteqw64.exe`
  with cwd `C:\FTESurf` (the basedir is the cwd). The installs keep their binary
  and a control run on `C:\FTEQuake\fteqwsv64.exe` stays one command away.
- AND THE FLIP SIDE: AN ARM THAT PASSES SAYS NOTHING ABOUT WHAT THE OWNER IS
  RUNNING. The bullet above is why — every arm drives `engine\release\`, so the
  install can lag the engine tree indefinitely and every verdict stays green.
  Measured 2026-10-05: `C:\FTESurf\ftesurf64.exe` was SIX engine patches behind
  (485, 487, 488, 489, 490, 491 — four of them client-security fixes that protect
  the owner's own client) while all four of Patch 491's arms passed beside it.
  Nothing in the tree checked. `cfg/test/deploy491smoke.cfg` is that check: boot,
  load a map, ask the server QC two questions, run one local operator command,
  quit, and grade by presence/absence of strings only one cause can produce.
  PROVENANCE IS AN MD5, NOT AN ARM: compare the install against
  `engine/release/fteqw64.exe` and `C:\FTEQuake`'s copy — all three identical is
  what "deployed" means. Reading a gate's literal out of the binary
  (`grep -a -o "Blocking insecure renderer" | wc -l`) dates it when the stamp
  does not, which is how the six-patch gap was found.
- A synthetic key (`in_journal_synth`) never reaches the binds in a minimized
  headless client, so a key's effect cannot be driven. Probe the input chain's
  verdict instead: `vote key <scan> <0|1>` runs CSQC_InputEvent and prints
  `took`, which is what decides whether keys.c runs the stored `-command`.
- A cross-session heads-up can sit unapproved and expire undelivered: park and
  restore shared fixtures regardless, and never wait on a reply.
- Another session may run game copies from `%TEMP%` on its own ports. Between
  harness arms kill only processes whose ExecutablePath is under `C:\FTESurf`,
  `C:\FTEQuake` or `engine\release`. Agent PowerShell cannot `Remove-Item`
  under `C:\FTESurf`, and logs append: give each run a fresh `log_name`.
- A HARNESS HANDLE IS A REGISTERED CVAR, NOT A QC GLOBAL. `+set foo 1` creates a
  CVAR; a bare `float foo;` in QC is invisible to it, reads 0, and nothing says
  so — the arm then exercises the unhandled path and passes by never happening.
  `registercvar` it and read it with `cvar()`, and set it AFTER the map, because
  registercvar resets a value set earlier (the `cl_trigdebug` trap). Related, and
  why Patch 438 needed a new command: the server STUFFS `set cl_saveroot
  "data/saves/<map>"` on every `sl_` command, so a client-side save root cannot be
  overridden at all — `sl_replay <slot>` fires the load event with no save behind
  it (no placement, no clock, no row) for exactly that reason.
- A HARNESS SCRATCH PATH MUST BE INSIDE THE GAMEDIR. `FS_LoadFile` locates with
  `FS_GAME`, so `%TEMP%` or the install root opens nothing and `fopen(FILE_READ)`
  returns -1 with NO "Access denied" line — which reads as a reader bug and is a
  path bug. Cost a whole arm.
- **A TRIGGER ALIAS'S EXECUTION IS DEFERRED, AND THE CLIENT'S `quit` RE-FIRES IT — so
  neither a marker's POSITION nor a COUNT attributes a phase** (measured driving Patch
  487's arm). A multi-command alias body (one containing `;`) goes to
  `Cbuf_AddText`, and text queued at a changelevel drained ~94 s later, during the
  client's own quit. Separately, quiting reloads the menu and the map and those
  reloads fire `f_newmap` AGAIN — two extra payload runs after the client had printed
  its own "done" — so the control counted the planted payload 4x and the subject 3x,
  a difference that is NOT the fix. GRADE SUCH AN ARM BY THE PRESENCE/ABSENCE OF A
  STRING ONLY ONE CAUSE CAN PRODUCE: three different gated `fs_*` commands gave three
  disjoint success strings and three disjoint blocking strings, and every line in the
  log then named its own cause. Same family: `cmd viewpos`'s reply is ASYNCHRONOUS and
  a shader reload (~150 lines) landed between request and answer, so a fixed byte
  window read it as "not connected" — a false verdict on the one prediction that says
  every other verdict came from a live connection. Bound that window by the client's
  own done marker. And `stuffcmd` REFUSES A `;` ("You're not allowed to stuffcmd
  that", `sv_ccmds.c`), so a server admin cannot stuff a multi-command alias body;
  the filter is in the console command, not in the wire path.
- **A SERVER-SET CVAR'S READBACK PRINTS THREE LINES AND THE FIRST ONE LIES.**
  `stuffcmd * set foo 1` makes the client `Cvar_LockFromServer` the cvar, so a later
  readback prints `"foo" is "0"` / `Effective value is "1"` / `Default: "0"` -- the
  LATCHED pre-override string first and the value `.ival` actually holds second. This is
  the same split AGENTS.md already records for string mirrors, appearing in the ENGINE'S
  OWN cvar readback. It cost a precondition control: an arm matching the first line
  reported a precondition that HAD held as one that had not, and the leg it was
  guarding had in fact fired (`Operating in databaseless mode` was in the log). Match
  `Effective value is`, not `is`, and derive the pattern against the real bytes with
  `repr()` rather than guessing at adjacency -- every log line carries a
  `YYYY-MM-DD HH:MM:SS ` prefix, so a pattern expecting two lines to touch can never
  match. A NOT-REACHED grade is what stopped that from being read as a passing verdict.
- **AN ARM WHOSE OBSERVABLE IS PRODUCED DOWNSTREAM OF THE THING IT MEASURES CANNOT
  DISTINGUISH A FIX FROM NO FIX.** `p482c` graded `allskins` by the skin-loader line,
  and `qwskin_t::name[64]` truncates that name to 63 characters -- so a bounded copy
  and an unbounded one print the SAME line, and the arm passed both. Its own RESULT
  block said the right thing ("the overrun itself was NOT measured") but the arm still
  looked like coverage. When the only visible effect is downstream of a narrowing
  step, MEASURE AT THE WRITE: Patch 489's canary build put a known word at the buffer's
  end and printed it before and after the copy, which is what an AddressSanitizer build
  would report and what this toolchain does not have (`mingw64` absent, `ucrt64` gcc
  builds without it). Generate BOTH variants from one pristine file with a script that
  ASSERTS they differ in exactly one line, or the instrumentation itself becomes the
  variable. And keep the detector separate from the regression arm: the canary pair
  proves the bound, the REAL pair proves skin forcing still works, and grading the
  canary build for behaviour would conflate the two. Note also that a canary changes
  the layout it instruments -- the crash it produced belongs to the instrumented build,
  so quote the write, not the crash.
- **A COMMAND'S LOCAL FORM AND ITS STUFFED FORM CAN PARSE DIFFERENTLY, and the
  difference is silent** (measured driving Patch 488's arm). `setrenderer gl <path>`
  UNQUOTED hands the handler `argv(1) == "gl"` ALONE -- the path is `argv(2)` and is
  never read -- so no subrenderer token is parsed, nothing loads, nothing complains
  and the log holds no evidence either way. `stuffcmd * setrenderer "gl <path>"`
  delivers the whole quoted string as ONE argument, which the handler's own
  `COM_Parse` then splits into name and token, so THAT form exercises the code path.
  A regression control written in the local unquoted form therefore measures a
  different path from the subject's: it would have read as "the fix broke local
  renderer selection" on the subject while passing vacuously on the control. When an
  arm compares a local invocation with a stuffed one, quote both identically and
  check the control produced its own evidence line before believing either verdict.
- `alias <name>` WITH NO VALUE DELETES THE ALIAS. `Cmd_Alias_f`'s argc==2 path
  builds an empty value and reaches `if (!*cmd && !dpcompat_console.ival)` —
  "someone wants to wipe it. let them" — and unlinks it. So it is NOT a query, and
  using it as one destroys the subject: two arms reported a planted alias as
  "missing", the second written specifically to explain the first, and the item
  they were disproving turned out to be real. The only safe read is the full
  `alias` listing (argc==1).
- A `+exec` CFG RUNS BELOW `rcon_level` (20), and bare `rcon_level` prints
  `Unknown command` — with no refusal message, because the dispatcher's
  `cmd '%s' was restricted.` is a `Con_TPrintf` that does not reach the log at these
  settings. Stufftext runs at `RESTRICT_SERVERSEAT(0)` = 31.
  **CORRECTION (Patch 487, measured): the claim this bullet used to carry — "an
  `alias` defined in a cfg creates nothing" — IS FALSE.** `cfg/test/p487probe.cfg`
  creates `alias f_probe "echo LOCALALIAS-RAN"` in a `+exec` cfg: the full `alias`
  listing shows it, typing it prints `Execing alias f_probe` + `LOCALALIAS-RAN`, and
  it also fires as an `f_newmap` trigger. WHAT A CFG CANNOT DO IS CREATE A
  SERVER-LEVEL ALIAS, which is the distinction the old wording was reaching for:
  `Cmd_Alias_f` stamps `execlevel = RESTRICT_SERVER` only when `Cmd_FromGamecode()`
  (level >= 31) is true, otherwise `execlevel = 0` = "run at users exec level". A cfg
  is RESTRICT_LOCAL, so its aliases are USER-level — which is exactly what makes one a
  valid regression control and not a second subject. An arm that needs a SERVER alias
  must stuff it. Related and general: **SILENT REFUSALS ARE
  EVERYWHERE IN THE COMMAND LAYER** (`condump`'s `if (Cmd_IsInsecure()) return;`
  prints nothing either), so grepping a log for a payload's own output cannot
  distinguish "refused" from "never ran". Every arm needs a control that must
  print.
- `stuffcmd *` WITH NO `map` HAS NO CLIENT TO ADDRESS and the text vanishes with no
  message anywhere — the same shape as the stringcmd-before-spawn trap below, one
  level earlier. The server's userinfo dump is `user`, not `info`; `InfoBuf_Print`
  renders a blob key as `<N BYTES>` and never dumps its content.
- bash SPLITS `+set <cvar> "value with spaces"` INTO SEPARATE ARGUMENTS, so the cvar
  reads back empty and the arm measures nothing while looking like a negative. Use
  a path with no spaces (an 8.3 short name via `GetShortPathNameW`) rather than
  trusting the quoting — and print the cvar back before believing the result.
- STRINGCMDS SENT BEFORE THE SERVER HAS SPAWNED THE CLIENT VANISH from both logs
  with no error anywhere. A map with downloads (bhop_arcane: ~7 s of models)
  needs a wait for `spawn`, not a fixed guess, and the failure looks exactly like
  "the command did nothing". `sl_hold` is the same shape one level down: it needs
  `sl_goto <n>` first (the cursor is the LAST row after a rescan, and with no row
  under it the hold returns without a word) and must share a frame with its
  `sl_load`.
- `sprintf` DROPS ITS NINTH ARGUMENT and only warns, so a nine-specifier debug
  print reports the EIGHTH value under the NINTH label. A print that lies is worse
  than no print: this one sent a hunt after a value that was correct. Same cost,
  different shape — a line inserted between a braceless `if (x)` and its body
  REBINDS the body, so the gate looks dead while the print runs unconditionally.
  Instrument by copying the file aside and restoring it; never clean debug lines
  with a line-filter script (one such edit left an `if` with no body behind).
- A smoothness gate needs the subject's own motion measured first. Patch 383's
  owner walking circles varies its speed 4.3% by itself, so `speed CV < 2%` was
  falsified by the owner, not the renderer. Compare the render with the sampled
  motion (frames drawn exactly on a sample tick), not with a constant.

## Generated / never edit

`ftesurf/*.dat`, `*.lno`, `src/defs/*.qc`, `ftesurf/ftesurf.cfg` (auto-saved
archive), `ftesurf/data/**` (player data), `installed.lst`, `crashaddr.txt`.

## Conventions

- OPEN BUGS AND FOLLOW-UPS LIVE IN `BACKLOG.md`. Add what you find and do not
  fix (with a file:function and a falsifier); delete it in the fixing commit.
- QC style: `type() Name =\n{ … };`, `local` declarations first, tabs,
  ALL_CAPS defines, module-prefixed globals (`ui_`, `lb_`, `lj_`, `rec_sl_`).
- THIS TREE USUALLY CARRIES MORE THAN ONE WORKSTREAM UNCOMMITTED. Before
  claiming a build number, `grep -rn "BUILD 8[0-9]" src/` — comments claim
  numbers before the commit does. A `build.ps1` failure in a prog you did not
  touch is probably not yours: check `git status` first.
- Every change is "Patch NNN": append to `ENGINE_PATCHES.md` (engine repo) and
  bump the `patch` pin in `ENGINE.txt`. Mod-side-only patches still take a
  number and say so; the engine `commit`/`tag` pins only move for engine work.
  NEW ENTRIES ARE CONCISE: Problem / Change / Verified, a few lines each, no
  prose padding. Entries up to patch 334 are a long-form archive: never rewrite
  them and do not imitate their style. `qcbuild` bumps only on the user's
  "Build NN" commit.
  - PATCH NUMBERS COLLIDE BETWEEN CONCURRENT SESSIONS (343, 351 and 354 all did
    on 2026-09-18). Right before committing, `git fetch` both repos and take
    max+1 over the ENGINE_PATCHES.md headings AND untracked `cfg/test/pNNN*`
    files, where a claim shows up first. Tell any other live session the
    number, and claim one number at a time: an open range ("392 and up")
    leaves the other session no free max+1. Fix a collision forward by
    renumbering yours; `patch` never moves down.
- COMMIT AFTER EVERY FEATURE, AND PUSH. Do not wait to be asked and do not batch
  a session's work into one lump — this is the development phase, and the cost of
  not committing is what the build-86 catch-up had to clean up: 75 unpushed
  commits, the agent brief untracked, and four client sources that `cl_progs.src`
  references missing from the repo entirely, so a fresh clone could not compile.
  - The order is: build to 0 new warnings, run the falsifier, THEN commit.
    Never commit something you have not verified.
  - ONE COMMIT PER FEATURE. `git add -A` fuses unrelated workstreams into an
    unbisectable lump — this tree usually holds more than one. Stage the paths
    your change actually touched, and check `git status` for what you left.
    A shared file (AGENTS.md, ENGINE.txt, ENGINE_PATCHES.md) can hold another
    session's uncommitted hunks. Stage only yours: `git apply --cached` a
    trimmed diff. `git add -p` is interactive, which agents cannot use.
    Other sessions also STAGE files in this shared index. `git commit --
    <paths>` commits those paths' WORKING-TREE content: right for files wholly
    yours, wrong for one holding another session's hunks. There, `git apply
    --cached` yours, check `git diff --cached` is exactly your set, then a bare
    `git commit`.
  - A working-tree build proves nothing about a commit whose tree also holds
    other sessions' QC. Prove it alone: `git diff --cached > p`, `git worktree
    add <tmp> HEAD`, `git -C <tmp> apply p`, copy the untracked
    `src/fteqcc64.exe` in, compile the three `.src` there, remove the worktree.
  - Format is CONTRIBUTING.md's: `Build NN — …` or a plain subject ≤ 72 chars,
    body Root cause / Fix / Verified. Say what you could NOT verify.
  - `git push origin HEAD:main`. Never force-push and never rewrite pushed
    history; unpushed local commits are yours to reshape freely.
    **THE CHECKED-OUT BRANCH IS NOT `main` AND THE LOCAL `main` REF IS STALE.**
    This tree sits on a session branch (`build57` as of 2026-10-05) that is 563
    commits AHEAD of the local `main` ref, which still points at `4a87aef`
    (Patch 343). So `git rev-list --count main..feat-maps-demos` and any other
    comparison against `main` answers a question about a months-old tree, and
    `feat-maps-demos` reads as "500 unmerged commits" when it is simply old.
    Compare against `origin/main`, which is what HEAD:main publishes to, and
    verify a push with `git merge-base --is-ancestor <sha> origin/main` rather
    than by reading branch names.
  - `qcbuild` in ENGINE.txt still moves only on the user's own "Build NN" commit;
    the `patch` pin moves with your ENGINE_PATCHES.md entry.
- Compare two dynamic strings with `strcmp`; `==` only against literals.
- One `URI_Get_Callback` per VM — branch on the request id.
- Inspect existing implementations before adding systems: cvar mirrors in
  cl_hud.qc, `HUD_Size` fallbacks, the `Seq_*` anchor chain in cl_board.qc, the
  `sl_*` command table in cl_saveloc.qc/sv_saveloc.qc, surfd routes. Reuse
  commands/cvars/paths instead of inventing parallel ones.
- A display switch that can be turned off wants three things, not one: the
  `registercvar`, a row in `cl_hudedit.qc`'s `HE_OptDef` (rows must stay
  contiguous — the first `""` ends the pane, and `HE_ResetAll` walks them, so an
  omitted row is a cvar the reset button cannot recover), and a `set` line in
  `default.cfg`.  A chip in hud_edit's FIXED block instead -- a setting that
  belongs to no element, like Patch 440's `hud_font_outline` -- wants a
  `HE_FIXEDROWS` bump and a `HE_ResetCvar` line in `HE_ResetAll`, or the panel's
  height and its reset button both miss it.

## Boundaries and interfaces

- Server QC is authoritative (saveloc lists, timer/zones, heartbeat, board
  submits). Client QC renders/predicts. Menu QC is offline UI + directory.
- **PlayerPreThink is per USERCMD; PlayerPostThink is per PACKET.** The engine
  brackets the usercmd loop in SV_PreRunCmd/SV_PostRunCmd (`sv_user.c:9331`), so
  `SV_TimerFrame` and the whole timer run ONCE PER PACKET while touches and the
  mover run per command. Anything that must act on every command belongs in
  PreThink. Corollary: `FL_ONGROUND` read in PostThink is post-move AND
  post-touch — a jump or any upward `trigger_push` has already cleared it, so a
  ground test there is not the ground state the player had. Patch 403's first cut
  put a per-command clamp on the PostThink path and a client's own packet rate
  chose how often it fired.
- **A speed check must say whether it means `.velocity` or velocity + carrier.**
  `trigger_push` does not write `.velocity`; it arms `.run_basevel`, which the
  engine rides as `pmove.basevelocity` and which becomes velocity only on the
  first command nothing re-armed it (`SV_BaseVelocityFrame`). A body can be doing
  1800 u/s with `.velocity` EXACTLY ZERO — measured, and the recording's `seed`
  says `0 0 0` because that is honest. Effective horizontal speed is
  `.velocity + (1 + run_bv_tick * 0.5) * .run_basevel`. `run_stagecap` read the
  wrong one until P407/P411 (`launch 0 ... cap 290` at 1809 u/s); it is 0 since
  2026-09-21 (Lex: boosters count, speed does not matter).
- Client→server: `cmd sl_*`-style registered command strings.
  Server→client: `stuffcmd` (e.g. `set cl_saveroot`), stats, sprint, csqc
  entity fields. MIRRORS SPLIT BY TYPE: floats ride a stuffed `set` read with
  `cvar()`; STRINGS must ride `forceinfokey(p, "*key", …)` read with
  `getplayerkeyvalue(player_localnum, "*key")` (`*wrank`, `*phash`) — a stuffed
  `set` is Cvar_LockFromServer, and `cvar_string` then returns the LATCHED
  pre-override string while `cvar()` still reads the effective value.
  Customization channels: userinfo `lobbycolor`/`lobbyfx`/`lobbytrail` in;
  `tc` (the engine's own chat-name colour key), `lc`, `lrgb` and `*phash`
  (FS_GuidId) out.
- Engine↔QC: traps (`registercommand`, `infokey`, `serverkey`,
  `Mod_ForName`/`BIH_EnumBrushes`), per-frame cvar mirrors in QC, renderer cvars
  (`r_voidview`, fog) live in the engine repo.
- EVERY PUBLIC LOBBY SETS `lobby_nopb 1`. SV_PBGet then returns 0 and every PB
  figure is zero there — `TF_HAVEPB`, `STAT_FS_TIMERPB`, and the split and
  checkpoint deltas (`TIMERDELTA`, `TIMERCPD`). Anything PB-dependent is silent
  on the servers people actually play on; test it offline or on a listen server.
- CLIENT-SIDE TRIGGER PREDICTION (patches 335–338; full story in
  ENGINE_PATCHES.md). `cl_triggers.qc` mirrors the stateless Source triggers
  (teleport/push/setspeed) inside `CSQC_PredictPlayerMove`. It is a MIRROR of
  `sv_entities.qc` — read the server counterpart before touching either half.
  Load-bearing invariants:
  - Push is NOT a one-command carrier: 337 mirrors the full Patch 249 state
    machine. PUSH HAS THREE LEGS that must stay in lockstep: ride, CASH OUT held
    into real velocity when `!armed`, spend held Z. Per predicted command the
    engine runs `SV_BaseVelocityFrame`'s exact shape (restore, cash out, hand the
    window to `pmove.basevelocity`, spend held Z) and QC reports fires via
    `predmove_basevel` / `predmove_bvfired`. The engine keeps a sequence-keyed
    ring of (held, armed) and it MUST survive chain restarts — the chain restarts
    from the ack every rendered frame, so chain-scoped carrier state
    systematically loses the first replayed command's push.
  - THE SERVER STAYS AUTHORITATIVE for anything needing runtime state:
    StartDisabled / IO-toggled triggers, and filters whose verdict depends on the
    player's runtime targetname (`filter_activator_name` — outputs rename the
    player). Missing or unimplemented filters FAIL OPEN exactly as the server
    does, so those triggers ARE predicted (336). `.rec`/`.hid` evidence is
    untouched by any of this, and LISTEN SERVERS GATE THE HOOK OFF — a listen
    server never exercises prediction at all.
  - Patch 338 mirrors only the Enable/Disable half of entity I/O, ZERO DELAY
    ONLY: touch edges of predicted slots, event-only trigger_multiples, and
    `logic_auto`'s OnMapSpawn. A demotion fixpoint keeps everything else
    server-side — relays, buttons, timers, OnTrigger/OnJump/OnLand,
    Toggle/Kill/AddOutput/ModifySpeed, the All-variants, delayed outputs — and
    StartDisabled slots are predicted only when their enabler is mirrored too.
    Gate state = persistent array + sequence-keyed ring committed at chain start;
    edge seeding uses persistent last-overlap stamps (continuous stay vs
    warp-in). `trig_io` dumps the graph, `cl_trigdebug 2` traces edge seeding.
    If a map ever mis-gates, suspect a speculatively-committed event or a
    suppressed setspeed enter-edge first (both bounded, both Patch-328 class).
  - Exact client brush clipping = tracebox `MOVE_TRIGGERS|MOVE_OTHERONLY`
    against an edict with `setmodel("*N")` AND `solid = SOLID_BSPTRIGGER`,
    tested ZERO-LENGTH at the command's END position (the server's
    `World_TouchAllLinks` dispatch shape). Sweeping fires on grazes the server
    never sees. (A submodel with `solid = SOLID_NOT` silently clips its BOUNDING
    BOX instead — `World_ClipMoveToEntity` resolves the model only for
    SOLID_BSP/BSPTRIGGER/PORTAL — and huge trigger bboxes then fire from
    everywhere under them.)
  - `cl_prederror` prints one line per acked command whose server origin
    differs. KNOWN RESIDUE, do not re-chase: 4–8 u transients at discrete
    boundaries (pad entry, step-off lip) are Patch-328 class and self-heal in a
    correction or two. A CONSTANT quantized cascade or a GROWING error is a real
    bug — that is how 337 was found.
  - Changes here need a REAL playtest on `bhop_mom_training_beta` (24 pushes,
    20 setspeeds, training-scale blocks); synthetic walkers never once crossed a
    live pad, and both push bugs only printed under a human riding them.
    Harnesses: `p335k5` (walk-mode pad drop, z-drop WALK proof), `p338c`
    (Enable/Disable lifecycle) / `p338e` (the mapspawn-enabled teleport) against
    the `p335sv2` dedicated server.
- Patch 339 was a CENSUS, not code (`tools/ioscan.py`): across 82 roster maps
  there are ZERO zero-delay relay or timer gates on movement triggers — every
  relay OnTrigger gate is delayed 0.05–200 s (song/hint/ending sequences; the
  only MOVE-class rows are surf_lt_unicorn's ending viewholder swap) and timers
  gate no triggers at all — so a relay or timer mirror has an EMPTY actionable
  set — re-run the census before building one. The next real coverage step is a
  delayed-output scheduler (absolute-clock pending queue), the prerequisite for
  movers and song-timed work alike.
- Movers: the server has NO real movers — func_door/func_button are Tier-2
  state only ("NOTHING MOVES", sv_entities.qc:553 and :6221), func_rotating is a
  MOVETYPE_PUSH stub, and competitive maps force doors open anyway. Client
  mover prediction is moot until server movers exist.
- Pi deploy of csprogs requiring engine 335+ is version-skew safe: csqc globals
  bind BY NAME and missing ones point at junk (CSQC_FindGlobals), and
  CSQC_PredictPlayerMove is simply never called on an old engine — prediction
  degrades to server-authoritative, both directions.
- surfd broker: `/lobbies.json` (directory), `/api/join` (files a claim and
  returns a lobby NOT already running the map — the menu waits for the directory
  row to flip, patch 334), `/api/heartbeat` (carries assignments back to
  lobbies; children of mapcluster never heartbeat).
- The web leaderboard (Patch 359) is surfd's `/board/`, served from `surfd/web/`
  and proxied at proto.bar/ftesurf/board/ by `src/release/ftesurf.nginx`. Owner
  review is `/admin/runs` on play.proto.bar. The page must use relative URLs,
  because the browser path and Flask's path differ.
  The admin panel is PUBLIC at play.proto.bar/admin; proto.bar/admin/ is an
  unrelated FileBrowser. The panel's fleet comes from `cfg/lobby/lobby<N>.cfg`.
  nginx changes go in `src/release/ftesurf.nginx` or `surfd/surfd.nginx`, and
  installing them needs Lex's sudo (`install.sh`). A proxied surfd route must
  set `X-Real-IP`, or every client shares one rate bucket.
- LOBBY BODIES ARE A CSQC STREAM (Patch 383): the avatar's SendEntity
  (`sv_pose.qc`) feeds CSQC_Ent_Update (`cl_body.qc`). Each sample carries the
  owner's `run_movetick`, and the client interpolates on that clock, never by
  arrival; `Body_Pose(slot, ...)` is the API. `lobby_av_stream 0` is the old
  engine avatar byte for byte (the control), `lobby_av_rate 0` every moved tick,
  `lobby_av_budget` the cap for a full lobby. qwprogs and csprogs ship TOGETHER:
  a client whose csprogs lacks CSQC_Ent_Update is kicked. CSQC_Ent_Remove is
  global, so a second networked CSQC entity dispatches on the reserved type bit
  0x80. Measure with `body_trace`/`body_stats` and `tools/bodytrace.py`.
- `shared/sh_interp.qc` is the one interpolation speller (the replay viewer and
  the body stream). The replay viewer is measured per frame with `replay trace
  <n> <dt>` / `replay trace frames <n>` and `tools/watchtrace.py` (`--model`
  re-derives its tables, `--compare` replays the frames through a Python model).

## Anti-cheat and run evidence

- **Verifier observations need stable source bytes (Patch 599).** Fresh SHA-256
  before runner admission must match a known-current filing digest. Fresh reads
  after runner/row/stage checks must match the admitted bytes; evidence requires
  both the lobby copy the engine reads and KEEP copy the row checks read. Read
  failure/replacement becomes retryable ERROR, with unknown ticks and no counts
  snapshot, not a cheating judgement or a new Verified badge. Hash reads compare
  handle/path metadata and never use the filing cache. Hashing runs outside a
  writer transaction; existing ERROR budgets/refile/recheck scheduling remain.
  Unknown/stale filing digests retain compatibility without backfill. Run
  `surfd/test_verifier_sources.py` alongside sweep/counts/board/replays controls.
  This is a before/after fence, NOT immutable engine input or detection of a
  hostile host's intermediate change-and-restore. ERROR does not revoke existing
  PASS/owner approvals; no historical reread, schema, detector or review-policy
  change. Sweeper-only deployment needs no web reload or game/progs swap. Exact
  controls, full boundary and installed-source/hash gates: `tools/p599sources.md`.

- **Journal diagnostics are frame measurements, not new detector policy**
  (Patches 512–514). `identity_mouse_frames` counts nonzero counts only on a
  judged axis; its denominator is the yaw/pitch judged union, counting a frame
  once. `identity_no_mouse_longest` and `identity_unresolved_longest` follow
  original v-record order; an unjudged/nonmatching frame breaks continuity,
  interspersed event lines do not. These are not elapsed seconds, raw-report
  coverage or hardware attestation. Explicit `identity_blind` reasons explain
  existing abstentions. Fault and unresolved precedence, equations, thresholds
  and ranking remain unchanged. Receipt journal details retain the measurements
  before identity prose; a fault summary is limited to 96 characters so the
  sweep's existing 300-character bound cannot discard all numeric diagnostics.
  The original fault note remains unchanged. `test_journal_diagnostics.py` has
  active/sparse/excluded controls; `test_sweep.py` proves five genuinely signed
  SQLite rows including FAULT plus unresolved continuity. Independent reviews
  caught the bounded-FAULT omission; pre-fix controls fail and retained re-review
  closes it. Four paired readers from exact `ebf8462` deployed to the Pi and BOTH
  Windows installs, hashes and installed-module paths/controls proven at
  2026-10-06 21:21:56 UTC. Thirteen staged Pi suites pass. Real receipt pass read
  0/faulted 0; generated installed-source controls ACTED, not field calibration.
  Original gunicorn master and health/12 lobbies unchanged; no progs, engine,
  config, schema or historical reread. Primary build57 branch/index preserved;
  its two clean-but-stale reader paths now have owned commit-derived deployment
  overlays. Build/release from the clean inspected worktree, not that dirty tree.

- **A reproduced trajectory must also describe the ranked duration** (Patch 602).
  New finished-run PASS observations compare the engine's confirmed finish ticks
  with `replays.ticks`; the submit-time filename stamp is not that independent
  check. A different duration is HOLD, preserving measured ticks/counts. Missing,
  ambiguous or out-of-range `ticks N rows N` output is retryable ERROR, with unknown
  ticks and no counts snapshot, not a player finding. Evidence/abandon promotion,
  header/stage/source fences and explicit review precedence keep their contracts.
  No historical reread, schema, detector, engine/progs/config or Build change.
  `surfd/test_verifier_finish.py`: real POST/file/SQLite/public-board controls with
  an acting verifier stub; nine tests, five baseline failures, final zero. Both
  arrival orders, grouped companions, malformed output, approvals and abandon
  controls are explicit. Full Linux70 pass; Windows70 retain only the two existing
  admin UDP/amplification assertions. Native Pi pm_verify positively PASSes one
  existing recording with parseable matching ticks on an owned verifier port;
  that is compatibility, not detector calibration. Immutable run/sidecar corpus:
  baseline/subject269 rec,91 view,170 faulted files/173 faults, unchanged.
  Deployed exact a4a75be at2026-10-08T20:27:40Z to the Pi: only sweep and two
  controls, destination hashes exact; actual installed finish9/counts7/sources15
  pass. Canonical lock, mode600 completed DB/source rollback retained;137
  protected files/history/scalar board counts/master+worker/health12 unchanged.
  No reload or Windows game swap. Provenance/limits: `tools/p602finish.md`.

- **Angle explanations are observations, not strings to reconstruct later**
  (Patch 511). `receipts.angles_reason` stores up to 1,000 characters from the
  same captured pair as `angles`; diagnostic notes include why an existing
  rule abstained. Late view/recording updates move verdict and detail together,
  never overwriting an earlier angle FAULT. Partial reads/recovery keep the
  historical detail whenever they keep its verdict; journal-only retries leave
  both alone. A completed explicit full reread may replace both. The additive
  migration leaves old details empty, even if sources still exist. Authenticated
  admin renders literal text and says historical detail unavailable; an empty
  angle verdict says not checked, not that the recording is necessarily absent.
  This changes no thresholds, detector verdicts, signing history, ranked policy
  or automatic reread scheduling. `test_receipt_angle_reasons.py` exercises real
  signed pairs, migration and executed DOM rendering; it explicitly skips only
  DOM controls when Node is absent (83 Python checks vs 99 with Node).
  Scheduling suites compare complete rows including the detail.
  Deployed from exact `be530ead` to the Pi, final hashes 2026-10-06 20:34:30 UTC:
  18 staged suites pass, admin258; installed-source/reader83 controls pass. All
  old fields of22 historical observations match the owner-only SQLite backup;
  new details remain unknown. Live admin field/fallback and anonymous refusal,
  unchanged real receipt pass (0 reads/faults), original master/one fresh worker
  and health12 are proven. No lobbies/progs/binaries/configs/Windows install swap.
  For a selected `surfd-deploy.ps1 -Only` stage, include its unchanged import
  supports (recplot/simcheck/rcon) or staging fails before copy. Live tools default
  to the game's `tools/`, not surfd's directory. Fixture writers may prepend their
  own tools path: preload actual installed readers and assert module paths in
  installed controls; byte-identical staged code is not installed-path proof.
  The shared build57 branch diverged from main and was preserved; published source
  is on main and the isolated p511-angle-reasons worktree.

THE DESIGN IS NOT IN THIS REPO. It lives in
`C:/FTESurf-private/anticheat-plan.md` — layers 0–3, threat classes T0–T5,
phases 0–5, experiments E1–E5. Read it before touching anything below; none of
this restates it. Half the commit log since build 72 is this workstream.

IT IS OUTSIDE THIS REPO ON PURPOSE AND MUST STAY THERE. This repo is GPL and
published to dl.proto.bar; the plan names live bypasses, the Layer 3 detection
thresholds and the T5 ceiling. Quote a conclusion here when you need one, never
the document. (It was in `C:/Users/Lex/.claude/plans/` until 2026-09-18 under a
generated slug — tool-managed, unbacked, and the only copy. That one is now
bannered as superseded.)

**A SECOND PRIVATE DOCUMENT SITS BESIDE THE PLAN: `ENGINE_SECURITY.md`**, the
audit of what a server can make a CLIENT do — the engine's stufftext surface,
which is the other half of the anti-cheat argument (a client that can be made to
run things cannot be trusted to report honestly). **EVERY DRIVEN ITEM IN IT IS NOW
FIXED** (481's `fs_*` set, then items 4/7/8 by Patch 483, 5/6/9 by 485, item 1 by
487, item 2 by 488, item 3 by 489 and item 10 by 491). What is left is the audit's
LOWER-VALUE list -- a census of read-only `fs_*` commands, never armed, and Patch
485's sweep is the reason not to assume that list is harmless: `fs_indexmaps` looked
read-only and was writing and mounting. THE TWO HEADLINE ITEMS WERE THE ONES THAT DEFEATED ALL THE OTHERS: one
stuffed `alias f_newmap "<anything>"` ran its body at `RESTRICT_LOCAL`, so every
`Cmd_IsInsecure()` gate read 29 for it and 481 was a delivery-path fix rather than
a boundary (Patch 487 closed it by running a trigger alias at the alias's OWN
execlevel); and a stuffed `setrenderer "gl <path>"` named the DLL the renderer
loads, which is native code in the client process -- driven with a canary whose
DllMain wrote a marker line (Patch 488 closed it by refusing an explicit
subrenderer token from an insecure caller, WHOLE rather than screened for slashes,
because a bare name also reaches LoadLibrary through the search order); and `allskins`
was a bare `strcpy` of a server-supplied argument into `char allskins[128]`, which a
canary build measured writing 172 bytes past it (Patch 489 fixed it with the BOUND and
not a gate, because forcing skins is a legitimate server feature that must stay
server-reachable); and item 10 let a remote server DROP a connected client and
re-purpose its process into a cluster master, because `mapcluster` had no restriction
level and a client registers those commands too -- the audit's own note that the route
"needs a local/listen server first" was wrong, and arming it is what showed that
(Patch 491). What is safe to say here is in BACKLOG.md's
"Engine client-security audit" section — code site, impact class, falsifier, no
recipe. The arms are in `poc/p482/cfg/`, `poc/p483/`, `poc/p485/`, `poc/p487/`
`poc/p488/`, `poc/p489/` and `poc/p491/` there and stay there: they are working
exploits for holes that are still open, and the convention is that an arm ships
publicly WITH its fix, not before it.

- **A CLEAR IS ONLY SAFE IF THE ILLEGITIMATE SPEED CANNOT SURVIVE IT — AND "I HAVE
  ENUMERATED EVERY PLACE THE SPEED COULD BE" IS NOT A WAY TO ESTABLISH THAT.** Most
  clears in the taint design satisfy the rule by ZEROING the velocity, which is
  checkable. The one that cannot — the finish, because players coast past the line —
  went through Patch 454 and six rounds of 455 trying to satisfy it by listing the
  places speed can hide: the push carrier, the carrier's vertical component, a pending
  trigger output. **Three consecutive review rounds found a defect in the previous
  round's fix, every one of them a term missing from the list**, because completeness
  is not a checkable property and "as far as I can trace" is the only honest answer
  anyone can give about it.
  What replaced it is a LATENCY BOUND — **but it does NOT dominate the enumeration, and
  the first draft of this entry said it did.** Measured after the fact: `vbsp_io_delay`
  is a bare `stof` with no clamp (`sv_entities.qc`, the only writer), and the shipped
  corpus carries 249 delayed outputs on 39 maps that reach a player through an input
  this QC implements — including a **0.5 s** `AddOutput basevelocity` on
  `surf_aquaflow`, which has an online zone file and is therefore a timed map. That is
  twice the dwell, in the wrong direction. What protects that map is the enumeration's
  `vbsp_iodelay` clause, so the two are COMPLEMENTARY: the bound covers the short and
  the unenumerated, the enumeration covers the long. Do not delete either on the
  strength of the other.
  The bound itself is that the clear waits until the body has read clear for an unbroken
  interval, on the argument that whatever was committed would have ARRIVED by then.
  **AND AN UNBROKEN INTERVAL HAS TO BE INTERLOCKED, NOT ANDed.** Requiring
  `elapsed >= D` AND `reads >= N` is bankable: send N-1 clear packets at a low
  `cl_netfps` (a client cvar the server cannot refuse), stop, and the streak sits one
  read short with both bounds pre-paid for as long as you like — then commit the pending
  write inside the Nth packet's usercmds, which run before the gate, and the required
  latency is 0. The streak must break when too long passes between OBSERVATIONS, which
  is what makes the interval an observation window rather than a span. It is stronger than waiting,
  because the carrier cash-out runs in `PlayerPreThink` — inside `SV_RunCmd`, before
  `PlayerPostThink` where the gate lives — so a pending carrier does not merely arrive,
  it becomes `.velocity`, which the gate already measures. Sized from the longest
  latency the tree has measured: an `OnEndTouch` at 0.06–0.09 s (four to six packets),
  a carrier at one command. **It needs BOTH an elapsed-time and an observed-read bound**
  — a read count alone is bought by bursting packets, and elapsed time alone credits a
  gap in which nothing was observed, which is the completeness argument again one level
  down. If you add a term to a gate like this, ask first whether the gate should stop
  depending on the list being finished.
- Three recordings of one run, joined by filename through `FS_RunPath`: `.rec`
  (server, `sv_timer.qc`), `.view` (CSQC per-frame angles, `cl_replay.qc`),
  `.hid` (engine raw-input journal, `in_generic.c`). A forgery has to be
  consistent across all three. Taint bits demote and never accuse:
  `TF_CHEAT/NOJOURNAL/NORULESET/NOPROFILE/NOMAP/NOCLOCK` in `sh_defs.qc`,
  consumed by surfd's `certifiable()`.
- **THE MOVE TRIPLE IS THE ONE COLUMN WITH NO RANGE TEST ANYWHERE** (Patch 493,
  mod-side): the engine copies a usercmd's `forwardmove/sidemove/upmove` into
  `.movement` with a bare assignment, and the only bound is the client's wire bound
  at ±32767.  `SV_MoveBoundFrame` compares each command's largest |axis| against
  `run_movebound` (2000, 0 = off, latched per map beside `run_startcap`), counts the
  ones over it, keeps the largest value the attempt sent AT ALL, and sets
  **TF_MOVEOOR (262144) -- a marker, never a demotion**, because THREE HONEST ROUTES
  PASS ANY CONSTANT: the move cvars are plain archived cvars (`cl_movespeedkey`'s
  engine default is 2.0 where `default.cfg` ships 1, so +speed sends 900),
  mouse-strafe adds `m_side * mouse_x` per command, and **A GAMEPAD WITH +speed HELD
  IS UNBOUNDED** (`in_generic.c`'s IN_MoveJoystick scales jstrafe by
  `360 * cl_movespeedkey` then multiplies by `cl_forwardspeed` without
  re-normalising).  The 2000 is a judgement over a corpus, not over a rule: 450 is
  the maximum of 1,342,728 axis values in 63 fleet runs.  The file states its bound
  as a `movebnd` header key from the SAME latch the check reads, so reccheck can
  fault the bit against the file's own `in` rows in both directions -- and no key
  means abstention on the `proprule` precedent, which is what keeps this tree's own
  Patch 358 fixtures (`side=2325 / fwd=-1067`, no bit) honest.
  **THE HEADER FLAGS WORD IS ONLY REWRITTEN AT A REAL CLOSE.**  `SV_RecFlagLine`
  reserves a fixed width at open and only `SV_RecClose` / `SV_RecKeepEvidence` seek
  back to it, so a Multi-Session park and a save-state prefix are closed files
  reading `flags 0` no matter what the run did.  That is why every header-bit
  cross-check in reccheck sits behind `end`, and it is not a guess: Patch 493's own
  first harness graded a park, got `flags 0` beside 284 rows over the bound, and the
  ungated check accused a file the writer never finished.
  Arm: `tools/p493move.py` (26 checks) with `cfg/test/p493{move,off}.cfg`.
- A FORGIVENESS HUNG ON ANYTHING `SV_TimerArm` TOUCHES IS A FORGIVENESS THE MAP
  HANDS OUT. `SV_TimerArm` is reachable from ordinary map DATA, not only from a
  gesture: 21 shipped maps have two abutting start regions whose seam re-arms on
  every crossing, and 66 have a velocity-keeping `trigger_teleport` landing inside
  a START region (both measured over the 1316-bsp corpus). Three attempts at the
  hopped-start rule died on this before Patch 445, which is why the rule now hangs
  its clear on a short, named list of callers instead of on a state change.
- AND THE TEST THAT SETTLED IT IS "DOES THE CLEAR KEEP YOUR SPEED". A taint on a
  pre-start attempt is only worth laundering if the prespeed the chain built
  survives the laundering, so a clear paired with `velocity = '0 0 0'` cannot be an
  exploit however reachable it is, and a clear that leaves the speed on is one
  however narrow. That is checkable, where "is this reachable from map data" needs
  a corpus census every time. Patch 445's three callers each zero or abandon the
  velocity; `SV_TimerArm` does not, and that was the whole bug.
- ON A DEDICATED SERVER MAP ENTITY I/O CANNOT BECOME A CLIENT COMMAND, and that is
  what makes `!r` usable as a rule. `SV_IOCommand` runs a map's `Command` through
  `localcmd()`, i.e. the SERVER console, and `ClientCommand` is the only path to
  `SV_ZoneChatCommand`. **THE DEDICATED QUALIFIER IS LOAD-BEARING AND WAS MISSING
  HERE UNTIL PATCH 445's ROUND 6:** the server's own `say` is registered only
  `if (isDedicated)` (engine `server/sv_ccmds.c`), so on a LISTEN server
  `localcmd("say !r\n")` runs the client's `CL_Say_f`, forwards as that player's chat,
  and does reach the gesture. It buys nothing (the forced `!r` zeroes velocity and
  voids the run, and a listen server cannot submit to the board) but the absolute
  form of the claim is false.
- THE `say`/`echo`/`print` ALLOW-LIST WAS NOT ITSELF A BARRIER, and Patch 446 is what
  made it one. `SV_IOCommand` checked the first token and passed the WHOLE string to
  `localcmd`, and `Cbuf` splits on an unquoted `;` — so `echo x;set run_starthop 0`
  passed the gate and ran both, at a restriction level that admits anything registered
  without an explicit one. `run_starthop` is read live every packet, so one poisoned map
  switched the whole hopped-start rule off; `run_evidence_days` would have made the next
  sweep delete recordings. 446 refuses `;`, CR, LF, `"` and `$` for an allow-listed verb
  (measured free: 0 of 1438 shipped Command rows carry any of them).
  THE LESSON OUTLIVES THE FIX: do not hang a new rule on "the map can only say things".
  Hang it on where the command ENTERS — client stringcmd versus console — which is a
  property of two code paths rather than a list of permitted words.
- THE SAVE FILE IS AN UNTRUSTED INPUT TO THE RUN, and `state.txt` is plain text in
  the player's own `data/saves` tree. Every taint bit the format carries — or fails
  to carry — is a laundering channel: `run_t_hopped` was missing until Patch 445, so
  one `retry` forgave a marked chain for free. The grammar is additive (a key-match
  loop with defaults), so adding a field costs one line at each end and no version
  bump. STILL MISSING and in BACKLOG: any check on the BSP behind the map NAME
  (`map` is written and no reader matches it, while `infokey(world, "*mapcrc")`
  already exists with a correct third verdict), the mover state, and the five
  movevars the `SL_RowGrounded` probe judges a row with.
- THE `.rec` GRAMMAR BLOCK over `SV_RecOpen` (sv_timer.qc) IS AUTHORITATIVE,
  currently FTESURF-REC 10 when the file holds a `pause` (retry, cold load,
  Multi-Session) and 9 otherwise. pm_recsim and pm_verify replay a v10
  Multi-Session file session by session (Patch 367) and REFUSE a retry/load
  pause or anything above 10. `tools/reccheck.py` is written from that block and
  never from the writer, so a writer that drifts from its own documentation gets
  caught. Same rule for `hidcheck.py` and `.hid`.
- **A `.rec` CARRIES ONE WITNESS FOR THE PLAYER'S INPUT, NOT TWO, so any detector
  that cross-checks one input column against another is vacuous in every file in
  this tree.** `keys` is DERIVED from the move columns: `SV_RecKeys` sets
  FSI_LEFT/RIGHT from the SIGN of `movement_y` and FSI_FWD/BACK from
  `movement_x`, and `momreimport.py` applies "the same rule as SV_RecKeys" -- so
  LEFT and RIGHT are mutually exclusive by construction and an overlap statistic
  reads a perfect score for everybody. Same for jump: `fl` bit 4 and `keys`
  FSI_JUMP are both `e.button2`, and measured they agree on every row of all 5571
  `.rec` files in `data/`. This is why `tools/reccheck.py`'s key-mask check is
  self-referential (BACKLOG), and the general rule is Finding E's: **a check
  built on a field the same writer derived from the field it is checked against
  measures nothing, however clean it reads.** Cross-check the client's `.view`
  against the server's `.rec` instead -- those are two machines.
  Measured by `tools/census/assist.py census`, which prints the agreement count
  beside it so a future reader sees the 0 disagreements rather than trusting this.
- THE `.hid`'S TWO "FRAMES" COUNTERS ARE TWO DEFINITIONS, and confusing them reads
  as a defect: `end <dt> <abs> <events> <frames> ...` counts DRAINS, i.e. `f`
  rows, while `in_jrn484_frames` counts VIEW SAMPLES the identity governed. The
  relation is exact and worth remembering: `#v == in_jrn484_frames +
  in_jrn484_skipped + 1`, the +1 being the first view, which
  `IN_Journal_CheckIdentity` returns on before `vcount++` (`!in_jrn_vhavelast`).
  Verified both ways on `p484_B.hid` (678 `f`, trailer 678) and `p486_B.hid` (182
  `v`, log reads 181, skipped 0). And `f` appears **iff a device event was
  drained** -- `IN_Journal_Frame()` has one call site, inside IN_Commands'
  non-empty-drain branch -- so a journal with no `f` rows is a journal of nothing
  happening, not a journal with a missing record.
- HID DIAGNOSTIC DENOMINATORS (Patches 515–517): union relevant-mouse coverage
  can conceal a silent axis. Use `identity_yaw_*` / `identity_pitch_*` coverage
  from actual judged sets, not governed-candidate totals. Each axis's exclusion
  dictionary plus its judged count accounts for emitted `v` records; earlier
  global gates omit unexecuted coverage rather than inventing a measured zero.
  Seed records are not comparisons. Counts-join windows partition into initial
  exemption, checked and absolute-input unjoinable; transforms overlay the latter
  two groups and exclude the same initial window. Spans/windows describe source
  records, not elapsed time or render frames. These additive measurements are
  available in verbose HID reports, NOT durable per-receipt metric snapshots:
  the stored 300-character reason remains bounded prose. No-window/invalid
  profile paths cannot be reconstructed as present-day measured zeroes.
- Version bump rule: new header keys and new record types are additive and need
  no bump (readers skip what they do not know). Bump when `end` grows a field or
  an existing line CHANGES MEANING. Then update, in reccheck.py: `COLUMNS`, the
  `HEAD_Vn` ladder, the allowed-header ladder, the trailer-width ladder, and the
  `r.info` print tuple — that tuple has silently swallowed a new field four
  builds running, because nothing automatic reads it.
  - "Additive" is safe for reccheck, NOT for the verifier: pm_recsim skips
    unknown records. A record that changes physics or the run's continuity
    (resume, pause, session) must be taught to pm_recsim/pm_verify in the same
    patch, either consumed or REFUSEd. pm_verify REFUSEs any version above the
    one it reads (Patch 356).
- A new recorder COUNTER or change-latch goes in four places, or a resumed file
  lies: `SV_RecOpen`'s reset, `SV_RecRecount` (every rewind recounts from the
  body), `SV_RecTrailer`, and sv_resume.qc's ms.txt (`SV_MsWriteMeta` /
  `SV_MsReadMeta` / `SV_MsRecAttach`).
- After ANY change here: `python tools/test_reccheck.py` (0 failed) AND a corpus
  sweep over `ftesurf/data/runs` — the fault count must not move. A false note
  about a correct file is the one thing these tools may not produce.
- A MAP ENTITY THAT WRITES A PLAYER'S VELOCITY MUST MARK ITSELF. The hop rule's
  only view of a jump is velocity_z crossing PM_NONJUMP_VEL, so any direct write is
  read as a jump unless the site sets `run_pushed` — keep its writer list in
  sv_entities.qc current. `trigger_setspeed` was missing for three patches and
  falsely accused players on 16 pads across 9 maps (Patch 412). Two rules, each
  paid for with a withdrawn patch:
  - ONE PACKET WIDE. `run_pushed` is cleared every packet, so it cannot cover a
    consequence that lands later, and a horizontal write clipped upward off a
    STANDABLE slope on the next move still is not covered (Patch 412's NOT DONE
    note). The carrier path survives only because it re-arms every command; a site
    that writes once has nothing to re-arm.
  - SIGN DISCIPLINE. A flag that WITHHOLDS an accusation must not be reused to
    GRANT credit. Reversed, `run_jumpcmd` turns "press on with the accusation"
    into "holding +jump buys the mover's rise" (withdrawn 411b, sv_timer.qc).
  Both directions are defects: a false accusation taints an honest run, a false
  acquittal ranks a driven one. Say which one a change trades for the other.
- EVIDENCE BOUNDARY, exactly: `warp` = a direct write of origin or velocity
  OUTSIDE the mover by a map entity, or by two client commands: `zone` (`!r`,
  zone_goto) and the zero a replay/rewind pin imposes on a body with speed or a
  carrier (`warp ... pin`, Patch 477; the hold's per-packet zero and the
  release's are not written). `ride` = the basevelocity carrier handed to
  the mover (a span: `arm` persists until changed, `pay` is the cash-out). A
  PORTAL crossing (`linked_portal_door`) is committed INSIDE the mover by the
  engine (`PM_PlayerTracePortals`), so no QC site sees it; the engine publishes
  it (Patch 346) and v9 writes the `portal` record. None has been captured live
  yet.
- THE VERIFIER: `pm_verify <file>` (engine, headless server on the file's map)
  replays a finished v9 or v10 file exactly and runs the timer's own zone scan, printing
  `VERIFY <file> PASS|HOLD|REFUSE <reason>` (never FAIL). It is exact only on the
  same binary and pin. It REFUSES on a zone-table mismatch before replaying a
  single tick, so a file recorded under a `cfg/test/*.zones.json` fixture only
  verifies with that same fixture installed at `maps/zones/local/<map>.json`. It replays with the file's own trace cvars
  (`pm_trisoup_bevels`, `pm_rotatedboxhulls`, `pm_portalcsg_scanall`; Patch 358),
  warns when they differ from the server's, and restores the server's values
  after. `surfd/sweep.py` runs it from proto's cron into the `verdicts` table.
  A board row reads Verified when its replay's latest current non-ERROR
  verdict is PASS or the owner approved it (`VER_SQL`, surfd.py). "Current"
  means newer than the file (`at >= replays.submitted`). Reasons never leave
  `/admin`.
  It follows a stage restart through the progs' `SV_VerifyRestart` (Patch 369),
  and a warp or restart written after its packet's sample (`!r`) acts after
  that packet's zone scan. At each Multi-Session pause it checks the clock (the trace's ticks at the
  pause's closing horizon = the pause's = the session's) and the resume (the
  seed within 0.0001 of the replayed state: the save writes %.4f) -- HOLD
  otherwise. A ghost window (Patch 373) runs no zone scan; it HOLDs on input
  once the window's rows went empty or 1 s in. Run verify harnesses whose
  subjects must PASS on the Pi: this Windows box builds one physent fewer at
  surf_derpis's finish than the Pi and the live server (Patch 373).
  Harnesses: `p349verify`, `p352slots`, `p356newer`, `p358trace`,
  `p367verify`, `p373verify`.
- A LOBBY STREAMS. A `retry` reads it back into a buffer first (Patch 368,
  SV_RecDestream). A save copies the stream's prefix to its slot a 512 KB
  chunk per packet (Patch 375); a load of the same lineage truncates the
  stream in place (`fsize(fh, n)`), any other rebuilds it from the slot.
  Anything that closes, renames or truncates the part file calls
  SV_RecCopyFlush first. The first load after a posted stage is always cold
  (Patch 360 keeps the stream as evidence). `p375sv/p375cl`, `p375bsv/bcl`.
- MOUSE COUNTS (Patch 376): a 376 client sends its input-ring and read sums
  in the prydon cursor floats when serverinfo says `fs_counts 1`; the progs
  write `mc` records and pm_verify HOLDs on ring != read. `p376sv/p376cl`.
  `sl_prev`/`sl_next` LOAD the save they step to -- a harness that follows
  them with `sl_load` loads twice.
- THE SPECTATE HOLD (Patches 380/382) keeps a run RANKED. `cmd rec_spec <n>`
  (entnum; 0 starts the countdown) sets `.run_pmhold`, and the engine then runs
  ZERO mover ticks for that player and links it without touching triggers
  (`*pmhold` "1" says the engine can; the progs refuse a ranked hold without it).
  A MOVETYPE_NONE pin is NOT a hold: the duck timer and stamina decay under it.
  The window is `spec 1|0` edges plus TF_SPEC (32768, a marker, not a class);
  the trace stays continuous, so a replay needs nothing from them, and pm_verify
  checks each edge where it sits among its row's warps. Anything new that moves
  a player, idles or rewinds a run, or parks it must call `SV_SpecRelease` FIRST
  (the funnels: disconnect, SV_Shutdown, retry, load, SV_ZoneMove, setpos,
  respawn), and nothing may write to the recorder while `run_pmhold` is set.
  Entry is refused while a trigger is touching the body or has not seen it leave.
  STAT_FS_SPEC 103: 0 off, n = watching entnum n, -3..-1 the countdown.
  Harnesses: `p380verify` (derived files), `p382a/c/d` (+`p382t/e`), `p382verify`.
- SPECTATING (Patch 385, `client/cl_spectate.qc`) drives that hold. The camera
  integrates IE_MOUSEDELTA itself and NEVER writes VF_CL_VIEWANGLES, so the
  body's aim cannot move (the .hid shows no 'v' record inside a window).
  `Spec_Active()` (cl_keys.qc) is the one "spectate owns the input" test --
  asking, leaving, watching, counting down, or the stat says so; anything new
  that opens over the game must refuse under it, as the ghost and replay do.
  Under it a key press runs only a bind on SPEC_CMDS, looked up with
  `Keys_BindNow` (the bind for the modifiers held -- plain `getkeybind` misses
  `bind shift+q`; an unbound right Alt runs left Alt's), and a key with a turn in
  ANY modifier slot is swallowed (`Keys_TurnAny`); a new menu key that must work
  while watching goes on that list or into a handler ahead of it in
  CL_InputChain. Two routes stay open, outside CSQC: a console `+left` and an
  F-key under the engine menu; the per-frame release cuts a held turn
  from either, not a force_centerview.
  The usercmd and its time are zeroed for the whole window, so after the release
  about one round trip of anti-hover moves land as no-input rows (one on a local
  host, p385rec).
  Handles: `spectate look <dx> <dy>` (a mouse delta through the chain),
  `scores pick <name>` (a row click minus the hit test), `spectate status`,
  `spec_trace` for `tools/spectrace.py`. Harnesses `p385view` (+`sv/own/two`),
  `p385hid` (+`t`), `p385rec` + `p385verify` (a recorded run, surf_666 fixture).
  A three-client harness needs `set sv_playerslots 4` (default.cfg allows 2;
  the third client just retries "full").
- At a frame rate near the 66 Hz stream a raw-sample control jitters between
  0, 1 and 2 samples a frame instead of stalling: grade the rate band, not the
  no-step fraction alone (p385view P4c).
- To put MORE THAN ONE COMMAND IN A PACKET use `cl_c2spps`, not `cl_netfps`.
  Lowering cl_netfps makes one LONGER command ("cl_netfps 20 -> one usercmd per
  50 ms"), and CSQC re-pins it to `pm_ticrate` at every map load
  (`Net_MatchTicrate`), so it only sticks if you set it AFTER the map. `cl_c2spps`
  drops outgoing packets (`cl_input.c:3570`, at most 2 in a row) and QW's backup
  moves then travel together — 3 `in` rows per packet. This is the only way to
  reach the multi-command paths a LAN never exercises.
- Experiment convention: numbered (E1…), one cfg per arm in `cfg/test/`.
  PRE-REGISTER the predictions and the falsifier in the cfg header before
  running; keep a CONTROL that must still fail (a harness that merely got looser
  improves both); write the result back into the header afterwards, INCLUDING
  the predictions that failed — build 85's did, and the failure was the finding.
  Each prediction must name an observable the change can actually move, and
  every changed call site needs a subject that only it affects. p358 first
  "verified" a restore through a cvar string the patch never writes.
  When you DERIVE an arm from another cfg (`sed` on log_name and a path is the
  usual way), rewrite the header — a RESULT block inherited from the source
  states another run's numbers for this one, and a stale RESULT is worse than
  none. Two of Patch 403's arms shipped that way and the review caught it.
- Capture pattern for a live recording: a run only closes at the finish, which a
  scripted walk never reaches. So the harness holds the run open at the end and
  an outside poller copies `data/parts/0.rec` during that window (an abandoned
  stream is removed on quit -- unless the run passed `run_resume_min`, see
  below). `b85ride.cfg` is the current worked example.
  On a lobby, copy `data/parts/p<port>-<slot>.rec` from the Pi over ssh during the hold
  (`p352live.cfg`). A copy taken mid-write ends in half a row.
- THE RUN NONCE (Patch 416). The server draws 128 bits at `SV_RecOpen`, writes
  `nonce <hex32>` in the `.rec` header, stuffs it to the running client, and sets
  **TF_NONCE (131072)** when that client echoes it (`cmd rec_nack`). A resume
  draws a fresh one into the body as `nonce <mt> <hex32>`; a retry or save-load
  re-publishes the one in force (`SV_RecNoncePublish`), and a COLD load adopts the
  nonce the rebuilt file's header states. MARKER ONLY -- not a class, not in
  TF_UNCERT, nothing demoted for its absence, and it must stay that way while
  pre-416 clients exist: the attacker picks which silence they present.
  reccheck FAULTS a v9+ file whose flags claim the bit with no nonce anywhere;
  the converse is never a finding.
- THE RUN RECEIPT (Patch 417). At the run-end edge the client signs five lines --
  server, nonce, ticks, sha256 of its `.hid`, sha256 of its `.view` -- with an
  Ed25519 key kept in `fskey` beside `qkey`, and the server writes
  `data/evidence/<map>/<runid>.rcpt`. Check one with `python tools/rcptcheck.py
  <file|dir>` (`--hid`/`--view` to hash the files, `--tamper` for the negative
  control, `--server` to check the address binding). THREE RULES THAT COST
  SOMETHING TO LEARN: a server may not ask a client to sign (`rec_sign` refuses
  `Cmd_FromGamecode()`, or a relay attaches a victim's key to your run); the
  statement names the server the CLIENT's netchan is talking to, which is what
  makes a signature non-portable; and the server refuses a receipt while the run
  is still recording, or the commitment is not made at the finish.
- EVIDENCE UPLOAD (Patch 418). `run_evidence_ul 1` takes the client's `.view`,
  `2` also takes the `.hid`; the client's own switch is `rec_upload`. The client
  stages to `data/staged/<nonce>.<ext>` and ARMS it; the server asks after the
  receipt lands (`sv_recupload <entnum> <nonce> <path> [path2]`) and the files
  arrive as `data/evidence/<map>/<runid>.<ext>`, swept by `run_evidence_days`
  with the recordings. THE REQUEST CARRIES NO PATH THE CLIENT READS -- it names
  the RUN and the KIND (`rec_ul_send <nonce> view|hid`, stuffed) and the client
  answers from the slot it armed for that run, or not at all. That asymmetry is
  the security argument; the nonce is what stops a LATE answer being the NEXT
  run's file, which is not a corner case (see the race arm). The client holds
  four arm slots -- two runs -- and `data/staged/` keeps two runs' files,
  because a run's second file is asked for only when its first has arrived.
  One chunk per request -- enforced by the packet sequence, not just by a flag
  -- written to `<name>.part` and renamed at 100%; a completion carrying no
  bytes is discarded, and a teardown deletes the part. A CLIENT THAT CANNOT
  ANSWER SAYS SO: `rec_ul_send` with nothing armed, or a file over the client's
  4 MiB cap, sends the `snap` stringcmd, which is QuakeWorld's existing "I
  decline" and reaches the same teardown. An armed destination nobody has
  answered expires in 15 s (a round trip), one with bytes arriving in 120 s of
  silence -- two clocks, because holding the first for two minutes also blocked
  the next runs' evidence behind it. A loopback client is never asked: on a
  listen server the recording is already here.
  `rcptcheck` now COUNTS the receipts that commit to evidence which is not on
  the host ("N of them commit to evidence that is not on this host"). That is
  not a fault -- an upload can legitimately not arrive -- but before it, a
  client that signed digests and handed nothing over looked exactly like a
  server with uploads switched off. Sizes decide the default: a `.view` is 2.93 KB per second of run
  (20 KB for 7 s), a `.hid` is 110 KB (8.38 MB for 76 s), 38x more.
  ONE UPLOAD AT A TIME PER CLIENT. A sidecar is one <=768-byte chunk per round
  trip -- 459 of them for a two-minute run, 25 s at 30 ms RTT and 80 s at 150 --
  so on a lobby the NEXT run finishes while the last one is still arriving. That
  request is refused and logged (`sv_recupload: <n> is still sending <path> --
  not asking again`), so **a run may legitimately have a receipt and no
  sidecar**; rcptcheck calls an absent sibling absent, not a fault. A request the
  client never answers expires after 120 s of silence, and every teardown (drop,
  cap, `snap`, expiry) DELETES the partial file -- a truncated `.view` beside a
  recording reads as a digest mismatch, which is the shape of an accusation.
  `run_evidence_ul 2` IS A LAN AND SHORT-RUN SWITCH: at 110 KB/s the client's
  4 MiB cap refuses any journal past ~38 s of run, and one that fits is 17,000
  round trips. Collecting journals from a public lobby needs a transport that is
  not the netchan.
- THE SIDECAR IS CHECKED AGAINST THE RECORDING, not just hashed. `reccheck`
  joins the `.view`'s frames to the `.rec`'s `in` rows by run tick and compares
  angles; `rcptcheck` reaches it by RUNID, so one command covers signature,
  digest and content. THREE RULES, and `reccheck.py --tamper-view <f.rec>`
  re-measures the sensitivity of all three on any pair -- the only honest way
  to quote one:
  - ONE-FRAME (v9 only, `ANG_SOLO` 0.05 deg): a tick that held exactly ONE
    rendered frame must agree to the `%.2f` print plus the wire quantum,
    because the usercmd was built from that frame. The tight rule, and the
    only one that discriminates on a camera that never turned.
  - SWEEP (`ANG_CUT` 3x the tick's own sweep, on over `ANG_HOLD` 5% of moves).
  - RUN LENGTH (`ANG_RUN` 250 consecutive), which is what sees a splice.
  Cut from 339 pre-v9 pairs plus 21 honest v9 ones. The real findings are
  `surf_garden/main/cheat` and `surf_demise/main/cheat`, which do pair a
  recording with another run's sidecar.
- THE JOIN HAS AN OFFSET AND IT IS NOT OPTIONAL. The `.view`'s tick column is
  `STAT_FS_TIMERTICKS`, a server stat read out of the client's last snapshot,
  so on a connection it lags `in.mt` by the round trip. AT 30 ms AN HONEST PAIR
  FAILED BOTH SWEEP RULES -- and every lobby client is remote while every file
  that calibrated the cuts is same-machine. The offset is READ OFF THE FILES
  (frames indexed by their printed angles, moves vote on the tick difference),
  never searched inside a window: a window has an edge and the edge convicts.
  Reported as `angle_lag`.
- IT ABSTAINS MORE THAN IT JUDGES, AND EVERY ABSTENTION IS LOAD-BEARING --
  each of these was a false fault on an honest run before it existed:
  - a GHOST window is a legitimate disagreement between exactly these two files
    and `cl_replay.qc:1730` says so. Exempt from the `.rec`'s windows, NEVER
    the `.view`'s, or a forger declares one ghost over his whole run.
  - a resume/retry/pause/session moves the tick epoch: no angle rule judges
    that file, including the two that convict.
  - the tight rule is gated on the ANGLE SOURCE (`in rows`), not the file
    version: `check_rec` falls back to `.v_angle` samples for any file with no
    `in` rows, at any version, and 0.05 deg against that stream faults 11
    honest pre-v9 pairs.
  - under `ANG_SOLO_COVER` 75% cover it reads `PARTIAL COVER` and surfd stores
    `BLIND`, never `OK`. Coverage is a line count in the attacker's own file,
    so it gates the CLEAN verdict and not the fault: hiding ticks costs a
    forger his `OK`, which is all it buys and is worth saying as such.
  - a non-finite column is its own fault, and a sidecar too broken to join at
    all makes the RECEIPT read FAULT rather than leaving the verdict empty.
  STILL OPEN AND DEMONSTRATED: a save-lock hold moves the same epoch and writes
  NO record of it (`SV_RecPause` is only reached on a cold rewind), so an
  honest held run is still convicted -- 33-41% of one-frame ticks past cut,
  cover reading 100%. The run is kept (`SV_TimerFreeze` marks it practice,
  which is `RT_LAST`, not `RT_NONE`), so it reaches the board. DO NOT TREAT AN
  ANGLE FAULT ON A RUN THAT MAY HAVE BEEN HELD AS A FINDING.
- CROSS-RUN SIMILARITY IS COLLECTED AND NOT ENFORCED (surfd schema 10,
  `surfd/simcheck.py`).  A run submitted twice -- a PLAYBACK of a recording rather
  than a performance -- produces two clean board rows and nothing else in this tree
  sees it, because `pm_verify` is an exactness check and PASSes a faithful playback
  by design.  `tools/census/recsim.py` chose the statistic and the fleet corpus
  calibrated it (positive min 1.0000 against negative max 0.5866, a clean 1.70x
  separation over 20 independent pairs), so **the sample and not the metric is why
  this stores and does not gate**: only 8 of those 20 pairs are cross-identity, and
  a similarity gate's hardest honest case is one player replaying one map.  A
  threshold picked from 20 pairs would be a guess in a measurement's clothes, so the
  sweep accumulates pairs from live submissions instead.  THREE RULES, each of which
  a review or a test caught:
  - **STORE-ONLY, EXACTLY AS SCHEMA 7's `receipts` TABLE WAS.**  Nothing in
    `VER_SQL` reads `sims`, no badge moves, no run is demoted and no public route
    exposes it.  `test_simcheck.py` arm 4 asserts that by grepping the three files
    that could have wired it in, which is the arm that would catch this becoming a
    gate by accident -- the one defect here that would hurt a player.
  - **A SKIP IS STORED AS A SKIP.**  `verdict` carries `skip` plus a reason beside
    `compared`, because a pair that could not be judged is not a pair that
    disagreed.  Two 9-move stubs agree over all 9 rows and read 1.0000, which is
    arithmetically true and means nothing; arm 5 pins that the floor turns it into a
    skip AND that the same pair with the floor lifted does read 1.0000, so the skip
    cannot pass by never having compared anything.
  - **THE IDENTITY IS THE GUID DIGEST, NEVER THE NAME.**  `same_who` is stored per
    pair and every figure is reported split on it, because a single max is the number
    that misleads.  `recsim.who_of` matches the trailing 8 hex WITHOUT requiring a
    dash in front, deliberately: `FS_PlayerSeg` files a name that slugs to "" under
    the bare id (`0001000_26c95e00_run.rec`), which a dash-anchored pattern reads as
    no identity.  (`1proto-` vs `proto-26c95e00`, the case first given for it, reads
    the same under both.)  The cost is that a netname ending in 8 hex characters
    reads as an identity -- a census imprecision in the safe direction, since it can
    merge two identities and so UNDER-report cross-identity pairs, never invent them.
  The comparison is NOT re-implemented: `reccheck` owns the `.rec` grammar and
  `recsim` owns the move stream, and `simcheck` calls `recsim.compare_paths`, which
  is the rule `rcptcheck` follows when it delegates to `reccheck`.  A host without
  `recsim.py` keeps migrating and keeps sweeping; the step stores nothing and
  `similarity skipped: no recsim.py found (tried: <TOOLS>/census/recsim.py)` rides
  on EVERY tick's sweep line (each tick is a new process, so the "once" this file
  used to promise never held).  Only the caller's TOOLS, else SURFD_TOOLS, is
  searched.  `sweep.py --sims 0` disables the step, note and import included;
  `--dry-run` prints the pending count and the identity split.  The comparisons
  run with no transaction open (test_simcheck arm 10): inserting between them
  held the write lock (peers-1) x ~88 ms, and /api/run 500'd behind it.
  **A RUN WITH NO COMPARABLE PEER IS NOT PENDING EITHER.**  `compare_run` stores
  nothing for it, so a `pending` selecting on "has no sims row" alone re-picked it
  on every tick and crowded out newer runs once the limit was reached.  Imported
  tiers are excluded for the same reason a lone run is: another community's run under
  another game's physics cannot be a playback of ours.
  **P524-526: VALID ZERO IS NOT UNAVAILABLE.** Required malformed move columns
  abstain for the whole source; parse to locals before parallel appends. Strict
  shared comparisons and CLI diagnostics distinguish I/O from successfully read
  no-input files. Tolerant standalone parsing remains available, but its None
  is not proof of absence. A zero-agreement pair retains a positive comparison
  denominator; a true zero-opportunity result abstains. `test_recsim_*.py` and
  `test_recsim_observations.py` prove positive, unavailable and measured-zero
  arms through the actual reader/storage/history boundary. This is not general
  grammar validation, pair-completeness, calibration or historical backfill.
  When checking corpus faults, retain sidecars: a REC-only private copy does
  not reproduce the complete REC/view reader result.
- EVERY v9 `.rec`/`.view` PAIR IN data/ HAS A NAILED-DOWN CAMERA (every 416-419
  fixture drives its route with `setpos` and `noclip`) and so does nearly every
  lobby run, which is why the one-frame rule is the one that works there and
  the sweep rule honestly reports `BLIND`. To make a swept pair: `cl_yawspeed`
  + `+left`/`+right` INSIDE the run, then a `setpos` to restore the heading
  (`p420live.cfg`); `tools/p421corp.py` drives a batch of them.
  AND DO NOT SET A THRESHOLD FROM ONE FRAMERATE. This file claimed for a day
  that the v9 cuts were ~400x looser than needed, from a single run at
  `cl_maxfps 100` -- at or below the mover rate the client builds one usercmd
  per rendered frame, so the two files carry the SAME NUMBER by construction.
  Across 30-500 fps the worst honest move is 1.49 against a cut of 3, so the
  cut stays. `cl_netfps` is not an axis either: `Net_MatchTicrate`
  (`cl_main.qc:108`) pins it to `1/pm_ticrate` on every map load.
  Every measurement behind the above is in the anti-cheat plan, not here.
- AN ABANDONED RUN KEEPS NO `.rec` UNLESS IT POSTED A STAGE.
  `SV_RecKeepEvidence` returns early on `rec_rec_posts <= 0`, so a main-leg run
  that is walked away from leaves a `.rcpt` and a `.view` and nothing to join
  them to. 37 of this tree's 38 receipts are that shape; "no recording to check
  against" is normal, not a fault.
  Since Patch 426 a KEPT abandon (one that posted a stage) takes its receipt:
  the server holds the run that ended (`rec_end_*`) until a receipt signing its
  ticks arrives. Its receipt asks no upload and names no `.view` (RT_NONE).
- EVIDENCE RETENTION REACHES EVERY MAP, NOT THE LOADED ONE (Patch 418, after
  review). `SV_EvidenceSweep` globs the current map's directory at every map
  init and, where `run_evidence_sweepall 1` is set, the whole `data/evidence/`
  tree once a day, stamped in `localinfo fs_evswept`. SET THAT ON EXACTLY ONE
  PROCESS: the tree is shared by twelve lobbies, so a whole-tree sweep imposes
  that process's `run_evidence_days` on all of them. Before that, `run_evidence_days` only ever applied to maps that
  were in rotation. It is 0 (keep everything) since 2026-09-21, so both sweeps
  are no-ops until it is raised; Patch 423 warns when the drive fills. The stamp is localinfo because an SSQC global is reset by
  the map load and a cvar the gamecode creates is purged with the progs -- both
  were tried and both silently swept at every init (`cfg/test/p418sweep.cfg`).
- A SERVERINFO KEY IS PUBLISHED AT MAP INIT, so a cvar it is derived from must be
  set BEFORE the map loads: `+set run_evidence_ul 2` on the command line, not
  `set` inside the `+exec` cfg. Cost a harness run.
- `surfd/test_admin.py` FAILS TWO ARMS AT HEAD on this box (the rcon
  amplification-guard message and "three snapshots cost no more packets than
  one") -- real UDP sockets, reproducible, and nothing to do with your change.
  Baseline before chasing: restore the file from HEAD and run it.
- TWO-PROCESS HARNESS TRAPS, one run each: a RUNNING dedicated server holds
  `C:\FTEQuake\fteqwsv64.exe`, so `build.ps1`'s deploy fails with "being used by
  another process" and the next arm measures the PREVIOUS binary -- kill it
  first and read the deploy line. And a second server started on a port another
  one already holds logs "Server spawned" and then sees no clients: the connect
  goes to the incumbent, so the run lands in the OTHER log file.
- `Con_DPrintf` NEVER REACHES THE LOG FILE unless `log_developer 1` (console.c:
  `developer` echoes to the console, `log_developer` writes). A falsifier that
  greps a server log for a DPrint measures nothing.
- **AND A SERVER QC `print()` NEVER REACHES A CLIENT'S LOG, WHICH IS THE SAME
  SILENCE WITH A DIFFERENT CAUSE.** `print` is builtin 339, "unconditionally
  print on the local system's console, even in ssqc" -- the local system being
  the SERVER. It is Con_Printf, and Con_Printf reaches a connected client only
  where the qc sends it there itself (`sprint`/`bprint`). So a client-driven arm
  that asks the server for something answered with `print()` sees NOTHING: no
  error, no "unknown command", no timeout -- the stringcmd went, was handled, and
  printed somewhere the arm is not reading. Measured three ways on 2026-10-06:
  `cmd viewpos` and `cmd timer` DO appear in the client's log because
  SV_SaveLocStatus/SV_TimerReport answer with `sprint(self, PRINT_HIGH, ...)`,
  while `cmd timefmt` and `cmd ent_census` -- `print(...)` -- did not, on a lobby
  whose qwprogs.dat was sha256-verified to be the local build and which answered
  both correctly in its OWN log. **USE `print`, NOT `dprint`, for a server-side
  harness handle** (dprint would be invisible on a lobby too, for the
  log_developer reason above, and a lobby has `log_enable 0`, `log_developer 0`,
  `developer 1` -- measured over rcon), and then READ IT FROM THE SERVER:
  `cfg/test/deploy496smoke.cfg`'s header has the rcon recipe (`log_name`,
  `log_dir`, `log_enable 1`, one cvar per `execute()` call, put back to 0 and
  delete the file afterwards). A command answered by `print` is still the right
  shape for a client arm IF the arm reads the server's log -- which is the only
  honest way to grade what the fleet is running.
- EDITING ENGINE FILES FROM A SCRIPT: the tree is stored LF and checked out CRLF
  (`core.autocrlf`), and earlier patch blocks were written back as LF -- so ONE
  FILE HOLDS BOTH. A multi-line match must try `\r\n` and then `\n`, or it
  silently finds nothing. Git normalises on commit, so the mix costs nothing but
  failed edits.
- Multi-Session (Patch 365): a run of at least `run_resume_min` s is PARKED on
  every disconnect, map change and quit (QC `SV_Shutdown`; not `retry`) into
  `data/resume/<map>/@<guid|local>/save000/`. A fixture that reloads or quits
  mid-run leaves a slot there that the next run on that map is offered: clean it
  with the rest of the test data, or `set run_resume 0`.

### Patch 502 — rewind/save pictures and continuation

- Patch 502 supersedes placement-only running rewind. The server ring keeps
  bounded timer/recorder snapshots beside physics; a same-lineage timed go
  restores the prefix as **segmented**, preserves valid pre-cut snapshots,
  and synchronously removes the abandoned tail. Ended runs without available
  evidence still produce practice placements. Cold restores do not invent
  historical scalar snapshots: the drawn prefix can predate the authoritative
  ring. A cold/demoted load clears the old implicit-row pointer, not its saved
  files; a later go on the same live lineage replaces its implicit resume row.
- The client picture is `trail.txt` beside a save's existing `.view`. It is
  visual data, never run evidence. Raw samples and rendered events are rebuilt
  together on a splice. An ordinary missing picture clears the live history;
  it must not copy another run's trail into that save. Ended/replay saves
  capture their cutoff at request time. Replay poses remain practice-only,
  regardless of the source recording's timer.
- Pictures need their own terminal result, not the latest save/load operation
  or an approximate command count. A raw list can overtake a queued save, and
  a later load can replace its event. The client consumes the correlated saved
  slot/cutoff before rebasing a loaded line and retains correlation through
  display reset. Native saves serialize captured pictures; following state
  changes wait behind them. Drain a ready load and hold **in one command-buffer
  pass**: the server's same-time/row/sequence/position checks are intentional
  and unchanged. Release stays immediate; deferred holds recheck ownership.
- `tools/p502segments.py --dedicated [--stream]` isolates fixtures and uses a
  real socket. It checks frozen timed clocks, held body/recording, release,
  deep warm rewind, cold row retention, viewer overlap/load, vote and board
  edges. Its display-off arm positively seeds a stale private picture after
  the server write, at one client FPS, before the answer is consumed.
  `tools/test_p502segments.py --rig <retained rig>` falsifies stale-report,
  recorder, clock, board, load-event and loaded-body false greens.

### Similarity collector operational limits (P546–548, P551–553)

- `simcheck.summary` distinguishes missing/error (counters unavailable), empty
  (measured zero), and available. Its read-only log line explicitly states no
  sample or unavailable; it never repairs/migrates a missing table.
- Each sweep reports unresolved-primary and row-failure counts, even when zero
  pairs land. These are availability, not player findings or coverage measures.
- `--sims` remains the source-row cap. `--sims-pairs` independently caps new pair
  admissions across a pass (default 200; zero disables quietly). Existing pairs
  consume none; unresolved peers and raised comparisons do consume an attempt.
  Limit exhaustion creates no fake skip for unattempted pairs. Comparisons still
  run outside write transactions; only completed rows flush short transactions.
- Collector comparisons explicitly bound each source to 16 MiB / 200,000 moves.
  Actual capture reads at most cap+1 bytes, including ignored records and growth;
  over-budget sources abstain whole, never a measured surviving prefix. The
  reader's standalone defaults remain unchanged. Old support without the bounded
  capability is unavailable, not silently unbounded.
- New skips capture allowlisted `skip_code` categories independently of prose.
  Additive ensure leaves old codes empty; read-only old/new-schema summary/admin
  classify them as legacy unknown without backfill. Unknown codes/details are
  withheld. Fixed categories are availability/abstention, not player findings.
- `--sims-seconds` adds a default ten-second monotonic cooperative admission
  window. Loader/schema/query time counts; in-flight work and normal writes finish.
  Zero disables before support import; invalid CLI values reject before main's
  connection, NOT before the existing import-time database initialization.
- NOT a hard timeout, overall RSS/DB scan bound, complete/fair pair scheduler or
  calibration. Existing pending and first-200-peer semantics remain. Run
  `test_simcheck_collection.py`, `test_simcheck_budget_cli.py`,
  `test_simcheck_ingestion.py`, `test_simcheck_codes.py`, `test_simcheck_time.py`
  and `test_recsim_observations.py` in addition to the regular deployment suite,
  which does not auto-discover new suites. Typed observations now project fixed
  malformed/unreadable labels; empty historical codes retain legacy withholding.
- Fresh parallel Pi reviewers in a NEW shared worktree can race automatic npm
  dependency installation (`ENOTEMPTY`, errno -4051). Capture state/diff and exact
  failed run first; once dependencies are present, retry that lane with the same
  native protocol. This setup failure is not a code review or external fallback
  permission. Private logs retain failed controls and successful replacements.

### Historical similarity byte provenance (P567-569)

- Capture the existing bounded binary buffer, not a second path read or normalized
  text/moves. Compared buffers carry version1 A/B SHA-256 and byte length; skips
  and unbounded standalone comparisons do not. The collector stores validated
  capture in the same short INSERT transaction as metrics. Old observations stay
  empty, never reread/backfilled or silently rebound to current files.
- Authenticated review retains stored A/B orientation and valid metrics when
  capture is missing/invalid. Bound raw SQL projection as BLOB bytes: SQLite TEXT
  slicing stops at embedded NUL and can hide malformed trailing data. Reject
  oversize/invalid UTF-8/JSON; coalesce SQLite's empty-BLOB substring NULL so the
  legacy-empty state remains explicit. Use text-only sinks and historical/not-
  current/not-authenticity labels; there is no public badge or policy consumer.
- Reload alone does not initialize an existing collector table. After a backed-up
  rollout, run installed ensure_schema under the canonical sweep lock, checking
  original columns/rows against the pre-deploy snapshot. This adds capture only,
  not a comparison pass. Keep legacy captures empty and prove a measured legacy
  projection ACTED. Explicit new reader/collector/admin *_sources.py suites are
  required; the standard shipper does not discover them. Node-free Pi DOM cases
  skip; Windows runs the actual renderer with an HTML-sink trap.
- Verified deployment source a976089 on 2026-10-08 at03:36UTC: all34selected Linux
  programs passed, installed22cases (five inherited, three DOM skips) passed, all
  four destination hashes match and old rows/values across six live tables are
  unchanged. Reader/SQLite/file backups retained, gunicorn reload/health/401 pass.
  Broad Windows admin suite's two UDP/RCON failures reproduce exactly in untouched
  e2d621b control; Linux passes. No engine/QC/progs/Build/release change. These
  hashes prove consumed bytes, not authenticity, current files, atomic A/B capture,
  calibrated thresholds, complete coverage, hard elapsed/RSS/DB budgets or browser
  visual acceptance. Shared uncommitted work was never deployed.

## The run line (Patches 432, 449-453)

- Patch 527: `hud_edit lines` has seven rows, not 29. Player (`hud_trail`),
  demo (`hud_watch_path`) and selected board (`hud_lines_board`) lines are
  independent and on by default. Turning off board drawing retains selections.
  `lines help` lists advanced label/style cvars; their existing names still work.
  `tools/runlines_smoke.py ftesurf/cfg/test/runlines_ui.cfg` checks this in a
  private content overlay, retaining logs/screenshots and unlinking its content
  junctions. Never run the fixture in the owner's save/config tree.
- Patch 529: reset/start-save loads retain the failed line and its pre-reset
  rewind head; a new attempt begins its one-second fade. The practice extension
  stops in a start/stage boundary after placement settles. Live discontinuities
  beyond a speed-scaled tolerance are visual dashed breaks, never .rec warps.
  `runlines_reset.cfg` through `runlines_smoke.py --dedicated`, graded by
  `test_runlines_reset.py <private log>`, covers map and explicitly requested
  stage-1 attempts. P502's full dedicated prefix/save/rewind suite also passes.
  Stage 2 on surf_dune in the first rig teleported outside its start and launched
  immediately; that is not a valid standing-at-start control. Immediate restart
  while TS_RUNNING (and clock reset) still needs separate lifecycle handling.
- Patch 533 supersedes P532's visible steps: live births come from Line_Add,
  not Line_End, and alpha is a constant-rate ramp. The small unbuilt tail draws
  with stride 1 and no stale sphere culling, including first two samples; breaks
  still terminate joins. Full spheres/LOD/gain builds remain batched. Only live
  tail colours refresh, not board caches; contact/energy classifiers still walk
  the active slot rather than guessing a kind. Demo publication is one uniform
  fade, not a restarted stagger every 32 points. Static interleaved-gradient
  noise replaces the body's 16 Bayer levels: 33 actual distinct monotonic coverage
  images over 32 substeps, normal survivor colours, no animated noise seed.
  Extended private overlay: 37 alpha checks, 51 rendered screenshots including
  pending-tail/break controls; both constant half-fades are 0.4993 brightness.
  The separate dedicated reset regression still passes all five acted checks.
  No all-backend or worst-case contact-mode FPS claim; owner motion feel remains
  a human check. No authoritative evidence or movement state changes.
- Patch 532: `hud_lines_reveal 0.18` reveals newly published live/demo chunks
  from oldest to newest; 0 restores instant drawing. Heap birth stamps belong
  only to demo slot 0 and the two live/previous slots. Rebuilding never restarts
  old births; Clear/reuse and cap compaction preserve the publication contract.
  Mature demo publication composes with playhead reveal, not the run clock.
  `cl_playerfade 1` is viewer-local opaque Bayer discard on streamed Body_Predraw,
  hidden within 32 units and opaque beyond 128 (`cl_playerfade_near/far`). Existing
  body alpha stays 1; no server rule, ghost or owner avatar change. The material
  is embedded in CSQC so joining clients need no separately installed GLSL file.
  `hud_edit lines` now has 11 rows including these four controls. The private
  overlay `tools/visual_fades_smoke.py` proves 33 publication/playhead/compaction
  assertions plus 16 actual line/body screenshots. Its test-only world-free
  hooks are never deployed. A forward call to Line_StatsReset (declared later)
  crashed fteqcc without stdout in the initial extension; removing the unnecessary
  call fixed the harness. QC definition order applies to test seams too.
  Frozen product `4fdfbdf` deployed 2026-10-07, verified at 04:03:53 UTC:
  both Windows CSQC hashes/backups and Pi live/previous pair match. Clean-build
  bytes equal the tested production build; no test hooks. SSQC source is unchanged
  from P530, Windows SSQC/menu/native untouched; Pi SSQC hash stays identical.
  default.cfg matches on all three destinations and also catches up the earlier
  approved P527/P529/P530 viewer defaults (their progs shipped without that cfg).
  No movement/server-rule changes. All 12 lobbies restarted empty, remained healthy
  and were empty after controls. Fresh-cache clients on both installed engines
  downloaded matching CSQC, drew the 11-row pane/defaults and received live peer
  body streams. The actual lobby map was surf_kitsune; its existing single missing
  material is not a fade/shader or map-download fix. Owner configs/data unchanged.
- Patch 530: `hud_lines_declutter 0` (default) keeps visible labels and lays them
  into up to 16 nearby vertical lanes instead of silently suppressing overlaps;
  `1` restores the sparse grid. The existing 128-label/frame cap, view/distance
  culling and explicit mark switches still apply. Impossible density can still
  overprint. `hud_lines_telealpha 0.3` fades both dashed joins and endpoint squares.
  Ramp holds/turn grades cannot span a break. Private `runlines_labels.cfg` on a
  supplied surf_kitsune .rec plus `test_runlines_labels.py` tests 8 complete vs 6
  sparse labels, all numeric fields, record-derived marks and both off switches.
  Screenshots prove the text actually draws. Native contact bits are retained;
  adjacent ramp-plane changes and imported missing planes are NOT solved here.
  The full dedicated P502 main/edge suite and 306 reccheck checks pass.
- QC compiler pitfall found here: `fov` is LOCAL to `Line_ViewFrame`. Referring to
  `fov_y` from a new helper caused the installed fteqcc to access-violate
  (3221225477, no diagnostics). A clean same-commit build acted; storing the
  screen size explicitly for the helper restores a zero-warning build. Do not
  diagnose a silent compiler crash as an unexplained success or rely on LSP.
- P527/P529/P530 deployed from clean inspected `5ff0b3b` on 2026-10-07 UTC.
  Both Windows installs received only CSQC with immediate `.prev` hash controls;
  native/plugin, SSQC, menu, owner configs/data were unchanged. This preserves
  already-deployed water code, not a new water deployment. Pi got the coherent
  SSQC/CSQC build pair through the no-player/hash/backup/restart procedure; SSQC
  source/shared contracts are unchanged from its deployed water baseline.
  All 12 active units and live/previous hashes verified. Actual fresh-cache
  downloads with both installed native clients match this CSQC; spawned editor
  screenshots and independent help/defaults act. Heartbeats empty afterward.
  Local map content was supplied read-only to the private overlays; this is not
  a map-download/material-availability fix or completed Momentum/contact/compare
  acceptance. Existing archived fade settings are not forcibly overwritten.

- **What it draws.** `cl_lines.qc` renders a recording's path as a screen-space
  strip, slot 0 the open replay and 1-8 the board's ticked lines. On it:
  `V` where the run touched ground or a ramp, a chevron where it left one, a
  DOUBLE chevron where the jump button was down, and two grey bars where a
  SEGMENTED run loaded a save (`resume`/`retry`, not `restart` -- a stage
  restart is not a save state coming back). Numbers at those marks and at the
  peaks where vz turns over. Four colourings beyond speed: gain, contact,
  energy, air control.
- **THE MARKS ARE THE EDGES OF `Board_KindOf`**, the same three-state contact
  function the Segments column is built from (`cl_board.qc`), with none of that
  column's row-level debounce. So every segment row boundary is a mark, and a
  contact too short to become a row is a mark with no row -- both directions are
  graded by `tools/p449mark.py`, and the second count is registered per fixture
  rather than asserted to be zero. Do not write a second detector; extend
  `Board_KindOf` and both follow.
- **Marks carry their own position, never a point index**, which is what makes
  them survive the two decimations (the build-time stride and the past-the-cap
  halving) with no fixup. A mark is identified by its SAMPLE ORDINAL and never
  by its time: both bhop fixtures repeat a timestamp, because a file records one
  sample per packet and a held clock repeats it, so keying on `t` mis-assigns.
- **MEASURED AND NOT ENGINEERED AROUND:** samples are one per packet (43-65/s
  against a 66.67 Hz tick) and a bhop's ground contact is one tick, so a perfect
  hop's contact can fall between two packets and be absent from the file. The
  line misses those hops -- and so does the Segments column, from the same
  samples, identically. Do not interpolate hops the file does not contain.
- **Cvars.** `hud_lines_marks|land|leave|jump|stitch|size|gap`,
  `hud_lines_nums|speed|energy|ref|delta|vz|time|numsize`, and
  `hud_lines_win|winf` (seconds of run time behind and ahead of the playhead; 0
  = the whole line). The colouring, the visible distance, the width and the
  through-walls mode stay on the EXISTING `hud_watch_path_*` names -- nothing was
  renamed, so archived configs keep working. All of it is one `hud_edit` pane
  ("Run lines", 25 rows, tooltips), plus `set` lines in both shipped configs.
- **Your own run, live (Patch 475, `cl_trail.qc`)** fills slots 9 and 10 from
  `pmove_org`, one sample per command frame, while the run is on the clock. A
  finished or cancelled run keeps its line; the next run's start swaps the two
  slots and the old one fades over `hud_trail_fade`. A picture only -- nothing
  in it is sent or is evidence. `trail` prints both slots and the build cost.
  Graded by `tools/p475trail.py`, pixels included.
- **Reading it back.** `replay marks [slot]` dumps the mark table as the draw
  pass reads it (`lnmb`/`lnm`/`lnmz`), `replay seq` the Segments rows for the
  containment check, `replay colours <slot> <stride>` dumps `ln_col` itself plus
  the movement settings a grade was measured against, and `replay marktrace <n>`
  prints what the next n frames actually DREW -- counts, window, ia/ib, and each
  glyph's screen position and label text. Graded by `tools/p449mark.py`,
  `p449win.py`, `p451num.py`, `p452col.py`, `p453q.py` against the `.rec` itself.
  `scores lineat <slot> <path>` is the harness handle for a board line: a
  headless client has no board rows behind it, and every `scores line N` answers
  "no recording behind that row".
- **A COUNTER OF INTENT IS NOT EVIDENCE OF INK.** Text drawn from inside
  `Line_Draw` does not appear at all -- the pass is a stream of `R_BeginPolygon`
  batches the engine defers until a later 2D call flushes them, and a
  `drawstring` between two of them draws nothing. The labels are queued and
  drawn from `cl_main.qc` beside `Ev_Labels`, which has the same shape for the
  same reason. While this was broken every counter, the trace and the graded
  label text were green; only a screenshot disagreed.
- **The air-control grade is the strafe bar's own**, regime for regime
  (`cl_hud.qc`'s `HUD_DrawStrafe`), so the line and the bar cannot grade one
  moment two ways -- including its several NO ANSWER cases, drawn grey rather
  than red. It reads the movement settings from THIS server, as the bar does for
  a replay: a recording made elsewhere is graded against local settings, and the
  v9 header's `pmpin` block is where a future patch would get the file's own.
  EXCEPT THE TICK: since Patch 470 the line (every slot, `ln_tick`) and the bar
  (`rec_wt_tickrate`) grade a replay at the file's own `tickrate`. A board slot
  gets it in `Watch_LineJobWindow`, after the header -- the job's start is too
  early. `replay status` prints the bar's `bar tick/ideal/speed/regime`. The
  Segments column too since Patch 473: `Board_Tick()` (cl_board.qc) is
  `board_ov_tick` inside Watch_BuildSeq's pass, the server's live. To change a
  listen server's tick in a harness, `sv_cheats 1` first -- the movement lock
  reverts a typed `pm_ticrate`.

- **Off-ramp stage diagnostic (not a patch or fix).** The first `surf_dune`
  route rides a slope but reaches ground before a surf-to-air leave: native
  contact alone does not prove the intended off-ramp arm acted. On Voyager,
  the start's real launch pad is reached walking BACK relative to its spawn
  view; forward merely explores the floor. `tools/OFFRAMP_CONTACT.md` describes
  isolated per-native-tick/packet/sample/event/actual-render traces and strict
  counterfactual gates. Live positions are predicted while flags/run clocks
  arrive in server stats. The hold can expire on a point well after native
  contact loss; the mark and actual render retain THAT point, so render retiming
  is not established as the cause. A jump between sampled run clocks is not a
  changed hold constant. Repeated timestamps retain command/input ordinals.
  First rewind press confirms a running-run splice; the second opens. Missing
  packet anchors (including a capture terminated between two prints) are RED;
  preserve them before a labeled rerun. Structural PASS explicitly does not
  close classification, jump/trough semantics, hull/brush geometry, LOD/pixel
  acceptance, or P560's requested/native clock mismatch. Raw traces stay private.
- **Buffered off-ramp replay (tooling only).** The live per-tick `Con_Printf`
  seam perturbs sampling; use a separate clean native worktree for the buffered
  exact-input control in `tools/OFFRAMP_CONTACT.md`. Build/retain the clean server
  before instrumenting. Capture OFF/ON/repeated ON must match the clean mover
  summaries and reproduce the file's own body text; this is not bit-exact clean
  state proof. Fixed buffers dump only after capture stops; overflow rejects.
  A bare `sv-rel` server/rig cannot load VBSP: copy the installed HL2 loader into
  the PRIVATE executable directory, copy isolated default configs, and load HL2
  before `map`. Hash that external loader rather than asserting a clean build.
  Offline brush candidates must use model 0's reachable leaf brushes, not the
  entire global brush lump (inline models are in there too). Python raw LZMA
  decoding can return padding beyond Source's declared `actual` output size;
  the plugin caps at `actual`, so the geometry reader must too, not invent a
  trailing leaf or weaken alignment checks. Candidate hull/plane halfspaces do
  not authenticate the winning brush. Short raw losses can lack a nonface
  boundary crossing; no-match/unsupported geometry abstains. This still does
  not decide the early label, live render/tick-rate cadence, or P560 clock.
- **Winning trace provenance (tooling only).** A later validation/ground trace
  can overwrite BIH probe globals. `offramp_origin_smoke.py` keeps the witness
  local to each BIH trace, stamps the exact output address and carries only
  the winning nested-model/physent result into the accepted ramp buffer row.
  Fraction decrease alone is insufficient: legacy brush clips replace an
  equal-fraction winner while Source clips retain the first; actual accepted
  leaf updates must drive the witness. Cached firsttrace needs its own copy;
  recovery's synthesized normal is not the underlying collider's plane.
  Runtime leaf ordinals are not VBSP brush-lump IDs. Missing/nonparticipating
  traces, portals and solids abstain; triangles stay unresolved, not guessed
  displacement identities. Sixteen setup-only native collider controls and
  four-arm repeat/parity validate provenance, NOT winning halfspaces, edge/
  jump/seam motion, cached/recovery/portal movement paths or classification.
  Use a fresh clean engine worktree and retain private raw output. No product
  patch/ABI/recorder/hold/mark/Build/deployment changes belong to this tool.
- **Copied brush geometry (tooling only).** Offline BSP plane lumps omit loaded
  bevels; a known winning runtime leaf is not a lump brush index. The optional
  `offramp_shape_smoke.py` seam copies all loaded side planes/bounds AT THE WIN,
  with a fixed 64-side whole-shape cap/ABSTAIN and instance/capsule/direct-BIH
  metadata. Never reopen source geometry at dump. Repeating every plane for
  every contact can exhaust the harness timeout: deduplicate only immutable
  captured payloads AFTER capture, not live geometry. Payload IDs are not
  collider identities. Exact accepted-plane membership and unchanged numeric
  tick/contact+origin captures validate copied static data, not a physical exit.
  Extended/hybrid callbacks, pose/scale/capsules, embedded/entity geometry,
  recovery/portals and over-cap shapes abstain. Halfspace gaps at a loss use the
  PREVIOUS contact hull; the new tick's posture/hull is not recorded here.
  Bounds are retained, but side-gap math is not the full collision/support
  oracle. Keep authored edge/jump/seam and same-input mark/render gates open.
- **Actual contact/tick hulls (tooling only).** `offramp_hull_smoke.py` composes
  a fourth private layer in a NEW clean native worktree. Copy actual mins/maxs,
  capsule/movement type and posture state separately at accepted contacts and
  tick ends; raw stand/duck cvars are not observed hull heights. A transition
  flag alone does not imply the small hull. Seven real `PMSrc_ApplyHull` setup
  controls restore all touched state, but are NOT crouch/motion trajectories.
  `offramp_hull.py` uses EACH POINT's actual hull for copied halfspace gaps;
  capsule/non-normal samples abstain. Quiet/parity/repeat and the initial
  standing-only replay prove capture, not physical exits or posture coverage.
  Added dump rows exceeded the prior 120-second limit on the same segment;
  180 seconds completed. Retain timeout rigs; no performance claim. No extra
  capture-path queries/I/O/allocations, player ABI or mark/hold/recorder change.
  Full support-oracle, authored edge/jump/seam/unsupported movement and all
  same-input render/rate/classifier/mark acceptance gates remain open.
- **Authored native static trajectories (tooling only).** `offramp_motion_smoke`
  adds a PRIVATE command driving REAL PM_PlayerMove/PMSrc ticks on models from
  the existing BIH_Build API, not mirrored private node layouts. Fixture-only
  versus capture servers, plus a no-oracle arm, prove body/query/binding parity.
  Six32-tick cases ACT: interior ride, partial/full straight and convex side
  exits, input-driven interior short loss/reacquisition, real ground jump and
  overlapping-brush handoff. Query actual hulls AFTER ticks: stationary, down2,
  projected +/-2 against union and each brush; validate JOINT convex/box
  feasibility, not independent expanded-plane maxima. A unit wedge falsifies
  the latter. Side support disappears at an end sample BEFORE raw contact's
  falling edge; an interior raw loss retains support and previous-brush loss
  at a seam need not mean union loss. These are observations, NOT mark rules.
  No map/progs/plugin/asynchronous spawn or owner content/process needed.
  Embedded template/base stamps are provenance, not authenticity. No new
  production traces/ABI/marks/hold/clock/evidence semantics. Only these static
  fixture actors are closed: exact physical exit time, broader support/world,
  real posture/capsule/transform/entity/triangle/displacement and explicit
  cached/recovery/portal motion, plus P560 clock/live/rate/render gates stay open.
- **Independent authored triangle/slab SAT (tooling only).**
  `offramp_triangle.py` compares the retained triangle/removal standing-AABB
  queries to a complete geometric prism/box SAT sweep interval. Include all
  prism-face/box-face/edge-cross-axis projections and the four-unit BACK slab;
  face/axial tests alone ACT a false positive at an oblique back corner. The
  solver uses authored vertices, not native fractions/planes. Native collision
  bias is 1/32 along the independently derived entry normal, not a universal
  fraction tolerance. Native misses have entnum -1, zero plane/contents; guessing
  0 broke the first controls. Triangle hit ticks are 0..13, not another fixture's
  0..22. Inactive removed geometry may overlap while native removal still misses;
  that is explicitly hypothetical, not an actual embedded body. Mirroring a
  wrong fraction into all arms preserves parity but the SAT check refuses it.
  Query agreement does NOT prove native axial/broadphase semantics equal the
  ideal full slab everywhere, copied accepted geometry, physical exits or marks.
  `world-triangle-unresolved` and support ABSTAIN remain unchanged; no new native
  build/runtime actor or product/deployment claim belongs to this reader work.

## Rewind (Patch 477)

- **Request/native captions (P560).** Fractional display, sampled wire request
  and acknowledged native clock are separate. `Rewind_ResumeInfo` states the
  sampled request while browsing, waiting while pending, and native/request/
  signed delta while counting. Native caption requires correlated SLTRAILTAG
  plus valid SAVETICKS/rate; untimed practice and missing/foreign metadata never
  invent a clock. State clears/gets gated across reset/open/close. Context goes
  below key legend (.84), not on the speed/e-line (.735 initially overlapped in
  inspected pixels). Countdown caption .46; actual held main HUD is untouched.
  `stitched_rewind_smoke.py --presentation --selection-audit --visual` records
  forwarded ACTUAL draw text and timer-panel output in private overlays; nine
  compiled metadata/presentation units and five REAL SV_RewindFind repeated-
  position/window/tie cases restore the player's private test ring. Four six-cut
  warm/fresh-cold arms at caps 30/100/300 and both clients pass independent native/
  body/hold/release/ack/prefix/camera/UI gates with explicit 120ms delay; unchanged
  requested-clock test stays RED on three/four cuts. Presentation is not general
  alignment. Twenty-five UI counterfactuals, prior HUD21/12, navigation/focus/
  opposition and reader 306/0 pass. Production screenshot/status/timer control
  passes; PNG IHDR verifies 1920x1111 (video request is not size proof).
  QC pointer locals must be separate declarations: combined `*old, *m` produced
  a double-pointer cast warning/error in the private test. Initial seam/compile
  failures did not ACT. With delay/screenshots, 500ms initial save wait left go
  legitimately blocked; allow 1600ms and prove pending/hold. Inserting screenshots
  inside fixed six-cut hold/log windows misplaced late cmd-timer replies at
  high caps; run images separately, never remove body/frozen/clock assertions.
  Countdown number changes during hold; compare fixed NATIVE caption, not the
  whole draw string. Low-resolution/custom HUD and actual-device/untimed camera
  feel remain human gates. No evidence, selection, camera or engine/Build change.
  Frozen 8994b59 rebuilt clean/zero warnings and deployed to both Windows installs
  and empty-gated twelve-lobby fleet, P554 retained .prev. SSQC/menu/config/engine
  and owner source/index/personal cfg unchanged. Non-instrumented request/pending/
  native/delta/main-timer/close controls pass on both clients and live lobby 1;
  production screenshots inspected. Destination/previous hashes and twelve active
  services verified; final health OK/twelve empty rows 2026-10-08 01:46:48 UTC.
  Original game push raced a peer ROADMAP-only plan: inspect/rebase unpublished
  commit, no force; source/progs remained identical. First post-probe health
  assertion did not pass and its response was not retained; later explicit saved
  readbacks passed. Do not invent a cause from that missing first snapshot.

- **Focus cancels activity, not ownership (Patch 554).** `rw_kactive` is separate
  from down/taken identity. Chat/menu/modal cursor and effective console cursor
  cancel browsing holds; IE_FOCUS cancels only keyboard=0, not unchanged -1 or
  mouse-only loss. Return/repeats and releasing an opposing cancelled owner do
  not restart; a released fresh press ACTS. Taken repeats/up remain owned after
  close/rebind. `notmenu` excludes menu/cwindows but NOT the main console;
  existing checked `getcursormode(TRUE)` supplies its effective cursor. No new
  engine hook. Pending-go/countdown and native save/resume/body/evidence gates
  are unchanged. Extended `rewind_navigation_smoke.py` passes at 30/100/300
  and both installed clients, unchanged baseline ACTS/fails chat cancellation,
  47 grader controls pass. Existing HUD 21/12 controls and reader 306/0 pass;
  screenshot inspected. These are synthetic chain events, not real OS/device
  delivery or human feel. Private regression launch initially lacked an output
  directory; create it and rerun, do not call an unlaunched arm a pass. Grader
  mutation initially expected echoed cfg text in a timestamped log; target the
  final event instead. Compiler/VM logs, probes and failures remain private.
  Production source `e1c556e`, rebuilt clean/zero warnings, deployed to both
  Windows installs and empty-gated twelve-lobby fleet; `.prev` retains P550.
  Non-instrumented whole-chain focus/cancel/return/fresh/pin/body/clock controls
  pass with both installed clients and live lobby 1. SSQC/menu, default cfg,
  engine and owner source/index/personal cfg unchanged. Final destination hashes,
  all twelve active services, twelve empty heartbeat rows and health OK verified
  2026-10-07 23:49:14 UTC. Actual-device acceptance remains in lextest.md.

- **Opposing live-rewind holds cancel (Patch 550).** Direction is presence of
  owned right minus presence of owned left, not the newest held key. Refresh on
  press/release and every browsing frame; reset acceleration only on an effective
  direction change. Preserve physical ownership through repeats/rebinds and
  pre-open presses. Native cursor/save/resume and pinned movement are unchanged.
  `rewind_navigation_smoke.py` drives full-chain controls over a real dedicated
  socket at 30/100/300 FPS and with both installed clients. The unchanged source
  ACTS and fails cancellation; 28 grader controls reject missing/duplicate/NaN,
  unacted, stuck-release, body/clock/native-selection and pending-HUD mutations.
  Start its cursor at 2 s: the live line has fewer indices at 30 FPS, so the
  original 1 s acceleration control reached its lower bound, invalidating that
  arm. Native probe agreement is with the existing lower selected sample, NOT
  proof of low-FPS requested/native snapshot alignment. Delivered releases behind
  chat/console/menu pass; opening chat/menu without release still scrolls on the
  P550 baseline; P554 closes that focus-cancellation defect. Synthetic
  chain events are not actual-device/OS-focus or camera-feel acceptance.
  Production from exact `41410d8` built with zero warnings; both Windows installs
  and all 12 empty-gated Pi lobbies carry CSQC SHA-256
  `676ca48a7b5d5bf26f76fe0620d50e80c30c248310758b368283841666615f2a`.
  SSQC remains `76f4a7bf...`; menu/configs/engine are unchanged, `.prev` kept.
  Both local production clients and live lobby 1 pass non-instrumented
  cancel/release/pin/body/clock controls; fleet hashes/default cfg and all active
  services rechecked 2026-10-07 22:09:02 UTC. No instrumented program deployed.

- 2026-10-07 repeated-cut control `tools/stitched_rewind_smoke.py`: private
  dump seam plus real dedicated recorder, fresh second client, no fixture or
  install saves touched. Three warm cuts pass after counted 5–6 second waits:
  cut head replaces future, raw hold counts/rows stay equal, release grows the
  retained prefix. Cold persisted picture equals save001. Cold cuts at
  2.0/1.5/1.0 (all after the load) remain RED on two/three: later server sample,
  then refusal. Do not loosen the oracle or call warm success an idle-tail fix.
  State files show cold snapshots lack `recrid`; SV_RecGenOK refuses warm,
  SV_RecRewindStream makes another serial, SV_RewindRebase drops old snapshots.
  BACKLOG carries the boundary; never fix it by passing client geometry as
  authority or merely trimming to its requested clock. Initial test also
  requested pre-load times and must not be cited as newly recorded history;
  corrected after reading the bounded state-ring contract. Harness first used
  two unregistered bare cvars before spawn: repaired to `set`, full rerun had
  zero command/VM errors and zero compiler warnings. Strict retained grader
  exposes the two cold failures, not an all-green claim. Run with private
  `--output-dir`; test-only programs must NEVER ship.
  P539 repairs this specific cold attachment boundary without adopting a saved
  run ID/nonce: fresh local `recbranch` at open/cold/session attach; both save
  writers emit it; warm cuts compare it plus serial/run ID/generation floors.
  Legacy saves retain the nonempty run-ID gate. Streamed and buffered six-cut
  controls now pass, including native body/ticks at the selected snapshot,
  counted failed waits, hold/release and 17 compiled refusal/reset controls.
  Grader counterfactuals: 19 streamed / 18 buffered pass. P502 main/edges and
  its nine grader controls pass in both recorder modes. Reader 306/0; read-only
  corpus remains 269 recordings / 164 recording faults and 91 views / 6 view
  faults, with byte-identical before/after reports. The first candidate omitted the
  separate SV_RewindWriteState writer and correctly remained red. A diagnostic
  seam initially used nonexistent fields (fteqcc crashed without output); fix
  the probe, not product code. `p502segments --content` is needed in source-only
  worktrees: a missing map proves no gameplay. Broader visual acceptance remains
  open; these probes do not judge rendered labels or camera feel. Independent
  review caught a vacuous `zip` native-body oracle: empty/truncated vectors
  could pass. Enforce complete unique finite native fields and keep eight
  malformed-field counterfactuals. Old parser accepts the acted empty-body
  negative; corrected parser rejects it and all other malformed arms. Initial
  draft corpus counts were incorrect; inspect the complete report, not line
  counts or a recalled summary, before publishing a count.
  P539 production progs from inspected `8f87209` reached both Windows installs
  and all 12 Pi lobbies on 2026-10-07 (completed controls 07:49:48 UTC). Pi
  occupancy gate found a current row for every unit, all zero; no force. Hashes
  agree and ordinary `.prev` pairs remain. Engine/plugins/menu, owner configs
  and the second install's Quakers mod were not changed. Independent source
  reviews and the bounded oracle recheck found no residual code blocker.
  Two fresh private clients cold-downloaded matching CSQC, received real peer
  streams and reached the settings/imported/native UI without command/VM/shader
  errors. Native screenshot inspection shows the terms-unaccepted gate and a
  missing-map-material warning: no board-row fetch, complete map appearance or
  rendered camera/path acceptance is claimed. Isolated native cut controls,
  not these compatibility screenshots, establish the recorder fix.
- **Current requested/native selection audit (2026-10-08, tooling only).** Do
  not group historical ticks 49/103 as two still-broken boundaries: P542 closes
  tick49's raw serialization loss; tick103's forward selection was separate.
  Fresh P554-source six-cut controls pass at caps 30/100/300, streamed/buffered
  at 30 and with the second installed client. All thirty local selections match
  independently enumerated native rings, correlated acknowledgements and exact
  acknowledged raw prefixes; measured requested/native offsets are -15..+30ms,
  not universal clock equivalence. Second-client 0.735/request/native/raw agrees.
  An explicitly configured/read-back 30ms packet-delay arm retains strict red
  requested-clock results on three warm cuts (+60/+60/+45ms), while all six
  native/body/hold/release/counting/prefix and camera/discontinuity gates pass.
  Nearest-clock-only candidates have worse position matches; do not force time
  selection or retime evidence to satisfy the display oracle. Alignment/UX and
  human feel remain open. The original .031s clock check is unchanged.
  `stitched_rewind_smoke.py --client` selects both warm/fresh cold executables.
  Requested-clock failure no longer skips per-cut native/body checks or camera
  diagnostics, remains a nonzero result and is not mislabeled as only cold.
  An acted pre-fix combined clock/body negative hid native corruption behind the
  clock failure; the strengthened grader independently rejects it. Grader
  controls: native-selection19, streamed cuts21, buffered cuts20, visual16;
  selection/visual counterfactuals also pass on the strict-red latency captures.
  Compiler zero warnings; reader306/0; no product/format/clock/engine/Build bump,
  new numbered patch or deployment. Private logs/captures stay private. Initial
  second-client launch used an unsupported flag and did not ACT; the added
  explicit pass-through then ACTED. Final logs append warm+cold cvar readbacks:
  expect one in the warm snapshot and two in the combined log, not one overall.
- P542: `Trail_RawSample` serializes clocks at six decimals. Native tick 49
  at 0.015 produces cutoff 0.734999955, but decoding its 0.735 row produces
  0.735000014. An exact unrounded comparison dropped a whole rendered sample
  (45 ms at 30 FPS), despite the request/native/ack clocks agreeing. The old
  retained native probes establish tick 49 for the 0.735 -> 0.690 failure;
  the other 1.500 -> 1.545 failure held native tick 103 and is separate.
  `Trail_RawClock` puts trim/save/load cutoffs through the SAME six-decimal
  formatter/parser once per operation. No new sample, FPS epsilon, native
  selection, evidence/save-state clock or format change. It also preserves
  negative/untimed cutoff behavior. New `--selection-audit` captures the entire
  native ring, wire request, sampled cursor and correlated go acknowledgement;
  independent distance/tick ordering and full raw-prefix comparisons ACT on
  all six cuts. All strict existing checks plus six compiled clock controls
  pass buffered at 30/100/300 and streamed at 30; 19 audit counterfactuals reject
  wrong/missing/nonfinite selection, request, ack and raw rows. Visual 30-FPS
  scans pass 5,646 buffered / 5,574 streamed samples and all nine compiled
  presentation controls. Baseline 30-FPS still loses a 2.025 boundary to 1.980
  and fails compiled clock normalization; do not weaken either grader.
  Production P502 main/edges pass both modes, native negatives 18/19 and visual
  negatives 16 pass; reader 306/0. Captured 269-file recording corpus: unchanged
  baseline/candidate findings, 164 files with faults. No evidence-reader change.
  An initial edit used an undeclared `endt` in `Trail_Trim`, causing fteqcc to
  exit without diagnostics; fixed the variable, not the compiler or peer code.
  New diagnostics are PRIVATE programs: never deploy probe commands/raw output.
  General requested/native clock UX, real teleport/contact truth and human
  moving-camera feel remain unverified. Engine commit/tag and qcbuild unchanged.
  Frozen published source `72e7884` production pair installed to both Windows
  trees at 2026-10-07 11:28:21 UTC, keeping ordinary `.prev`. CSQC SHA256
  `ac19e6df987d33393b6c1e526f0ab3d7256d9754fa27e49f47c6741efc36e22b`;
  SSQC remains `e56b81df...`. No private diagnostic markers in production.
  Installed dedicated P502 main/edges ACT/pass using FTESurf's client and
  FTEQuake's actual `fteqw64.exe`; finish verified 11:34:44 UTC. The initial
  FTEQuake arm used absent `ftesurf64.exe` (WinError 2 before client action):
  recheck destination hashes and finish only with the actual executable, do
  not recopy the progs. Protected native/plugin/menu/personal/default config
  and Quakers hashes stayed unchanged.
  Pi deployment is PENDING: normal `-Pi` occupancy gate found one player in
  lobby 1 and refused before copies/restarts; no force. Independent read at
  11:32:04 UTC found predecessor `e7e519c3...` CSQC and all 12 units active.
  A later directory read still had 12 current rows and the same occupied port.
  Retry the frozen production build normally when empty, then verify remote
  hashes, every unit and fresh-cache live behavior. Do not claim fleet delivery
  or drop the connected player to finish this deployment.
  Fleet retry completed 2026-10-07 at 12:10:46 UTC, from the SAME clean frozen
  `72e7884` source. Normal occupancy guard found all 12 current rows empty;
  no force. Zero-warning production rebuild matches the Windows pair. All
  12 exact units independently active; remote CSQC is `ac19e6df...`, previous
  CSQC is P540 `e7e519c3...`, SSQC remains `e56b81df...`. Default cfg unchanged;
  ordinary `.prev` retained. Two fresh-cache installed clients downloaded exact
  matching CSQC, received acted peer streams and reached the settings/imported/
  native UI without command/VM/shader errors. Inspected native screenshot still
  shows unaccepted terms and the known missing-map material: compatibility, not
  board-row fetch, map completeness or moving-camera acceptance. No second
  restart during finish controls. Windows production/protected native/plugin/
  menu/personal/default cfg and Quakers hashes stayed unchanged. Directory had
  all 12 rows and zero players afterward. P542 fleet delivery is now complete.
- Native event/stop controls (tooling after P542):
  `python tools/native_trail_events.py --output-dir <private dir> --fps 30`
  (also 100/300) walks out of start on a real dedicated socket, then engine
  touches private AABB volumes using the ordinary `trigger_teleport_touch`.
  Keep/zero velocity and view-snap modes ACT, with exact native before/after
  destination, body, velocity and unchanged tick checks. Land on the map's
  actual floor: an unnetworked synthetic slab does NOT provide matching client
  prediction collision. A six-second running stop advances counted ticks and
  raw time without body/velocity drift; a fixed cursor over 1.5 wall seconds
  preserves clock, body, velocity and raw rows while the native pin freezes.
  Complete quarter-point scans at 30/100/300, nine compiled controls and distinct
  first-person/chase view-state probes pass. The initial screenshots aliased:
  PNG encoding consumed the waitms interval without drawing the changed camera.
  Follow-up uses frame barriers and captures VF_ORIGIN/VF_ANGLES immediately
  before renderscene, not from a console command outside CSQC_UpdateView.
  First/chase/return at 30/100/300 changes 40.2% of a world-only image patch,
  then restores it (0.0% changed). Screenshots were inspected. This is bounded
  renderer/synthetic-volume/native-handler coverage, NOT authored BSP teleport
  or human camera-feel acceptance.
  `python tools/test_native_trail_events.py --rig <private rig> --output-dir
  <private dir>` rejects 43 malformed/missing/unacted/wrong-state/body/clock/
  mode/raw-break/camera cases, including aliased images, wrong return pixels and
  missing/wrong return camera probes; positive first. Existing visual grader's 16
  controls still pass. Its angular oracle now accounts for the SAME independently
  derived six-decimal time bound as velocity: `abs(short_arc)*2e-6/dt`, not a
  tolerance chosen from a failing difference. One native trace exposed a
  90-degree turn over serialized 9.960000..9.974999 seconds: midpoint -135 was
  correct but a fixed .003-degree oracle rejected its .0030002 text-rounding
  difference. Discontinuities retain the strict bound; wrong-view falsifiers
  still reject. No product/evidence format change or new product patch.
  Native instant poses and sampled visual endpoints are different contracts:
  keep-velocity native-to-first-raw-break offsets vary across runs/FPS. Bracket
  each acted touch with raw pre/post dumps, retain exact native tests and report
  the offset; don't silently retime history or claim instant-pose equivalence.
- P540: raw trail break/stitch columns (8/9), not only legacy flag
  `0x4000000`, gate `Trail_VisualState` interpolation. `Rewind_Camera` bounds
  its +/-3-point tangent to the cursor's continuous span. Compiled positives
  for continuous/short-yaw/sampled-save/raw-break/raw-stitch/legacy-break/
  position-break and both sides of a chase break: baseline fails four, subject
  passes all nine. `stitched_rewind_smoke --visual` adds private quarter-point
  first-person/chase traces, restored after scanning; never ship the probe
  programs. Six-cut native body/clock/prefix/refusal controls pass streamed and
  buffered at 100 FPS and streamed at 300 FPS (12,006 / 12,110 / 12,142 traced
  cursor samples respectively). Genuine 5-second running stops stay counted.
  Visual-only 30-FPS buffered traces pass (5,626 samples), but the full oracle
  stays red: 0.735 requested -> 0.690 retained, 1.500 -> 1.545. Both failures
  reproduce exactly with `--baseline` (HEAD client code, before this commit).
  Do not call the low-FPS full matrix green or silently broaden its tolerances.
  All 17 lineage guards, 19/18 native grader counterfactuals, 16 visual grader
  controls and P502 main/edges pass; reader 306/0. No evidence writer/reader,
  server selection, save clock, engine pin/tag or qcbuild change.
  Probe compile failures were a vector component on a call result and a missing
  forward declaration, not product defects. Initial hold probe preceded load
  acknowledgement: allow 1.2 s before hold1, still inside the 3 s hold. At
  30 FPS use .9/.7/.5 warm cuts to retain the existing >10-sample coverage floor;
  changing that floor would conceal the first low-FPS fixture failure. Printed
  six-decimal time needs a velocity tolerance derived from dt/velocity slope,
  not arbitrary smoothing. Empty/truncated/nonfinite/missing-quarter and pose/
  view/camera/index mutations all reject; raw angles are independently derived.
  Numeric geometry is not screenshots, camera feel or full contact/teleport
  truth. Those human/broader cases and low-FPS alignment remain open.
  P540 frozen production `996462b` deployed to both Windows installs and all
  12 Pi lobbies; compatibility gates finished 2026-10-07 08:44:27 UTC. CSQC
  SHA256 `e7e519c38707aca332ff8eff8ad7ff44282187a7404c320f43b13a56aecac32f`;
  SSQC stays `e56b81df...`, predecessor CSQC `8b3811fb...` retained as `.prev`.
  Clean frozen builds match the production P502 subject byte-for-byte and
  contain no probe commands. Pi occupancy gate: all 12 current rows empty,
  no force; independent hash/status read: all active. Windows native/plugin/
  menu/personal/default cfg and Quakers hashes unchanged. Two fresh-cache
  installed clients downloaded matching bytes and received acted peer streams;
  no command/VM/shader errors. Inspected settings/native screenshots still
  show the unaccepted-terms gate and known missing-map material: compatibility,
  not row-fetch, map appearance or camera-feel acceptance. No extra restart
  during finish-only controls. Peer source/index edits remain untouched.
- P533/P535/P536/P537 final frozen product `2b7cced` deployment verified
  2026-10-07 at 06:07:21 UTC. Both Windows installs and Pi have CSQC SHA256
  `541accec08be6396d4e711947c8092a641183c97c0242a7661913fd74851e66a`;
  immediate `.prev` is P536 `9120d5ac...`. Clean product has no test hooks.
  Windows SSQC/menu/native and owner configs/data unchanged; Pi coherent pair
  preserves SSQC `951acd41...`. Default.cfg `8fd357ac...` changes only the reveal
  comment relative to P532, with original config backups retained. No engine
  pin/tag, qcbuild or server-rule changes. All 12 were empty for deployment;
  verification finished separately without another swap/restart. Fresh-cache
  clients on both installed engines downloaded those bytes, received peer body
  streams, and drew the eleven-row settings plus separate imported/native tabs
  without Compare. Terms deliberately unaccepted: UI/scope and stream controls,
  not remote row-fetch/permission or all-backend acceptance. Actual map was
  surf_kitsune with its known unresolved material; not repaired by this batch.
  The final 21-unit/12-dedicated-phase P537 layout regression and inspected
  screenshot remain the cursor/input proof, not these idle live clients.
- Patch 537: final production screenshot caught the old REWIND heading
  overlapping P535's timer caption. Hide that heading while the main cursor
  snapshot is active; footer carries explicit mode. Controls at 0.80 and implicit
  resume context at 0.76 avoid default speed/chat rows. Pending-go/countdown
  heading/guards stay unchanged. Full 21/12 controls rerun, new screenshot
  inspected; this is default-layout evidence, not every custom HUD layout.
- Patch 535: ui_rw_* is a presentation-only snapshot, published after camera
  setup and consumed by the existing main timer/speed/energy panels. Fractional
  rw_visualt/p and tr_vis_* never serialize a save: tr_cur_t/p, raw selected
  velocity/angles and prefix bound remain at the same floor sample as before.
  Duplicate clocks keep the last sample; position/velocity do not blend through
  breaks. The timer says display-only; `e line` is relative to the first line
  sample's total energy (not the current live/manual/jump anchor). Missing raw
  velocity displays unavailable, not a fabricated zero. Live physics/board
  derivatives and unsupported ramp/trainer panels stay out of the cursor path.
  Entry/exit force the readout latch; pending-go/countdown use normal live HUD.
- Bound bare +moveleft/+moveright commands now scrub live rewind, not assumed
  A/D. Up to 16 simultaneously held physical bind identities track separately;
  released slots recycle. Held-before-open keys are not adopted; repeats do not
  step again; release/rebind/focus identity and overlapping-direction fallback
  retain ownership. Movement during pending-go/countdown follows the preexisting
  release-gate policy, not queued navigation. Compound binds and demo parity are
  not claimed. This is not the full P477 27-round matrix or a stitched-idle fix.
- `tools/rewind_hud_smoke.py` uses private test-only seams and a real dedicated
  socket: 21 sample-vs-visual/unknown/ownership assertions and 12 acted HUD/input
  phases, including native viewpos proving a stationary pinned body. Actual main
  HUD/camera and post-resume screenshots inspected. Initial seam needed a later
  Rewind_Reset prototype; the first grader expected `origin:` rather than the
  actual viewpos `setpos` output. Both repaired and controls rerun. First product
  compile caught a nonexistent tr_track and wrong Interp_Arc arity, corrected
  using the existing stat and Interp_View before any product publication.
- P533 tail-batch correction: TR_BUILD is 16, so a live tail can have 15 pending
  points, not three. The implementation already handles it; extended pixel/emit
  controls now prove the full 15-point tail. 37 alpha assertions, 52 screenshots.
  Long-sweep opaque body had five one-channel 1/255 differences; the endpoint
  now uses the same <=1 RGB tolerance as survivor checks, retaining exact coverage
  masks. Original images regraded explicitly, not silently relabeled/relaunched.
  306 recorder-reader checks pass; unchanged checker/corpus hashes retain the
  existing 269 REC observation (164 REC faults plus six of 91 paired VIEW faults).

- P544 demo navigation: `Watch_Track` runs before every input handler/release
  gate. Up/repeat identity is physical, not a re-read bind; pre-open/chat-owned
  repeats cannot acquire the viewer. Bounded 16-key table; bare +moveleft/right
  only (primary mouse buttons remain chrome's). Tap seeks one recording tick;
  held rate is 0.45..9 run seconds/wall second over 2 seconds, opposing directions
  cancel, same-direction keys remain independent. `Watch_Seek` retains all cache
  invalidation/window clamps. Close/open/Space cancel active scrub, but taken
  repeats/up remain swallowed through close/rebind. Menu/chat cursor focus and
  IE_FOCUS loss cancel active scrub; console releases are observed ahead of its
  draft/other handlers. Compound/modifier binds and actual OS/device focus are
  not covered by the synthetic input arm; P550 later adds live opposing-key
  cancellation and P554 adds live focus cancellation.
  `tools/watch_navigation_smoke.py --output-dir <private dir>
  [--baseline <pre-patch ref>]`
  creates an isolated test-only overlay and real dedicated socket. 35 cursor
  probes/55 CSQC_InputEvent events pass at 30/100/300, replay position/velocity
  match the synthetic straight-line cursor and native pinned body stays exact.
  Unchanged baseline ACTS but fails held-scroll oracle. The grader's 31 controls
  reject unacted/missing/wrong ownership/time/pose/body/focus probes. Initial
  harness used absent menu_main; togglemenu repaired both arms. Coordinate
  oracle allows .03u for float32 interpolation at <=14500u world coordinates,
  independent of ownership/time stop equality. 306 recorder-reader tests pass;
  unchanged checker over 269 real REC files retains 170 existing paired faults.
  This is navigation assurance, not evidence retiming, imported-camera or human
  smoothness acceptance. Engine pin/tag/qcbuild stay unchanged.

- P549 fractional demo clock: `Watch_ClockTicks` is presentation-only. The
  main timer and full-demo chrome use visual seconds / recorded tickrate,
  bounded to zero/recorded finish; sampled `rec_wt_ticks` still own events,
  splits and state. Live rewind and stage-cut chrome remain unchanged.
  `tools/watch_clock_smoke.py --output-dir <private dir> [--baseline <ref>]`
  probes actual formatted draw text and panel arguments through a private
  dedicated overlay: 33 acted native/foreign/legacy positions, paused holds,
  forward/backward/sub-tick seeks, stationary spans and lead-in/finish bounds.
  Native server body stays exact. Unchanged baseline ACTS but fails the
  fractional-input oracle. Retained screenshots show matching panel/chrome.
  `--rig <retained rig>` runs the strict grader and 20 counterfactual rejections.
  Foreign/legacy fixtures are reader controls, not import-codec/unknown-velocity
  acceptance; broader HUD/camera continuity, long demos and human feel remain
  separate. All three progs compile at zero warnings; 306 reader checks pass.
  Unchanged checker/corpus retains 269 REC / 91 VIEW and 170 existing faults.
  Clean published product `11e32ba` deployed 2026-10-07 UTC: fleet restarts
  completed 20:18:51, both Windows installs hash-match with .prev retained and
  personal cfg preserved (including absence). Independent 20:25:57 host read:
  both progs match, all twelve lobbies active, directory back to zero players.
  Production client on lobby 1 ACTS on synthetic replay: inspected panel/chrome
  agree at 1.001s, stationary 3.205s and exact 6.000s finish. No diagnostic progs,
  server/config/engine changes or PiForce. This is clock rendering, not world
  camera/import acceptance. `runlines_smoke.py --recording` always copies to
  cfg/test/runlines_sample.rec; a generic no-error completion with 'nothing
  loaded' is NOT an acted control. Preserve failed logs and repair the cfg only.

- **The rewind rides the replay's pin, marked as its own: `rec_watch 1 rw`.** A
  pinned RUNNING run is frozen and practice, and EVERY way out of a rewind ends
  that run rather than thawing it -- a thaw past an unrecorded freeze convicts its
  angles (the held-run fault, under Anti-cheat). ENTER and ESC resume through
  `sl_saveat <ticks> x y z go` (an IDLE row). A refused resume, `rec_watch 0`
  (plain or `void`), a warp the server serves (SV_RewindWarped: AFTER the warp,
  and only if it moved the body), `retry`, a Multi-Session park and a lobby flip
  void it (SV_WatchLetGo). A replay's pin (no `rw`) keeps its run through warps
  and thaws on release, as before 477; it shares the rest -- speed and carrier
  held at zero (a `warp ... pin` on a running run), the taint only on a running
  clock.
- **The state is the server's, never the client's.** SV_RewindSample keeps 4000
  samples a slot, one every 2 run ticks, only while running and unheld; the
  client's x y z only picks among samples within 0.5 s of its tick. A run start
  wipes the ring; a warp under the rewind marks it over, so the next start does.
- **STAT_FS_PIN (111) is the rewind's open serial while its pin is held,
  `-serial` once that open's pin is refused or let go (until the next pin), 0
  before any** (`rec_watch 1 rw <serial> <state at the open>`). The client closes
  the mode on a release it did not ask for, and latches only its own serial, so
  an earlier open's pin or release in flight is never mistaken for it. The pin
  also carries the state and the run ticks the client saw at the open, and the
  server refuses to pin a run that is not that one (not RUNNING then, or fewer
  ticks now); the ask is tied to the trail line, so a new run is asked afresh.
- **A replay opened while browsing takes the pin over in the same frame**
  (Watch_Open calls Rewind_HandOver before its own `rec_watch 1`).
- **A frozen run's kept-abandon `inend` is the mover tick at the freeze**
  (`run_t_frzmt`), because the `in` rows stop there; pm_verify flies a last row
  to `inend`.
- **THE PIN OWNS THE MOVETYPE (Patch 499).** `SV_WatchHoldMove` re-imposes
  MOVETYPE_NONE from BOTH thinks -- PlayerPreThink per usercmd and ahead of the
  mover, PlayerPostThink ahead of `SV_NoclipWatch` -- because `SV_WatchHold`
  wrote it once at the press and nothing held it, so one `cmd noclip` left a
  pinned, recording run reading `class: cheated`. The pin does NOT re-place the
  body (a teleport under it is the rewind's own business); that is what the
  save-lock hold does instead, and why only the hold was immune. A resume row's
  "the next resume replaces it" pointer (`rw_goid`) now dies with its run:
  `SV_RewindReset` clears it, so a `retry` no longer lets the next ENTER's `go`
  DELETE a save from the run before it. The row stays, as an ordinary save.
- Harness: `tools/p477rewind.py` (parks data/saves/surf_dune; its last section
  changes map to surf_embrace). `vote key <scan> <0|1>` runs a key through the
  whole input chain (CSQC_InputEvent: Rewind_Track, the chat draft, the rest);
  `rewind key <scan> [up] [other]` feeds Rewind_Track and this mode's handler
  only (`other`: a press another handler took); `rewind
  status|seek|step|go|save` drive the rest.

## Imported runs: Momentum Mod and KSF

- Patch 536 removes the misleading imported-board Compare chip and its
  rec_sb_mixboth state. Scores_TierOf returns imported for the imported tab,
  ranked for native; no silent interleaving. Combined read API/database rules
  remain intact and this is not a live/frame comparator. Private
  tools/compare_chip_smoke.py proves both board frames actually drew, getter
  tiers differ, Compare has zero calls and imported/refresh widgets retain
  positive calls. Screenshots inspected; terms are unaccepted, so the arm proves
  UI/scope, NOT remote row fetch or new permission. The first test initialized
  its sentinel as an implicit QC constant; explicit var repaired it and rerun
  passed with zero warnings. Test-only draw counters are never shipped.
- **THE TIER IS THE MECHANISM, and it is not decoration.** A foreign run lands
  in its own `tier` (`momentum`, `ksf`), never in `ranked`. `tier` is in the
  runs primary key, so one player holds a time in each without either
  overwriting the other; and every board query filters on `tier`, so imported
  rows are invisible to the ranked board BY CONSTRUCTION rather than by each
  future query remembering to exclude them. Patch 425 already used unreadable
  tier strings as the hiding mechanism -- this is the same trick named.
  `surfd/test_momindex.py` is the arm: 130 ranked boards' rows and counts
  identical across importing 2,782 runs, against a COPY OF THE LIVE DATABASE.
- **READABLE, NOT CLAIMABLE.** `/api/board` validates against `TIERS_READ`;
  `submit_run` still validates against `TIERS`. A keyed lobby -- trusted enough
  to write `ranked` -- gets HTTP 400 for `momentum`, `ksf`, `imported` or
  `combined`. Only a local importer beside the files writes those. Keep it that
  way: the wire must never be able to name a foreign tier.
- **`imported` and `combined` are PSEUDO-TIERS: they name a query, not a class
  of run.** Nothing is stored under either. `TIERS_IMPORTED` is the one tuple
  the predicates read and `TIER_EXPAND` maps the pseudo names to it, so a third
  source is one tuple entry, not four edits. Rows on those boards carry `tr`,
  their real tier; single-tier boards do NOT send it, and the client falls back
  to the board's own tier (`Online_WhyString`, two levels, in that order).
- **The pipeline.** `.mtv` (Momentum's container) is never parsed here: its body
  is a Source entity-delta netstream with no public spec, and the wrlines
  reference does not decode it either -- it fits a chain of float32 triples with
  a dynamic program. Read its OUTPUT instead:
  `wrlines/tests/reference/wrpath_extract.py --all --jobs N --skip-existing`
  writes `.wrpath`, then `tools/momimport.py` turns those into `.rec` under
  `data/momentum/<map>/<legdir>/`, then `surfd/momindex.py` indexes them.
  **Extraction stays on Windows**: that extractor's float arithmetic is
  bit-pinned to CPython 3.13.9 (`math.dist`, a Neumaier `sum()`), and a
  last-digit disagreement does not nudge a coordinate, it SELECTS A DIFFERENT
  CHAIN through the demo. The Pi runs 3.11. `momimport` does no such arithmetic.
  Extraction is memory-hungry: 8 workers peaked ~2.2 GB and got a background job
  reaped on a 16 GB box. 3 jobs is the polite figure.
- **WHAT A .wrpath DOES NOT CONTAIN** (the "proven negatives" here came from
  grepping wrlines, which never decodes the netstream): view angles, buttons,
  ground contact. The .mtv has all three -- tools/momreplay.py decodes them, and
  since 4 Oct tools/momreimport.py writes every import from its demo (5260 of
  5281): eye angles, fl ground/duck/jump/attack, the move from the recorded
  wishVel. Still never recorded: ramp contact (bit 16, the plane -- BACKLOG).
  **Never write a `.view` sidecar for an import**: that file is the client's
  per-frame evidence, and nothing here was recorded per frame.
- **NO `warp` RECORDS ARE SYNTHESISED**, and the grammar forbids it in terms:
  "A record synthesised by watching for a discontinuity would see the jump and
  still not know what caused it, which is the entire question." 37 % of these
  paths teleport; the reader's own kinematic test finds them and reports them as
  `kin` rather than `rec`, which is the truth about where the knowledge came
  from. `momline.cfg` A3 grades exactly that: `snaps 0 rec 22 kin`.
- **The integrity keys are OMITTED, not filled.** `mapcrc`, `zonecrc`,
  `zonerule`, `nonce`, `pmpin`, `seed` state what the machine that ran the
  physics loaded, and that machine was Source. `cl_lobbytime.qc:652-681` already
  makes this argument for a client-written `.rec`. reccheck then reports the
  file as `zones not stated` / `nonce not stated` / `ruleset unknown` in its own
  words, and `pm_verify` cannot pass one of these and should not.
- **THE DEMO NAMES THE BUILD IT WAS RECORDED ON, and it is checkable exactly.**
  A `.mtv`'s 40-hex `mapHash` is a plain SHA1 of the `.bsp` -- verified on five
  maps, and the `.wrpath` carries 39 of it at 0x74. So `momimport --maps <dir>`
  hashes the map once and compares. **877 of 7,040 extracted paths (12.5 %)
  name a build this install does not have**, concentrated in maps re-released
  under one name (`surf_simple_v1` alone has 183). Those are SKIPPED by default:
  the time is real, but a line built from their samples is placed against
  geometry the player never touched, which is wrong and looks right.
  `--other-build` imports them anyway and the header records the verdict as
  `mapbuild <sha> ok|other|nomap`.
  This is the exact form of the wider hazard: 322 of 1,062 map names shared
  between the Momentum and CS:S installs are DIFFERENT BUILDS under one name,
  and all 322 are plain-named -- the `_ksf` suffix marks the cases somebody
  disambiguated, not the cases that collide. A size comparison is a proxy; the
  SHA1 is the answer.
- **Velocity is a central difference of positions and it SPIKES AT COVERAGE
  GAPS.** 7.6 % of files exceed the demo's own `maxHorizontalSpeed` by >5 %, 44
  by over 2x; 81 % of those carry no `LOW_CONFIDENCE` flag, because that flag
  measures coverage, not velocity. The ceiling ships inside every demo, so the
  check is free: the ratio goes in the header as `momquality`. `Line_Range`'s
  mean ± 2 sd clamp keeps an outlier out of the colour ramp, so the visible cost
  is confined to the live speedometer at that instant.
- **KSF is times only.** No demo URL, no Source `.dem` parser, nothing that
  could become a `.rec`; `replay_id` is 0 and the board shows no `watch`.
  `surfd/ksfimport.py --from-maps` pages every board of a map -- main, stages,
  bonuses -- off KSF's JSON API (its docstring has the routes and the two traps:
  a linear map's `cp_count` counts checkpoints, and the search is a typeahead).
  `--seed`/`--from-boards` is the older player-seeded path, main track only.
  Politeness is the wrlines reference's: one at a time, 400 ms apart, capped,
  honest User-Agent, never automatic, a non-2xx reported as a refusal and
  nothing retried. Answers are cached, so a re-run costs nothing.
  `surfd/test_ksfimport.py` is the arm (no network; six mutants caught).
- **A KSF time is a THIRD measurement.** CS:S physics, KSF's own zones, and
  their `mapName` is the PLAIN name (`surf_whiteout`, not `surf_whiteout_ksf`),
  so a matching name does not mean the same build, start or end.
- **THE TWO IMPORTED TIERS DO NOT CARRY THE SAME CLAIM, and that asymmetry must
  not be averaged away.** A Momentum row is build-verified exactly (the demo
  publishes the map's SHA1). Nothing on the CS:S side publishes a per-map
  digest, and the 322 divergent names are all plain-named -- which is where KSF
  records live. So `momentum` means "same build, checked" and `ksf` means
  "build unknown and unknowable". Anything that presents them as one class of
  row is overstating the second.
- **`board_fetch` asks for the map the client is ON.** `Online_Fetch` reads the
  level name; it is not a parameter. An arm that fetches a board for a different
  map without changing map first grades the wrong board and looks correct.

### In-game demo requests and graphs (Patch 545)

Momentum board rows now carry `get = rowid/demo-SHA1` from the indexed upstream
hash, not a caller-provided address. `momboards.py --all --go` backfills this
metadata after schema 11 installation; equal-time updates attach only the same
PB, never a slower cached row's hash. `POST /api/momentum/N/SHA1` validates the
current Momentum/clean row and queues it; GET only polls. At most 64 active
jobs, 10 POSTs/min/IP, TTL one day, terminal history pruned. No CDN request on
the HTTP path. The existing locked momgrab cron prioritizes these jobs inside
its six-demo budget and existing hash, size, duration, disk, map, time and retry
checks. Explicit candidates also bind the demo's player. The converter/filing
path and `/api/replay/N` remain the existing foreign-replay contract.

Client requests selected line handles before round-robin polling; closing a
board cancels watch intent, not a durable job. New picks replace old watch
intent; a cached replay must not wait behind a queued unavailable old choice.
A lost POST is retried idempotently rather than silently converted to a GET.
The nginx snippet must be installed separately from the Python deploy: the new
public GET/POST prefix is allowlisted, body-limited and rate-limited, with no
heartbeat/run-write exposure.

`cl_linegraph.qc` follows the same retained samples as displayed replay/board
lines (slots 0..8, not live trail slots 9..10). A bounded min/max envelope builds
2048 points/frame; mouse readings binary-search actual retained samples. It
aligns run/stage starts, includes vz in E, and uses recorded pmpin gravity or an
explicitly labelled g=800 assumption. E is relative to the first shown run
sample. No endpoint clamping or interpolation over teleport/stitch/large gaps.
`linegraph` takes cursor claim 64; the board's graphs button hands off after
sui_end. Legend ticks hide graph curves, not the world-line loads. Escape releases
only that cursor claim; watched-replay chrome retains its own claim. `hud_linegraph`
and `hud_linegraph_labels` control passive graphs and world-path names.

Falsifiers: `tools/p545graph.py --prepare`, its cfg and `--check <fresh log>`;
`tools/p545mom.py` has a localhost-only HTTP stub and its own game arm. The latter
must use a cold disposable synthetic replay id to prove body delivery; a cached
run is not that control. `surfd/test_momrequest.py` exercises the real filing,
linking and serving path with an explicitly doubled converter. Neither double
claims independent codec coverage. Synthetic UI inputs and screenshots do not
prove actual-device feel or eight long-demo performance; those remain in lextest.

Measured deployment controls: Linux `/tmp` had 5.1 GB free and NVMe had 80 GB.
The downloader's unchanged 20 GB floor stopped both queue-worker test arms in
`/tmp`; all eleven suites passed with TMPDIR and fixtures on NVMe. The deployer
now stages on the target data volume, and `-Only` restricts installation, not the
complete app/dependency archive used by tests. Do not lower the production floor
to make fixtures pass. Private game cfgs use `waitms` for startup, not a long
frame wait before any map exists. `menu_restart` reloads consent: synthetic HTTP
controls set their test-only cvar *after* it, never in a player's install.
The inspected public build.ps1's QC loop only writes this checkout's generated
progs; a successful worktree build did not update C:\FTESurf, and C:\FTEQuake's
csprogs hash remained different too. Explicitly copy the clean build's three
progs to both installs, retaining .prev/first rollback bytes, and compare hashes.
The Pi swap/restart gate did match both progs and all 12 zero-player lobbies.
Backend queue/real conversion/serving works; installing the prepared nginx prefix
needs Lex's sudo. Do not call the public HTTPS path verified before that step.

### The map roster (which BUILD, not just which name)

- **A MAP NAME DOES NOT IDENTIFY A MAP HERE.** Of the 1062 names present in both
  the Momentum and CS:S installs, **322 (30.3%) are a different file** -- and a
  run recorded against the wrong one is demoted `TF_NOMAP` silently. `surf_kitsune`
  is the worked example (`mapsync.py:47-63`). Anything reasoning about maps by
  name alone is wrong about a third of the library.
- `tools/maproster.py` is the answer to "which build": `hash` fills
  `data/maphash.txt`, `build` writes `data/maproster.txt`, `check <map>` explains
  one, `fetch` refreshes the KSF sources. 1748 surf/bhop maps, 1280 of them on a
  local mount (`have` != `-`); that is NOT the same number as what the Pi serves.
- **IT HASHES ONLY THE BUILD THE ENGINE WOULD LOAD**, resolved by reading
  `fs_addons.txt`'s mount order rather than assuming it -- 43.7 GB instead of the
  90 GB both installs hold. First run is at disk speed; after that the cache is
  keyed on (size, mtime) and a re-run is free, because **a stale cache is silent**.
- **`ftesurf/maps/` WINS THE MOUNT, ahead of Momentum and cstrike, and two of its
  four loose BSPs shadow a different upstream build.** `surf_dune` and
  `surf_fantasy` there are byte-identical to the CS:S cuts and override Momentum's,
  so every run on either is against geometry no leaderboard knows -- 45 and 5
  attestations respectively say so. This is the one gotcha a census of the two
  Steam installs cannot see, and it is why `mount_dirs()` puts the gamedir first.
- **THE PIN HAS THREE VERDICTS AND `unknown` IS PERMANENT.** `ok` matches the
  most-attested build, `alt` matches an attested build that is not that one,
  `other` means builds are attested and ours is none of them, `unknown` means
  NOTHING attests. `unknown` is 1279 of 1748 and it is not a backlog: no CS:S- or
  KSF-sourced map has a published digest anywhere. Collapsing it into `other`
  accuses most of the library on the strength of nobody having said anything.
- **WHERE ATTESTATIONS COME FROM, and the two sources disagree in LENGTH.** A
  `.mtv` demo carries the map's SHA1 as 40 UPPERCASE hex at FIXED offset 80
  (verified on 2888 demos, no exceptions). An imported `.rec`'s `mapbuild` line
  carries **39**, because a `.wrpath` stores the hash in a 40-BYTE field including
  its terminator and the last digit is lost; `momimport.py` copies that through.
  So matching is prefix-aware and a 39 is folded into the 40 it prefixes --
  without the fold every map carrying both sources reads as contested. The `.rec`
  corpus is the WIDE source (472 maps) and the demos the exact one (40).
- **`builds` IS A FLOOR AND `ev` SAYS WHY.** A count of attested builds is what
  these sources SAW, not what exists -- a wider corpus finds `surf_4am` on three
  where these find two. `ev` carries the number of attestations so a later corpus
  raising the count reads as new evidence rather than as the tool having lied.
  This is not theoretical: `surf_slobs` was reported here as a build nobody plays
  on the strength of ONE demo, and against 19 it is the most-played one.
- **THE KSF DRIVE IS PUBLIC -- no API key, no OAuth, no credential, and there
  should never be one.** `tools/ksffetch.py` mirrors what is missing. 929 maps on
  the roster sheet, 929 archives, 894 already on disk. **Enumerate with
  `embeddedfolderview?id=<id>`, NEVER `/drive/folders/<id>`**: the latter embeds
  only the first 50 entries and paginates the rest by XHR, so a scraper on it sees
  50 of 466 and looks like it worked.
- The BSP lands in the **Momentum install's `maps/`** because `mapsync.py` mirrors
  FROM there to the Pi; anywhere else is a map you can play and cannot host.
  Archives are RAR5 (7-Zip, not stdlib), hold one bare `.bsp`, and reach 335 MB
  unpacked -- stream them to disk, do not `.read()` them. Google's large-file
  interstitial returns HTML, so the magic bytes are checked before the file is
  believed.
- The roster and the KSF sheet **disagree on five names** and four of those five
  are on disk under the DRIVE's spelling (`surf_junglepics_ksf` vs
  `surf_junglespic_ksf`, `surf_not_so_zen` vs `surf_nsz_fix`, ...). Trusting
  either alone reports maps missing that are already here: that is
  `unreconciled`, and it never folds into `missing`.

### Map downloads (the button, and where the bytes actually go)

- **HTTP IS THE TRANSPORT AND THE GAME NETCHAN IS THE FALLBACK, and the engine
  already does that swap on its own.** With `sv_dlURL` set the client rewrites a
  missing map to `<url>/<gamedir>/maps/<map>.bsp` (`cl_parse.c:1002`); if that
  fetch fails it re-enqueues the same file over the netchan by itself
  (`cl_parse.c:719-724`). A broken mirror therefore costs speed, never the
  download -- do not write fallback logic, it is there.
- **THE MENU'S OWN DOWNLOADS USE A DIFFERENT URL SHAPE.** `cl_download_mapsrc`
  takes the BARE name -- `<url>/<map>.bsp`, the "maps/" prefix is stripped
  (`cl_parse.c:1020`) -- and is only consulted when `sv_dlURL` is empty, which is
  exactly the disconnected case. Both layouts must resolve or the button works
  in a lobby and not in the menu; `surfd/maps.nginx` answers both with one regex.
- **`localcmd("download …")` CANNOT DO THIS AND MUST NOT BE MADE TO.**
  `PF_localcmd` buffers at `RESTRICT_INSECURE` for every VM, so menuqc is
  indistinguishable from a server's stuffcmd and the console command takes its
  server-initiated branch: `cl_download_redirection` defaults to `2`, which
  allows only `demos/*.mvd` and `package/*.pak` and refuses a bare map. Relaxing
  that cvar is the tempting fix and the wrong one -- its own description says it
  lets a server send nearly arbitrary download commands, so it buys one button by
  weakening the client against every server it joins. Patch 465's `downloadmap`
  builtin exists for this, takes a bare name, and whitelists `[A-Za-z0-9_-]`.
- **THE PROGRESS BAR AND THE KB/s NEEDED NO ENGINE WORK.**
  `serverkey("dlstate")` returns `files-remaining total-size unknown-flag
  localname remotename percent rate received total`, and
  `PF_cl_serverkey_internal` reads `cls.download` directly rather than through a
  VM, so menuqc can ask (`pr_clcmd.c:1433-1447`).
- **THE RATE CAP IS IN NGINX, NOT IN THE GAME, and `limit_rate` CAPS ONE
  CONNECTION.** That multiplier is the trap already written into
  `nettest-dl.conf` from the day a tester pulled 6.20 GB through the Pi with
  nothing capping it. `sv_maxdrate` caps only the netchan fallback; it defaults
  to `500000`, so "is it uncapped?" has always been no -- it was half the figure
  anyone would have asked for, on the slow path only. Both are 1 MB/s now.
- **THE LIST COULD NOT SHOW A MAP YOU DO NOT HAVE**, and that, not the transport,
  is why this feature did not exist. `ui_load_maps` builds every row from
  `search_begin`, so "listed" and "installed" were one fact. `ui_dl_load` reads
  `data/mapdl.txt` and appends the rest with `ms_have "0"`. It MUST run before
  `ui_meta_load`, which builds its byname hash from `ms_name` -- the other order
  leaves every downloadable map untiered, and an untiered map and a tier-1 map
  look identical in the list.
- **`data/mapdl.txt` IS THE INTERSECTION OF THE CATALOGUE AND THE PI, not the
  catalogue.** 1748 maps are catalogued and the Pi serves 1743; offering the
  other 5 draws a button that 404s. `tools/mapscan.py` takes that intersection
  and reports the remainder as a sync backlog rather than hiding it.
- **`NEW` MEANS "A SWEEP SAW THIS NAME APPEAR", not "recently released" and not
  "we only just noticed".** The first run has nothing to compare against, so
  every name is written `bootstrap` and none of them badge; only a name that
  turns up in a LATER sweep is `scan`. Without that split the first run badges
  the entire library on the day it ships.
- **THE FINISH TEST ASKS THE FILESYSTEM.** `dlstate` goes empty both when a
  download completed and when it failed, and a 404 on the mirror is not even a
  failure -- the engine re-queues over the netchan and `dlstate` stays busy. Only
  "is the bsp on disk now" settles it. `Dl_Tick` is polled OUTSIDE `m_draw`'s
  `menu_active` gate for the same family of reason as `ui_join_tick`: the
  download survives an ESC and nothing else notices it finished.
- **AN HTTP DOWNLOAD LANDS IN A `.tmp` AND IS RENAMED ONLY WHEN WHOLE** (Patch
  465). It did not before: `httpclient.c:639-642` opens its localname directly
  with `"w+b"` and never renames, and `DL_Abort`'s rename arm is gated on
  `DLLF_BEGUN`, which a web download never sets. So an interrupted transfer left
  a SHORT .bsp under the real name -- which reads as installed, stops the button
  offering it, and mismatches mapcrc, i.e. a silent `TF_NOMAP` on every run
  played on it. The rename lives in `CL_WebDownloadFinished` and not in
  `DL_Abort` because that arm also does `FS_Remove(dl->dclname)`, and
  `dclname`/`prefixbytes` are set only on the netchan path.
- **NAMES IN `data/mapdl.txt` ARE THE PI'S SPELLING, NOT THE CATALOGUE'S.** The
  catalogues lowercase and the Pi does not; six maps differ by case alone. The
  name in that file IS the download path, and nginx's `alias` uses the captured
  name verbatim on a case-sensitive filesystem, so the catalogue's spelling
  would 404 forever. `mapscan.py` folds case to MATCH and emits what the Pi has.
- **HAVING THE FILE AND HAVING THE RIGHT BUILD ARE DIFFERENT FACTS** (Patch
  466). Patch 465 asked `COM_FCheckExists`, a question about a NAME, so the one
  case the Download button could not help with was a WRONG build -- which is
  exactly what a server kicks you for (mapcrc mismatch, `cl_parse.c:7669`).
  `ui_dl_load` now compares `mapfilekb(name)` against `data/mapdl.txt`'s kb and
  marks the row `ms_have "2"`, which draws "Wrong build" and re-gets with
  `downloadmap(name, 1)`.
- **THE RE-GET CANNOT TOUCH A STEAM INSTALL, and that was traced rather than
  assumed.** `DLLF_OVERWRITE` means "ignore any local files" (client.h:609), not
  "clobber", and this path leaves `fsroot` at `HTTP_CL_Get`'s default
  `FS_GAMEONLY` -- only `DLLF_NONGAME` forces `FS_ROOT` (`cl_parse.c:810`). So
  the file lands in `ftesurf/maps/` and SHADOWS the lower mount. Worth the trace:
  if it had been `FS_ROOT`, the `FS_Remove` beside the rename would have deleted
  content out of the user's Momentum install.
- **`mapfilekb` AND NOT `search_getfilesize`.** The first resolves through the
  MOUNT ORDER (`FS_FLocateFile`); the second answers for whichever duplicate the
  search listed first, and NAMESORT is an explicitly unstable qsort
  (`pr_bgcmd.c:3592-3598`), so with the same map in two mounts it can describe
  the copy the engine will NOT load -- precisely the configuration the check is
  for. Measured: with a truncated shadow planted, `mapfilekb` reads 483 KB, the
  shadow, not the 965 KB copy beneath it.
- **KILOBYTES, NOT BYTES, ACROSS THE QC BOUNDARY.** A QC float is 32-bit and
  exact only to 2^24; maps here pass 200 MB and surf_666 alone is 21,644,745
  bytes. KB also matches `data/mapdl.txt`'s own column so the two compare as
  authored. (And the integer divide has to come first: `(double)(n+1023)/1024`
  is a ratio, not a ceiling.)
- **A SIZE DIFFERENCE IS PROOF OF A DIFFERENT BUILD; EQUAL SIZES ARE PROOF OF
  NOTHING.** The check under-reports by construction and never accuses a correct
  install, which is the right way round when the action is to spend a player's
  bandwidth. Two builds of identical size are missed, and that is the documented
  limit rather than a bug to fix with a tighter threshold.
- **THE WRONG-BUILD BASELINE ON THIS BOX IS 2, NOT 0.** `surf_dune` and
  `surf_fantasy` -- the maps lextest 2i asks about -- and `tools/p466reget.py`
  computes the baseline rather than assuming zero, because a control that
  expected 0 would have failed for the right reason and been "fixed" the wrong
  way. That the size check finds exactly the pair the hash-attestation check
  found is two independent methods agreeing, and is the strongest evidence 2i
  has.
- **`ui_load_maps` IS LAZY, so a reading taken at startup is not a reading.** A
  bare `ui_dlmap` before the browser has opened reports `list 0`, and a
  `wrongbuild` of 0 from an empty list says nothing about the install. The first
  cut of p466reget graded exactly that and the control passed while measuring
  nothing. Any arm that inspects the map list must call `ui_maplist` first, and
  its grader must discard rows whose `list` is 0.
- **A FEATURE IS NOT SHIPPED UNTIL ITS DATA FILE IS IN `$ShipGameFiles`.** 0.1.15
  had to be cut because 0.1.14 carried the map-download code and no
  `data/mapdl.txt` for it to read -- `ftesurf/data/*` is gitignored and the ship
  set is a NAMED list, so the file existed on the build box and nowhere else.
  `ui_dl_load` then reads nothing, every row comes from `search_begin` and is
  already installed, and NO ROW DRAWS A BUTTON. It reads exactly like the
  feature being broken. When a feature's input is generated rather than
  authored, adding it to that list is part of the feature, not packaging.
  The release was also six hours older than the commits -- pushed source is not
  a shipped build, and "is it pushed" is a different question from "what did
  the user download".
- **`tools/mapgrab.py` FETCHES WHAT mapsync CANNOT.** mapsync copies from the
  local Steam install, so it is silent about maps this workstation does not have
  either -- 468 of 1748, and 443 of those bhop, which was 131 of 574. Momentum's
  own `_cache/*.dat` carries every map's `downloadURL` and `bspHash`, so the Pi
  curls them directly (2.7 MB/s there, against a 40 Mbit uplink here) and checks
  each against the publisher's digest. 463 of 464 landed; bhop is 574 of 574.
  `tools/grabtest.py` is the falsifier and must keep passing: good hash installs,
  BAD HASH INSTALLS NOTHING, dead url installs nothing, an existing file is left
  byte-identical, and no `.part` survives any case.
- **`mapsync --only` NAMES WHAT IT DROPPED, and the reason is the bug it hid.**
  It intersects against `--momentum`, so three maps living on the cstrike and
  ftesurf mounts vanished from the selection and the run printed "nothing to do
  -- the Pi already has everything selected". An EMPTY selection wearing a
  satisfied one's words, on a tool whose whole job is copying files.
- **`build.ps1` PRINTS THROUGH THE HOST STREAM, so `2>&1 | Select-String` COUNTS
  NOTHING.** A warning count taken that way returned 0 against a build that
  prints `Done. 0 warnings` three times -- the filter saw an empty pipeline and
  would have said 0 with fifty warnings present. Capture with `*>&1`, then count.
  This is the CLAUDE.md filter rule with a new mechanism: not a spelling that
  does not match, but a STREAM that never arrives.
- **`cl_download_mapsrc` IS DEAD CONFIGURATION while `sv_dlURL` is set**, because
  `cl_parse.c:1005` makes it an `else if` on dlURL being empty and `sv_dlURL` is
  the same cvar (`fs_dlURL`) on a client. Measured, not assumed:
  `tools/p465dl.py` serves both url shapes and every request arrived at the
  `sv_dlURL` one. It is kept as the documented fallback, not as the live path.
- `tools/p465dl.py` is the falsifier for the whole thing, and `ui_dlmap` is the
  Download button's headless twin the way `ui_join` is the start button's --
  no cfg in this tree drives a cursor. **Run `--control` too**: it answers 404
  from the same port with the same config and must reach `failed` with nothing
  on disk. A subject arm alone can pass on a stale file from the last run.
- **A STATE SHOWN FOR A FIXED TIME NEEDS A SAMPLE INTERVAL SHORTER THAN THE
  WINDOW.** `DL_HOLD` is 6 s; an arm polling every 8 s reported `active -> idle`
  with the map on disk, which reads exactly like a download that never finished.
  It had finished -- the probe was stepping over the banner.
- **THE TEST LOG ACCUMULATES.** FTE appends, so a driver that does not delete its
  log before the run grades the PREVIOUS arm's lines too. The control's first
  pass showed 12 state samples for 6 calls, opening with the subject's `ok`.
- The sweep is a Windows scheduled task (`FTESurf map scan`, PT6H,
  `tools/mapscan_6h.ps1`) and NOT a Pi cron, because `maproster.py` hashes the
  build this install would load out of the two Steam installs and those are here.
  The cost is stated in that file: a sweep missed while the PC is off is missed,
  not queued.

### The map browser's parallel buffers (build 89, and a build-58 defect)

- **`bufstr_add` APPENDS AT THE BUFFER'S PHYSICAL `used`, WHICH IS NOT
  `ms_count`.** `PF_bufstr_add_internal` (`pr_bgcmd.c`) does `index =
  strbuflist[bufno].used` for the append-on-end form. `ui_load_maps`' second
  pass compacts the list by moving the rows it keeps DOWN and then only moving
  the count -- its own comment says "just move the count", and the dropped rows
  stay physically in the buffer past `ms_count` (81 of them on this box; the
  "maps not listed" line is their count). So from build 58 to 87 every row
  `ui_dl_load` appended was written 81 slots past the index the hash beside it
  recorded, and the hash was right. Name, source, list mask, size and NEW badge
  all landed on a different map's row.
  It survived four builds because the columns it corrupted are UNIFORM over the
  search-derived rows -- `ms_have` is a column of "1", `ms_new` of "0",
  `ms_dlkb` of "0" -- so a displaced write looked exactly like a correct one.
  Build 89's tier column was the first with an independent count to disagree
  with: the engine said 550 KSF tiers where the data files allow 469, and
  550 - 469 = 81 exactly.
  **Write the index (`bufstr_set(buf, ms_count, ...)`) rather than trusting a
  length.** And never size a new parallel buffer from `ms_count` when the ones
  beside it were created before the compaction -- their lengths do not agree
  and nothing warns.
- **TWO NUMBERS FOR ONE QUESTION IS WHAT FOUND IT.** `tools/b89browse.py`
  derives all five of build 89's figures from `data/mapmeta.txt`,
  `data/mapdl.txt` and `data/mapwr.txt` and compares them to what the engine
  printed. The first cut of the PYTHON side was wrong too -- it tested "mapmeta
  has no row" where the engine tests "no tier is shown", missing 7 rows -- so
  the first disagreement was 88, not 81. A condition stated slightly wrong
  reads exactly like a bug in the subject; the way through was to make the
  engine NAME the rows rather than count them.
- **A SECOND TIER SOURCE EXISTS AND WAS BEING THROWN AWAY.** `mapmeta.txt` is
  Momentum's cache. `maproster.py:413` falls back to KSF's roster where Momentum
  has no record (`mtier if mtier != "-" else ktier`) and `mapdl.txt` inherits
  that, so 462 maps had a real tier in a file the menu already opens and drew
  "--". `ui_meta_load` now consults `ms_dltier` where `ms_tierv` is 0 and marks
  the row `ksf`, which draws `T3k`. 469 rows on this box; 128 maps have no tier
  from anywhere and still draw "--", which is the honest answer for them.
- **MEASURE A PROPORTIONAL FONT, DO NOT COUNT CHARACTERS.** The download button
  was a flat `DL_W 92` and "re-get 149.0 MB" was being cut off. The UI face is
  Roboto (`sh_font.qc`); `ui_dl_gutter` asks `stringwidth` for the widest label
  and the widest re-get line and returns 127 px. The arm FAILS if the old 92
  would have been enough -- a fix whose premise is not measured is aimed at a
  guess.
- **A WRAPPED FILTER STRIP NEEDS MORE PITCH THAN ITS OWN HEIGHT.** The wrap was
  `y + 46`, which is exactly heading (20) + `CHIP_H` (26) -- so the next heading
  started on the pixel the chips above it ended. Invisible while a wrap only
  happened in a narrow window; build 89's third strip made it the normal case
  and "library" sat on the tier chips. `STRIP_PITCH` is 52.
- **`buf_sort` IS NOT THE TOOL FOR ORDERING `ms_view`.** Its key is a string
  prefix, and `ms_view` holds indices as text, where "1000" sorts before "2".
  More importantly nothing specifies that it is STABLE, and within a tier the
  order has to stay the name order -- the engine's own NAMESORT next door is an
  explicitly unstable qsort. `ui_refilter` uses a counting sort over 44 buckets
  (ROADMAP 10's data class, then the 11 tier ranks), which is stable by
  construction rather than by assumption.
  A CONSEQUENCE WORTH KNOWING: because appended (downloadable) rows are added
  to `ms_name` last and the sort is stable, they land at the END of their tier.
  Installed maps come first within each tier. That is not a bug, but it means a
  Download button is never on the first screen of a tier.
- **`data/mapwr.txt` IS A SNAPSHOT, and `tools/mapwr.py` has to be re-run before
  a release.** It holds the best known main-track time per map, read straight
  out of surfd's `runs` on the Pi with `MIN(millis)` -- the same row
  `BOARD_ORDER` ("millis ASC, submitted ASC, player ASC", `surfd.py:2056`) puts
  first. MILLIS AND NOT TICKS: tickrate is per-run and 66.6667, 100 and 125 all
  appear in that table, so a tick count is not comparable between rows. 736
  maps have one; 586 of those are Momentum's imported archive and 150 KSF's, so
  on nearly every row this is another community's world record rather than
  anything set here. `ui_wr_load` is deliberately SILENT about a missing file --
  the column is optional, and a warning would send people looking for a tool
  they do not need to run.

- **A SAVED CVAR SHADOWS A SHIPPED ONE, SILENTLY, AND ftesurf.cfg IS READ AFTER
  default.cfg.** `sv_dlURL` was EMPTY at runtime although `cfg/default.cfg` sets
  it, because `ftesurf/ftesurf.cfg` -- what the engine writes on quit -- held
  `sv_dlURL ""`. With no url, `CL_CheckOrEnqueDownloadFile` never reaches
  `CL_EnqueDownload` and returns "nothing to wait for", which `ui_dl_start` can
  only read as a failure. NO MESSAGE AT ANY LAYER: the download button simply
  does nothing. `ui_dl_migrate_url` repairs an empty value and stamps a
  generation, which is `Lob_MigrateDir`'s rule -- and the reason `lobby_dir` was
  fine in the same file while `sv_dlURL` was not is precisely that one had a
  migration and the other did not.
  WHICH CVARS THIS CAN HAPPEN TO: ftesurf.cfg carries ARCHIVE-flagged ENGINE
  cvars (measured by ftesurf-e0: six `set` cvars from default.cfg are absent
  from it, and every line in it is engine-declared with the engine's own
  description). A QC `registercvar` cvar is not written -- unless someone types
  `seta` at it, which makes it archived from then on. `seta lobby_dir_gen "1"`
  is in there, which is also what makes the generation stamp a real one-shot.
- **TWO WRONG ANSWERS BEFORE THE RIGHT ONE, AND BOTH READ AS RESULTS.** Chasing
  that empty cvar: (1) "it is `cl_download_mapsrc`" -- three variants differed in
  the cvar AND in the map, and the map that succeeded under one setting later
  FAILED under the same one. A confounded arm reads exactly like a finding.
  (2) "it is elapsed time" -- +2 s, +18 s and +38 s, three different maps
  (a failed download is cached per file, so retrying one answers the cache and
  not the question); all three failed. What settled it was printing the cvar
  rather than reasoning about the branch that reads it.
- **ms_lst IS "WHICH LIBRARY", ms_src IS "WHERE THE FILE IS", AND THE SWITCH
  WANTS THE FIRST.** Lex, on a laptop: the CS:S list showed about 30 surf maps
  where `data/mapdl.txt` offers 925 that are KSF-listed (and every one of those
  925 is surf; 0 are bhop). `ms_lst` was being taken from the MOUNT alone, so on
  a machine with no cstrike mount every map Momentum also ships read as
  Momentum-only -- 463 of the offerable maps are in both catalogues. `ui_dl_load`
  now ORs the catalogue letters (`k`, `m`, `km`) into `ms_lst` for INSTALLED rows
  as well as appended ones. OR and not replace: a map in the Momentum mount
  really is available from Momentum, and KSF listing it too is an addition.
  Measured cs:s 1027 -> 1080 on a box that HAS CS:S, which is small by
  construction -- the machine without the mount is the one this is for.
- **A MAP ON DISK WAS BEING OFFERED AS A DOWNLOAD.** `ui_load_maps` drops every
  map whose only mount is neither Momentum nor CS:S, and THE GAMEDIR IS ONE OF
  THOSE -- so a map fetched by the Download button landed in `ftesurf/maps/`, was
  dropped from the search list on the next load, fell through to `ui_dl_load`'s
  append branch and was offered again with a size beside it. The one thing a
  Download button must never do is come back after it worked.
  `surf_raqbonus3ramp` reads `src 1 lst 1` here, which is what that looks like.
  The append branch now asks the filesystem (`mapfilekb`, or `ui_file_exists` on
  a pre-466 engine) and writes the same three `ms_have` states the installed
  branch does, so such a row draws Play or Wrong build instead. `ms_dlcount`
  counts what the row will DRAW rather than lines read, or "offers 464" would
  still say 464 after you had downloaded all of them.
- **THE ACTION COLUMN IS ALWAYS RESERVED, and that is why it holds Play.** The
  download gutter used to appear only when `data/mapdl.txt` offered something,
  because a download button was the only thing that ever went in it -- so on a
  complete install it was 127 px of nothing down every row. Lex: "replace the
  Download button box with a green play button box so it doesn't look so empty".
  `ms_have` is one value, so the three states are mutually exclusive by
  construction: "1" plays, "2" replaces, "0" fetches. Play goes through
  `ui_launch` and NOT `ui_launch_local`, so the consent gate and the name gate
  stay in front of it -- a direct call there is exactly the refactor `ui_launch`'s
  own essay warns about.
- **THE TWO HARNESSES FOR THIS BROWSER.** `tools/b89browse.py` derives all five
  of the build-89 figures from the data files and compares them with what the
  engine printed -- two numbers for one question, which is what caught the
  build-58 defect. `tools/b89join.py` drives the pre-join fetch against the REAL
  mirror (a stub would prove the state machine and not the feature) and grades
  its two NEGATIVE arms as hard as the positive one: a join-check that holds a
  join it should not have held is a player who cannot join anything, which is a
  worse bug than the kick it fixes. It also removes the map it downloaded and
  CHECKS the removal, rather than swallowing the error.
- **`tokenize` CLOBBERS A CONSOLE COMMAND'S OWN `argv`.** A diagnostic that read
  `argv(1)`, called `ui_load_maps()` and then used `argv(1)` again ran all three
  of its cases against `surf_zor` -- a word out of mapmeta.txt -- and reported
  the feature doing nothing. `ui_load_maps` tokenizes every line of three data
  files. strzone the arguments BEFORE any call that can tokenize. The server's
  too: Patch 477's `sl_saveat ... go` lost its `go` to SV_SaveReadLight, which
  tokenizes the state file it reads back -- read every argv() first.
### `status` CANNOT SEE MOST OF SERVERINFO -- do not read its silence as absence

`SVC_Status` builds serverinfo into a `char infostr[1024]` and `InfoBuf_ToString`
drops low-priority keys once that fills (`sv_main.c:1253-1256`, which carries its
own `FIXME` about the limit and a `prioritykeys` list "to make sure we include
these before we start overflowing"). A `status` probe of a lobby comes back at
almost exactly 1029 bytes and ENDS ON A CLEAN KEY BOUNDARY, so a truncated reply
is indistinguishable by eye from a complete one.

This session read `sv_dlURL` as unset from such a probe and started debugging a
config that was correct. Use rcon for a specific cvar when the question is "did
this setting take" -- and read the password from `cfg/lobby_local.cfg` inside the
script rather than passing it as an argument, where `ps` would show it.

### Preparing the boards (the sweep, and keeping it fresh)

- **Times and demos are separate jobs and the difference is three orders of
  magnitude.** Every surf/bhop board's top 25 is 3,693 requests, about an hour.
  The DEMOS behind those rows would be ~92,000 files, ~35 GB and a day of
  sustained traffic. So `tools/momfetch.py` fetches times for everything and
  demos stay bounded and on demand. Do not casually widen that.
- **The map catalogue is the one input that cannot be fetched.** `tools/msml.py`
  reads the game's `momentum/_cache/*.dat` (`MSML`, two u32s, a zlib JSON
  array) for map ids and each map's track list; there is no endpoint for either.
  Export it with `--out` and ship the TSV to any box without the game --
  `momfetch --tracks` reads that instead of `--cache`.
- **Ask in the map's OWN gamemode.** The catalogue claims a board in nearly
  every gamemode for nearly every map and almost all are empty (44,676 claimed
  against 3,693 real). `gm_of()` decides by the name prefix.
- **1.0 s between requests, not the reference's 400 ms.** That figure was for a
  person pressing a button; a sweep should cost more, not less. One at a time,
  capped per invocation, honest User-Agent, and a non-2xx STOPS and is never
  retried. Every answer is cached, so a re-run is free and an interruption
  resumes -- which is the property that makes re-running it polite rather than
  rude.
- **MOMENTUM'S API DOES RATE-LIMIT, AND 1.0 s EVENTUALLY TRIPS IT.** Measured
  2026-09-28: HTTP 429 after 2,164 consecutive requests in one 61-minute run,
  ~2,700 across the session. This CONTRADICTS the wrlines reference, which says
  "No 429 was ever observed and none is mentioned in any file -- the constraint
  is stated as courtesy and cost-to-the-operator, not as an enforced limit the
  author ran into." That was true of a tool that never swept; it is not true of
  one that does. The limit is real and it is theirs to set.
  THE ANSWER IS TO COME BACK LATER, NOT TO RETRY. momfetch stops on it, caches
  everything already fetched, and resumes exactly where it left off, so a full
  sweep is two or three sittings rather than one. Do not lower the delay to
  "get it done"; do not add a retry. A 429 is the host asking for less, and the
  only correct reply is less.
- **`surfd/momwatch.py` needs no hook in the game.** surfd already records what
  every lobby is on, so it reads the `lobbies` table, refreshes the boards of
  currently-played maps that are missing or stale, and does nothing otherwise.
  Staleness is per BOARD, so one new stage record does not re-fetch a map's
  other fifteen boards. Cron it; on an idle fleet it makes zero requests.
- **A KSF 500 is an ANSWER, not a refusal.** It is how that host says "not a
  player of mine" -- measured at a third of SteamIDs taken off Momentum's
  boards. Collapsing it into a refusal ends a sweep at its first non-KSF
  player. The reading is INFERRED, so `SKIP_STREAK` (25 consecutive) is the
  breaker on being wrong about it: a host that is really refusing answers 500 to
  everything and trips it in seconds.
- **The two imported tiers differ in watchability, by nature.** Momentum rows
  can carry a replay; KSF rows never can. After a full times sweep most
  `momentum` rows will also be times-only -- the demo corpus is ~5,000 runs
  against ~90,000 board rows -- so "imported" will mostly mean "a time", with a
  minority watchable. `momboards --link` is what joins a fetched time to a demo
  we already hold for the same run.

## Pi operations (public lobbies)

- **THIS FLEET IS A DEVELOPMENT FLEET AND THE OWNER WANTS CHANGES DEPLOYED.**
  Standing instruction from the operator, 2026-09-27, in their words: *"we are in
  development and I WANT changes to be deployed or else I can't test it. You will
  not be affecting any players because I don't have any."* So `build.ps1 -Pi` is
  the normal end of a piece of work, not an escalation to ask about: build to 0 new
  warnings, run the falsifier, commit, deploy, then verify on the host. Do not sit
  on a tested patch waiting for permission — an undeployed patch cannot be tested
  by the person who asked for it, which is the whole point of the fleet.
  The things that still warrant a word first are the ones that are NOT "deploy a
  tested build": destroying data (the evidence tree, the board database, a save
  root), anything that cannot be rolled back, and shipping ANOTHER SESSION'S
  uncommitted work — `-Pi` pushes both progs, so it carries whatever is in the tree.
  `qwprogs.dat.prev` and `csprogs.dat.prev` are kept by the deploy, so an ordinary
  progs deploy is one copy away from reversible; say so rather than hedging.
- **Credentials are the operator's to rotate and they have asked for it to be done
  when needed.** `rcon_password` and `lobby_master_key` live in
  `game/ftesurf/cfg/lobby_local.cfg` (NOT in this repo) and are SHARED with surfd's
  `surfd.env` as `SURFD_RCON_PASSWORD` and `SURFD_KEY` — prove that by hash before
  touching either, and rotate both sides in one pass or the board starts refusing
  heartbeats with `bad key`. Back up with the tree's `.bak-prerotate-<stamp>`
  convention, chmod 600, and never print a value into a log, a commit or a chat
  line. `SURFD_ADMIN_SECRET` is surfd-only. `sv_guidkey` is a different kind of
  thing: rotating it RE-DERIVES EVERY CLIENT GUID and orphans the identity binding
  on existing runs, so it is a data decision and wants asking.
- **surfd is NOT a systemd unit** — the unit file next to it says so in its own
  header. It is gunicorn started by `/srv/nvme/surfd/run.sh` as `proto`, so it
  needs no sudo. `stop.sh` only works if `surfd.pid` exists, and on 2026-09-27 it
  did not: `run.sh` then started a second gunicorn that could not bind 8084, wrote
  a pidfile anyway and exited, leaving the OLD process serving. Kill the real
  master by pid (`ps -eo pid,ppid,lstart,cmd | grep surfd:app`, the one with
  ppid 1), wait for the port to free, then `run.sh` — and confirm ONE master and
  one worker afterwards rather than trusting the "started" line.
- 12 lobbies, systemd `ftesurf@1..12`, basedir `/srv/nvme/ftesurf-server/game`;
  lobby cfgs sourced from this repo's `ftesurf/cfg/lobby/` — edit here, scp there.
- Server CONTENT is hand-copied beside the engine: `game/{momentum (maps only),
  cstrike, hl2}` hold VPKs from a Windows Steam install, mounted by the Pi's
  `fs_addons.txt`, and a lobby mounts new content only on restart. There is no
  Steam and no `data/mapdeps.txt`, so fs_automount mounts nothing: props from the
  CS:GO/TF2/Portal/Momentum-`mount` packs are NOT solid on the server. `hl2` was
  empty until 2026-09-20 (bhop_monster_jam collided 2142 of 6048 prop faces);
  with the 31 `hl2_*.vpk` copied in, the Pi's pm_dettest equals Windows. Prove
  any content change the same way (`cfg/test/p386det.cfg`, a spare port).
- **TWELVE SSH CONNECTIONS IN A ROW LOOKS LIKE A FLOOD TO sshd, AND A DEPLOY CAN
  END WITH THE FILES LIVE AND SOME LOBBIES STILL ON THE OLD PROGS.** Measured
  2026-09-27: `ftesurf@7`, `@10`, `@11`, `@12` all returned
  `Connection closed by port 22` during one `-Pi`. `build.ps1` reported it and
  threw, which is correct — but by then the swap had already happened, so the
  fleet was split: eight lobbies on the new build, four on the old. **Read the
  host after every deploy rather than trusting the "all 12 restarted" line**, and
  restart the stragglers one at a time. If this recurs, space the restarts or reuse
  one ssh connection (`-o ControlMaster`) instead of twelve.
- **THE GIT INDEX IS SHARED BETWEEN CONCURRENT SESSIONS, AND `git commit` COMMITS
  THE INDEX — NOT YOUR PATHSPEC.** This bit both sessions on 2026-09-27 in both
  directions: a `git add -A` swept the other session's uncommitted client work into
  two of my commits, and later my staged server work landed inside *their* commit,
  so my own commit message described changes that were not in it. Staging explicit
  paths does NOT fix it, because the hazard is the window between your `add` and
  your `commit`. **Use `git commit -- <paths>`**, which commits only those paths
  whatever else is staged, and read `git diff --cached --name-only` immediately
  before committing. The code survives either way; what breaks is the record, and a
  commit message describing work that is not in the commit is worse than no message.
- Restart: sudoers is per-unit only — loop `sudo -n systemctl restart ftesurf@$i`
  for i in 1..12. After copying a cfg, restart and READ THE VALUE BACK rather
  than trusting the file: from `/srv/nvme/surfd`, `rcon.Rcon("127.0.0.1", port,
  pw).execute([cvar])` with `pw` read from `surfd.env` inside the script and
  never printed (loopback only, 8 packets per 30 s per port).
- Deploy server progs with `./build.ps1 -Pi` (refuses while players are
  connected, scp's both .new files, hash-verifies on the Pi, swaps in ONE ssh
  command keeping `.prev`, restarts every active lobby); menu.dat stays local.
  `-PiForce` overrides the refusal — beta phase, and the connected player is
  usually the reporter; say so when you use it.
  `-Pi` SHIPS THE WORKING TREE. When the tree carries other sessions'
  uncommitted QC, build from a clean `git worktree add <tmp> HEAD` instead, and
  remove the worktree afterwards. A clean HEAD still carries other sessions'
  COMMITTED patches: check `git log <last deployed>..HEAD` and ask; if one is not
  approved to ship, `git -C <tmp> revert --no-commit <sha>` in the worktree only.
- The lobbies run a NATIVE aarch64 engine, `game/fteqw-svarm64`, built on the Pi
  in `/srv/nvme/p349build` -- as of 2026-09-20 the 375 deploy, Patch 380's three
  server files and Patch 396's `sv_send.c`, NOT 386-388's fs.c/fs_stdio.c; since
  then 418, 419 and 427 (`sv_user.c`), per the `fteqw-svarm64.preNNN-*` swap
  backups in game/. `git hash-object` a file before assuming it is current. That tree is NOT a git checkout: send changed files
  with `git -c core.autocrlf=false archive <sha> <paths> | ssh … tar -x` (plain
  `git archive` here ships CRLF), check them with `git hash-object`, then
  `make -C engine sv-rel FTE_TARGET=linux CC=gcc BITS=arm64 -j3`. Gate:
  `pm_dettest` on bhop_eazy prints the same hashes as the Windows build. For a
  one-off run: `+set sv_port <p> +map bhop_eazy +exec cfg/<x>.cfg`. A dedicated
  server with no `+map` dies with "Couldn't load a map", and the Pi has no
  `cfg/test/`: copy the cfg in, then delete it. Also `pm_verify` a known PASS
  file, because the sweeper uses the new binary at once. SINCE PATCH 492 A PIN-1
  FILE AND bhop_eazy CANNOT SEE THE SOURCE CLIP: `tools/pigate.sh <bin> <port>
  <dir>` (scp it, `cfg/test/p492voy.rec` and the install's
  `maps/zones/local/surf_voyager.json` into <dir>) prints pm_dettest on bhop_eazy
  and surf_ace -- every line, `srctrace` included, must equal Windows -- and
  verifies a pin-1 file and p492voy.rec (pmsrcver 2) through an overlay. The old
  binary REFUSEs p492voy.rec, which is the control. NEVER ROLL THE SWEEPER BACK
  PAST 492: an old verifier reads only the header's pmsrcver, so a Multi-Session
  run parked before a 492 deploy and resumed after it (pin 1 in the header, 2 in
  a later `pm` record) HOLDs there. An ssh that starts a
  background server does not return, so run it in the background. Run
  hand tests on a port other than 27698, which is the sweeper's. Swap by
  `cp` to `.new` then `mv -f`, keeping `fteqw-svarm64.preNNN-<stamp>`. Running
  lobbies keep the old binary until restarted; the sweeper picks up the new one
  immediately.
- **AN OVERLAY BASEDIR IS LINKS INTO THE LIVE GAME, AND A GUI DELETE FOLLOWS
  THEM.** 2026-10-05: an old overlay, /srv/nvme/p323base (126 links, 24 MB real,
  57 GB to anything that follows links), was deleted with a file manager and
  emptied game/ftesurf/{models,glsl,particles,scripts} and all of
  game/momentum/maps while 12 lobbies ran. Restored the same day from the 0.1.23
  stage and the Windows Steam Momentum install (1347 BSPs, a superset of the
  library), rotation maps first. Remove an overlay with `rm -r <dir>` in the
  session that made it; never leave one behind.
- To pm_verify a fixture-zoned file on the Pi (surf_666 with p360sf) without
  touching live zones: an overlay basedir -- link every entry of game/ except
  ftesurf/, and every entry of game/ftesurf except data, logs and maps; put the
  fixture at <overlay>/ftesurf/maps/zones/local/<map>.json and the files under
  <overlay>/ftesurf/data; run game/fteqw-svarm64 -basedir <overlay> with the
  sweeper's arguments (port != 27698). Remove it after (rm -r keeps link targets).
- Configs reach the Pi BY HAND: `-Pi` ships only the progs. A dedicated server
  execs `cfg/default.cfg` when there is no `server.cfg` or `quake.rc`
  (`sv_main.c:6714`).
  DIFF BEFORE COPYING, and list the server-relevant cvars that would change.
  Until 2026-09-18 the Pi's copy carried a hand-written `set pm_slide 0`
  block, which gated func_slide (Patch 280) off from the build 66 deploy. Lex
  turned slides on, and the Pi now runs the repo's file. Mover cvars must be
  set IN default.cfg: `cvar_lockdefaults` makes a later cfg or rcon unable to
  change them. A lobby's real physics values are in its recordings' `pmpin`
  header.
  A RULE CHANGE IN `default.cfg` NEEDS THE COPY TOO, and `-Pi`'s output never
  mentions it: Patch 445's `run_rearmhop 0` was "deployed" 2026-09-27 and the
  fleet ran `1` until 2026-10-03. Compare the two files' sha256 after a deploy.
- `rcon.Rcon(...).execute(argv)` runs ONE command, so `execute(["a", "b"])` SETS
  `a` to "b" -- on 2026-10-03 a two-cvar "read" did exactly that to two lobbies.
  One cvar name per call.
- Post-deploy verification is a CLIENT CONNECT, not the journal: `ftesurf@N`
  journals need sudo (sudoers is restart-only) and lobby cfgs write no file
  logs. Use the `cfg/test/p339pi.cfg` pattern — headless client into a live
  lobby, check the `trig:` census, hook-alive line and prederr count; every
  rotation map exists locally in the Steam Momentum library.
  **"NO FILE LOGS" IS ABOUT THE CFGs, NOT ABOUT THE ENGINE, and the difference
  matters: a lobby's file log can be TURNED ON BY RCON for the length of one
  measurement** -- `log_name <n>`, `log_dir logs`, `log_enable 1` (one cvar per
  `execute()` call), read `<basedir>/ftesurf/logs/<n>.log`, then `log_enable 0`
  and delete the file. That is the only way to see server-side `print()` output
  from the fleet, and it is what `cfg/test/deploy496smoke.cfg` needs because a
  server QC `print()` does not reach the client's log at all (see the pitfall).
  It is also a temporary change to a public lobby: do it on one unit, say so in
  the entry, and put it back.
- **A LOBBY PORT IS 27510 or 27520..27620 (cfg/lobby/lobby<N>.cfg), NOT 27698.**
  27698 is the sweep server's, which AGENTS.md already says to avoid for hand
  tests, and connecting to it from a smoke cfg produces `Can't "cmd", not
  connected` four times -- which reads exactly like dead progs and was a dead
  port. `build.ps1 -Pi` discovers the fleet's own ports over ssh rather than
  keeping a list, so nothing else in the tree repeats this mistake by accident.
- **`build.ps1 -Pi` MIS-BINDS ITS OWN PARAMETERS WHEN ITS OUTPUT IS REDIRECTED
  TO A FILE, AND THE GUARD IS WHAT MAKES THAT SAFE.** Measured 2026-10-06, pwsh
  7.6.6, same command line both times: `pwsh -NoProfile -Command
  "./build.ps1 -Jobs 8 -Pi" *>&1 > /tmp/x.txt` reaches the Pi step with
  `$PiGame = 'cl_progs.src'` -- a value that appears nowhere else in the script
  except as the middle element of its own compile list -- and throws
  `-PiGame 'build.ps1:cl_progs.src' is not a plain absolute path`. The identical
  invocation piped (`2>&1 | grep ...`), or run bare, or run through `-File`,
  binds correctly and deploys. Probes pin it: `$PiGame` is still correct at
  script start, at `Step "QuakeC"`, after `Push-Location` and inside the compile
  loop, and is wrong by `if ($Pi)`. Nothing in the script assigns it. A minimal
  faithful reproduction does NOT reproduce it, so this is a pwsh host/binding
  fault rather than a script one -- which is why the fix is not in the script's
  logic. TWO RULES FOLLOW: never grade or capture a `-Pi` run with `*>&1 > file`
  (use a pipe, or `-File`), and never remove that `$PiGame` regex guard, whose
  only job is to stop a corrupt path reaching twelve `scp` and `ssh` calls.
- surfd is `surfd.service` (gunicorn :8084 behind nginx), and its app log is
  `/srv/nvme/surfd/logs/surfd.log`. To deploy:
  1. Take the files FROM THE COMMIT, not the tree:
     `git -c core.autocrlf=false archive HEAD surfd/... | ssh … tar -x` into a
     /tmp stage.
  2. Run the suite there, with `TMPDIR` set to a private dir; the tests leave
     their temp dirs behind. Stage `tools/` and `src/shared/` beside `surfd/`
     (test_sweep and the TF_* pins read them). `test_momindex.py` is an import
     arm, not a suite member: it needs `--db <copy> --momentum <tree>`.
  3. Back up `data/surfd.db` with sqlite's backup API. (The `database is
     locked` heartbeats that seemed to follow it on 4 Oct were momwatch's: they
     land on every `*/7` tick, all day, backup or not -- see BACKLOG.)
  4. Copy the files in under `flock /tmp/surfd-sweep.lock`.
  5. Reload the gunicorn master, then read the log for `surfd ready`. SINCE
     27 SEP THAT IS NOT THE UNIT: `surfd.service` is dead and surfd runs from
     `run.sh` with `--pid /srv/nvme/surfd/surfd.pid`, so `systemctl show surfd
     -p MainPID` reads 0 and `kill -HUP 0` signals your own process group (it
     killed a deploy script on 4 Oct, mid-reload). Check the pidfile names a
     live `surfd:app` gunicorn, then `kill -HUP $(cat …/surfd.pid)`.

  **`tools/surfd-deploy.ps1` IS THAT PROCEDURE AS A SCRIPT** (added 2026-10-05):
  stages from a COMMIT with `git archive`, runs the suite in the stage on the Pi,
  backs up the db, copies under the flock, reloads, and then -- the step that
  matters -- **hashes every deployed file on the Pi against `git rev-parse
  <sha>:<path>`** and fails if any differ. Use it instead of hand-running the
  above; `-SkipTests` and `-NoReload` exist and should be said out loud if used.
  IT ALSO KEEPS THE CREDENTIAL STORE OWNER-ONLY: the backup it makes is chmodded
  600 and the deploy FAILS if that did not take, and its step 7 tightens any loose
  `surfd.db*` file and reports what the backups cost (`OURS=` / `HANDMADE=` /
  `TIGHTENED=` / `STILL_LOOSE=`). `-KeepDbBackups N` prunes the script's own,
  oldest first, only after the deploy has verified; the default REPORTS AND
  DELETES NOTHING, because a deploy that made the backup is not a deploy that may
  decide to destroy older ones.
  FIVE TRAPS IT PAID FOR, all of them the shape "the tool reported success while
  doing nothing":
  - **A COPY THAT PRINTS A COUNT IS NOT A COPY THAT COPIED.** Its first run
    reported `COPIED=49` having installed zero files: a variable that did not
    expand made every destination an empty string, `install` failed 49 times,
    `set -e` did not fire inside the loop, and the counter counted iterations.
    Nothing on the live host changed, /health answered, and the reload "succeeded"
    by reloading the old code. **Verify by hashing the destination, not by
    counting the loop.**
  - **`set -e` WITHOUT `set -u` TURNS A TYPO INTO AN EMPTY STRING.** A
    `$backupTag` that failed to interpolate inside a here-string did not error;
    it silently made the backup name and the destination empty. `-u` makes an
    undefined variable fatal, which is the only thing that converts this class of
    bug from silent to loud.
  - **`git ls-tree` PATHS ARE REPO-RELATIVE AND THE PI'S LAYOUT IS NOT.** The
    files it names are `surfd/recplot.py`; the Pi has `recplot.py` directly in
    `/srv/nvme/surfd`. Installing under the repo-relative name wrote 49 files into
    a NESTED `surfd/` that is not a package and is not on the import path -- live
    files untouched, deploy "successful". (The stage must keep the repo-relative
    names, because `tools/` has to land beside `surfd/` for the suite.)
  - **POWERSHELL `-match` IS CASE-INSENSITIVE**, so grading a remote script on an
    uppercase `FAILED` sentinel matched every suite's own `0 failed` success line
    and seven passing suites read as a failure. Use `-cmatch`/`-cnotmatch` for
    sentinels. And `$LASTEXITCODE` READ AFTER A POWERSHELL FUNCTION RETURNED IS
    STALE -- a function call does not set it, so the check graded an unrelated
    earlier command; capture it immediately after the native call and pass it out.
  Also: a function named `Ssh` and the `ssh` executable are ONE name in
  PowerShell, so `& ssh` inside it recursed until "call depth overflow" -- the
  release-script `-QcBuild`/`$qcBuild` trap above, in a function name.
  - **THE REMOTE BODIES RUN UNDER `sh`, AND POWERSHELL'S `-replace` IS A
    CASE-INSENSIVE REGEX.** `Invoke-PiScript` pipes the body to `sh '$stage/<name>.sh'`,
    so bash-only spelling (`read ... < <(...)`) is a syntax error on the Pi's dash --
    `sh -n` the body over ssh before believing it. And a `KEEP` placeholder in a
    body replaced with `-replace 'KEEP', $n` also matched the English word
    "keeping" in the printf two lines below it, putting a number in the middle of a
    sentence. Placeholders are `__NAME__` applied with the literal, case-sensitive
    `.Replace()`; the same reasoning as the `-cmatch` sentinel rule above.
  - **LONG SSH COMMAND-ARGUMENT SCRIPTS CAN TRUNCATE AND STILL EXIT ZERO.**
    Patch 507's checked 10.6k-character body copied source and ran its first
    installed controls, then the remote shell warned that a here-document ended
    at EOF. The remaining race probe, real receipt pass, reload and final health
    checks had never run; the caller still printed its success line. Local syntax
    checks prove the original body, not what transport delivered. Stream long
    bodies through SSH stdin to an explicitly selected `bash -s` (or `sh -s` for
    POSIX bodies), and require every final control/health/UTC sentinel plus exit
    zero and no heredoc warning. Finish only the missing gates after verifying
    installed/paired hashes; never recopy or reinterpret a partial deployment as
    complete. P507's finish-only streamed arm proved the remaining controls and
    reload at 2026-10-06 15:28:23 UTC; source and owner-only backups were retained.

  DEPLOYED (the Pi keeps no receipt of its own, so this line is the record; UTC):
  `2007afc` to /srv/nvme/surfd at 2026-10-04 18:00 -- all 49 files hash-matched
  the commit, master 2479950 unchanged since 27 Sep, worker re-forked to 425928,
  `surfd ready` 18:00:26, /health `{"ok":true,"lobbies":12}`, seven suites green
  in the stage. Backups: `*.pre2007afc-20261005-045845` (34 files it replaced) and
  `data/surfd.db.bak-2007afc-20261005-045845`. Verified live afterwards: run 749
  serves `momdemo e9a68559…` and no integrity key.

  **2026-10-05 10:09-10:14 UTC, the 0.1.23 batch (game `44e9bd8`, engine
  `f2630d9ad`, binaries tag `patch-494` = `6b7b70143`).** Pi engine: 38 files sent
  to p349build from 6b7b70143 (all hash-checked), `make sv-rel` -> md5 07323ee4;
  `tools/pigate.sh` equal to Windows on bhop_eazy and surf_ace (srctrace
  de0ed342 / f89ef15d), boreas 0003107 PASS, p492voy.rec PASS, the old binary
  REFUSE; swapped keeping `fteqw-svarm64.pre492-20261005-100948`. Cfgs:
  default.cfg (pm_fixrampbugs 2, run_movebound 2000) and
  maps/map_surf_voyager.cfg, backups `*.pre492-20261005-100948`. Progs:
  `build.ps1 -Pi` from the clean worktree, 0 players, all 12 restarted -- read
  back: every lobby's process is md5 07323ee4, lobby 1 `pm_fixrampbugs` 2.
  surfd: `surfd-deploy.ps1 -Ref 44e9bd8`, `surfd ready` 10:13:01, /health ok,
  backup `data/surfd.db.bak-44e9bd8-20261005-211108`. Release 0.1.23 published
  10:14 (Windows sha256 AD3085A7..., Linux 1E10FEC0...).

  `490f73d` then `e11084c` to /srv/nvme/surfd at 2026-10-05 03:48 and 04:03 --
  schema 10 (`sims`, the store-only cross-run similarity sample), eight suites
  green in the stage including the new `test_simcheck` (40 checks), all 53 files
  hash-matched the commit, master 2479950 unchanged, `surfd ready` 04:03:22,
  `/health {"ok":true,"lobbies":12}`, live `user_version` 10 with 0 `sims` rows.
  Backups `*.pre490f73d-20261005-144643` and `*.pre-e11084c-…`, plus
  `data/surfd.db.bak-490f73d-20261005-144643`.

  **[HISTORICAL: superseded by the 2026-10-06 runtime read below] THE SIMILARITY
  STEP STORED NOTHING ON THE PI THEN, AND THAT WAS EXPECTED RATHER THAN BROKEN.**
  At that observation `tools/census/` was not deployed beside the game, so
  `_recsim()` found no comparison and the step degraded to storing nothing and
  printing its reason on every sweep line -- the behaviour the receipt step's
  lazy imports exist for. The then-live `simcheck._recsim(sweep.TOOLS)` reported `no
  recsim.py found (tried: /srv/nvme/ftesurf-server/game/tools/census/recsim.py,
  /srv/nvme/tools/census/recsim.py)`.  The first path is the RIGHT one and is
  where reccheck.py and rcptcheck.py live; installing `recsim.py` there could
  activate the step with no code change and no reload. The 2026-10-06 read below
  found it already installed; this old observation is not current provenance.
  **AND NOTE THE SECOND PATH IT TRIED, BECAUSE IT IS A TRAP.** `/srv/nvme/tools`
  EXISTS and is a steamcmd directory (linux32, linux64, steamcmd.sh) with nothing
  to do with this tree.  It is `<surfd>/../tools`: simcheck's own-neighbourhood
  fallback, which `e11084c` kept, so a `census/recsim.py` there would have been
  imported and RUN by the sweep.  It is gone (branch surfdfix); the module
  searches only the caller's resolved directory (else SURFD_TOOLS), because a
  default is policy and two spellings of one policy drift.
  The measurement this feature was for was made on a COPY of the live database and
  reproduced `recsim.py`'s census exactly through a different code path: 24 pending
  runs, 22 pairs, 20 compared, 2 unjudgeable, 0 notable, same-identity max 0.5866
  (n=12) against cross-identity max 0.2146 (n=8).  Two independent derivations
  agreeing is the strongest evidence it has.

  `d42165e` to /srv/nvme/surfd at 2026-10-05 04:46 UTC -- momboards' link_demos
  fix (a symmetric LINK_SLACK_MS bound: a superseded slower demo can never again
  become a faster row's watch link) AND the cf6cd12 momgrab/momwatch/momindex/
  ksfimport batch that had sat undeployed since e11084c (momwatch's change is
  itself a logging fix -- a handler on surfd's logger so the per-tick import
  stops reading as a restart).  Nine suites green in the stage including the new
  `test_momboards` (9 checks), all 54 files hash-matched the commit, master
  2479950 unchanged (SIGHUP to the pid, never the unit), `surfd ready` 04:46:46,
  `/health {"ok":true,"lobbies":12}`, 2 processes.  Backups
  `*.pred42165e-20261005-154500` and `data/surfd.db.bak-d42165e-20261005-154500`.

  `df00b61` to /srv/nvme/surfd at 2026-10-05 04:59 UTC -- the player pages
  (561bb1e) and the test isolation they needed.  561bb1e itself stopped in the
  stage, nothing installed: `test_join` counted the Pi's 66 real local zones,
  because SURFD_ZONES_LOCAL defaults beside the live run tree.  56 of the
  commit's 58 surfd files hash-match (README.md and ftesurf@.service differ as
  before), master 2479950 SIGHUP'd, `surfd ready` 04:59:40, `/health` ok.
  `data/people.json` (0600, 10 MB) was then built by one local request (8.6 s
  on 127.0.0.1:8084) so no visitor paid the first build behind nginx's 5 s;
  deploys keep it, only `people_reset()` or a fresh install removes it.
  Through nginx: profiles 1.77 / 0.56 / 0.47 s, directory 0.04 s.  Backups
  `*.predf00b61-20261005-155751`, `data/surfd.db.bak-df00b61-20261005-155751`.

  `baadc73` to /srv/nvme/surfd at 2026-10-05 05:58 UTC -- the review fixes to
  561bb1e (per-writer snapshot temp names, a single-flight cold start, no older
  directory over a newer one, a stamp ahead of the clock counted stale, the
  thread-start guard, "Show more" by prefix via `limit`, and the maps cache's
  empty answer for 300 s after a boot).  Live hashes matched df00b61 at 05:56.
  After: a profile 2.66 s on the new worker's first request (snapshot load),
  `limit=200` 0.62 s, people.json rewritten by the background rebuild at
  05:59:13 (0600, no temp left).  Backups `*.prebaadc73-20261005-165654`,
  `data/surfd.db.bak-baadc73-20261005-165654`.

  `8cd56ee` to /srv/nvme/surfd at 2026-10-05 06:34 UTC -- three submit-path
  fixes out of the b818e8a review: adopt only a `kind='run'` replay's tier (a
  trusted post naming a momindex leaf can no longer file a board row under
  `momentum` nor unlink the imported row's demo), the hidden `tier@runid` slot
  now checks the stage cap (a rejected run cannot park stages past it), and the
  leg-0 cap scan runs BEFORE the write lock instead of holding it 0.37 s on every
  first finish (the scan is still 0.37 s -- BACKLOG keeps the index/count latency
  follow-up, with the teeth each has).  Nine suites green in the stage including
  the new falsifiers test_replays s15 and test_board s23/s24, all 54 files
  hash-matched the commit, master 2479950 SIGHUP'd, `surfd ready` 06:34:18,
  `/health {"ok":true,"lobbies":12}`, 2 processes.  Backups
  `*.pre8cd56ee-20261005-173227` and `data/surfd.db.bak-8cd56ee-20261005-173227`.

  `a254da2` to /srv/nvme/surfd at 2026-10-05 07:30 UTC -- the board database and
  its backups are the owner's alone (`runs.player` is a guid, and a guid is what a
  keyed lobby authenticates a submit by; sqlite creates the db 0644 & ~umask and
  the Pi's umask was 022).  Nine suites green in the stage including
  `test_surfd` section 10, all 54 files hash-matched the commit, master 2479950
  SIGHUP'd, worker re-forked to 1226126, `surfd ready` 07:30:49,
  `/health {"ok":true,"lobbies":12}`, `/board/api/map` 200.  Backups
  `*.prea254da2-20261005-182858` and `data/surfd.db.bak-a254da2-20261005-182858`
  (the first one this script wrote at mode 600 -- it chmods and then FAILS if the
  backup is not 600).  Step 7 of the deploy now reports the backups and tightens
  any loose `surfd.db*`: `OURS=12 files, 8236 MiB`, `HANDMADE=24 files, 1814 MiB
  (never pruned here)`, `TIGHTENED=36` on the run that fixed the existing copies
  (0 on the deploy, which found none left), `STILL_LOOSE=0`.  Pruning needs
  `-KeepDbBackups N` and is OFF by default -- 9.3 GB of copies on a volume at 88%
  is Lex's decision, in BACKLOG.
  PROVEN LIVE THREE WAYS, because a mode read once is not a mode kept: the
  WORKER's `/proc/<pid>/status` reads `Umask: 0077` while the MASTER's still reads
  `0022` (a SIGHUP re-forks the worker and the app is imported there, so the
  master keeps the umask run.sh started it with until a full restart -- it writes
  nothing sensitive); the db and its newest backup both `stat` 600; and a db
  `chmod 644`'d BY HAND was back to 600 after ONE request that connects, which is
  `_harden_db_files()` in production rather than in a test.  Still open and in
  BACKLOG with its measurement: the GAME's data tree, 10,938 of 10,938 files 0644
  under `game/ftesurf/data` with the guid IN THE `.rec` FILENAME, so a directory
  listing alone leaks it and file modes cannot fix it (the lobby unit says
  `UMask=0022`).

  `migrate()` runs on EVERY `import surfd`, including sweep.py's cron import,
  so each schema step must be idempotent and safe to race. admin.py must not
  import surfd; surfd injects what it needs.

  `sweep.py`'s receipt step (schema 7/8: `receipts`, `pubkeys`, `sweepmeta`) imports
  `rcptcheck`/`reccheck`/`ed25519` from `<SURFD_GAME>/tools` (`SURFD_TOOLS`),
  and the import is INSIDE the function on purpose: a host without them must
  keep running the verification it has run since Patch 349. Deploy those three
  beside the game, not beside surfd. Both new tables are store-only -- nothing
  in `VER_SQL` reads them and no badge moves.

  DEPLOY surfd/ AND tools/ IN THE SAME PASS, and check the sweep log after. On
  2026-09-21 the surfd half went up alone and the receipt step failed on every
  cron tick for three hours with `AttributeError("'Receipt' object has no
  attribute 'angles'")` -- a new `sweep.py` calling a `rcptcheck.py` that
  predated the function. The try/except held (the Patch 349 verdict sweep ran
  on the same line, every time) and `receipts` simply stayed at 0 rows, which
  is exactly why it is easy to miss: nothing is down, nothing is loud. Read
  `/srv/nvme/surfd/logs/sweep.log` for `receipt step failed`, and
  `sweep.py --dry-run` for the unread count.
  A tools-only deploy needs NO `kill -HUP`: surfd does not import them, so the
  PID and the lobbies are untouched. Copy under `flock /tmp/surfd-sweep.lock`
  with `install` + `mv` so no cron import can see a half-written file.
  READERS BEFORE CLIENTS. Engine Patch 468 journals carry a 12-field `end`,
  five-field `p` records and a `touchpad` device type. A `hidcheck.py` older
  than efc4627 reads every one of them as "never closed"; efc4627 passes a
  journal whose pad never fired and faults every `p` line of one that did;
  fde8420 is the floor (the length sets are strict on purpose). Deploy
  tools/ to every host that reads journals before any 468 client exists.

  **DEPLOYED 2026-10-05 02:43 UTC (game repo `24b50bf`).** The rule above had
  not been followed: `hidcheck.py` was ABSENT from the Pi and `reccheck.py` /
  `rcptcheck.py` were at their 2026-09-21 and 2026-10-03 blobs, i.e. before Patch
  484. All four are now at HEAD's blobs, verified by `git hash-object` ON THE PI
  (`493097d8`, `85fcfc68`, `fbb8c624`, `bb522ba4`) and not by size or mtime.
  Backups: `*.pre490-20261005-024331`. Installed under `flock
  /tmp/surfd-sweep.lock` with `install` + `mv`, `__pycache__` cleared, no surfd
  reload (the sweep re-imports per invocation, so a tools-only deploy needs no
  `kill -HUP`).
  WHAT THE ABSENCE COST: less than the rule implies, and it is worth knowing why
  rather than assuming the worst. `sweep.py` imports only `rcptcheck`, which
  imports `reccheck` and `hidcheck` LAZILY and inside a try, so a missing
  `hidcheck` degraded `r.journal` to "" plus a note instead of taking the receipt
  step down — and the fleet holds `0 hid` in `data/evidence/`, so nothing was
  actually going unchecked. The stale `reccheck` was the live one: Patch 477's
  `pin` warp kind is missing from its `WARP_KINDS_V9`, so a pinned run's warp
  reads as an unknown kind. Verified after: `sweep.py --dry-run` exit 0 with no
  receipt-step failure, all four import, and `rcptcheck.py data/evidence` checks
  19 receipts of which **2 fault** — both on surf_4am, both the KNOWN save-lock
  hold fault documented below at 33-41% of one-frame ticks (one reads 45.8% of
  155), not a regression from this deploy. 18 of the 19 commit to evidence that is
  not on the host, which `rcptcheck` calls absent rather than a fault.
  **A NOTE ON VERIFYING A DEPLOY: two ssh calls made back to back can read the
  directory in different states, and the one that ran second is not the one that
  is right.** The install and an independent check were issued together; the check
  reported `hidcheck.py ABSENT` and the pre-deploy hashes while the install
  reported success. A third, single-call read settled it — all four present at
  HEAD's hashes. Settle a contradiction with one authoritative read rather than
  believing either of the two that disagree.

  Schema 8 (Patch 422, first key wins) is admin-only too. Three things an
  operator must know:
  - `receipts_v8()` runs on EVERY migrate() -- a repair, not a step. It marks
    rows a pre-8 sweep wrote (`signed_at = 0`) stale = 1 (signature unknown,
    not judged) and voids the watermark. `--reread-receipts` marks stale = 2:
    the signature is known and is still judged until the re-read replaces it.
  - "unsigned" is judged only below `sweepmeta.receipts_through` (the last
    complete receipt pass) less 300 s, so a stalled receipt step pauses it
    instead of flagging every signer. The admin runs page says so in red after
    an hour: that note, not the flag count, is how a broken step shows now.
  - Patch 501: initial receipt/sibling-digest I/O alone defers the read, like
    a PENDING reread, rather than storing a permanent evidence FAULT. A separate
    measured signature/recording/digest fault survives sibling I/O; a pending
    join's recovery cannot clear it. Partial stale rereads preserve old content
    joins and the stale retry flag; their automatic completion also retains
    the measured primary fault (`receipt_partial:` metadata). Unknown first-stat
    paths still get a queue identity; disappearance cannot restore coverage.
    Failed reads consume the pass budget, with
    a durable per-path queue: arrivals/attempts go to the tail. An array cursor
    is NOT stable under compaction and arrivals; it still starved a stale row.
    Coverage uses ALL unread fresh receipts, independently of attempt order,
    or stays unchanged when an age is unknown. Enumerate both
    directory levels explicitly: glob silently hides unreadable map directories.
    `test_sweep.py` exercises failure/recovery, persistent-failure progress and
    source removal between a measured fault and an unmeasured join's recovery.
    Repeating `--reread-receipts` does not supersede an in-flight partial read;
    complete it before requesting a new reinterpretation. Permanent lost
    unobserved receipts pause unsigned coverage until operator reconciliation.
  - P501 deployed from clean reviewed/published `4f16963` on 2026-10-06 at
    07:52:56 UTC: 262 sweep checks, 306 reader checks, nine app suites pass on
    the Pi. Installed ONLY sweep/test_sweep and the matching four reader files
    under the sweep lock, with DB/file backups and all six blob hashes verified.
    The old live reader API lacked fields the sweeper expected (50 exceptions
    in its last 100 log lines). New live read ACTED: 1 receipt / 0 faults, rows
    19 -> 20, coverage 1791203401 -> 1791272575; health stayed ok / 12 lobbies.
    No progs/lobby swap or web reload. The 19 earlier receipt rows were not
    automatically reread; paired deployment is NOT historical recalibration.
  - Patch 503: receipt hash and content checks share captured `.view`/`.hid`
    bytes, including captured absence/read errors; `.rec` runid/nonces/angles
    share the selected handle's decoded observation. Parsers accept keyword-only
    `data=` without reopening the path and retain text-mode UTF-8 replacement
    and universal-newline behavior. Never hash a path and then reopen it to
    claim its content was signed. `tools/test_rcptcheck.py` swaps files AFTER
    the first read closes, with controls proving replacement and later digest
    rejection. This is one observation, not filesystem atomicity, persisted
    receipt identity, late-arrival scheduling or hardware attestation. Deploy
    rcptcheck/reccheck/hidcheck together from a clean inspected commit; no
    automatic historical reread or detector/policy change belongs in this slice.
    Selected `.rec` tail I/O must defer (not become ordinary absence); unknown
    final-session nonce cannot be inferred from its readable header. Known
    sibling presence can prove a missing-digest contradiction even when reading
    bytes fails; unknown presence cannot. Final reviewed `4303a0e` deployed on
    2026-10-06 09:52:46 UTC: 74 snapshot controls, 262 sweep, 306 reader and
    263 HID checks all pass; nine app suites plus all three reader suites pass
    on the Pi. Four reader/crypto files match the commit on the Pi and both
    Windows installs. Installed caller ACTED on generated signed HID (OK) and
    changed-digest control (FAULT), without storing test evidence; real receipt
    step read 0. This is integration verification, not new fleet calibration.
  - Patch 510: missing-source readiness is a captured observation, not a later
    filesystem inference. A successful full read can establish a missing-rec
    wait; a late-view completion may RETAIN that wait but cannot create it.
    Initial candidate: checked rec -> prune rec -> late view -> new rec wait ->
    returned/replaced rec automatically judged. Review exposed that excluded
    completed-source rearm despite 212 passing checks. Four new scope checks
    fail on the candidate; corrected suite has 227 passes. Both completed and
    historical-unknown cases must prove the direct reader's contradiction and
    an explicit full reread ACT, not just assert scheduler silence.
    `surfd/sweep.py:receipt_step` now keeps rec/view/HID turns separate; persisted
    co-ready order is rec/view/rec/HID, with bounded attempts and row fairness.
    Discovery headers are hints only; selected bytes and original receipt binding
    authorize joins. A checked view is hashed again to bind a newly possible rec
    pair, never to schedule completed-source replacements. Unknown readiness and
    initial partial observations still need a completed explicit full read.
    Frozen published b1be008 shipped only sweep/new recording suite on the Pi
    at 2026-10-06 16:23:30 UTC after both re-review lenses and 18 Linux suites.
    Installed temporary/in-memory controls ACTED; real pass 0 reads/faults and
    two bound rows unchanged, reload/health proved. No engine/progs/schema/reader
    or detector-policy change. Header discovery cost at fleet scale is unmeasured.
  - test_admin runs `node --check` on the admin pages' scripts (f19d477 shipped
    one that never ran). The Pi has no node and prints a skip, so run it on
    Windows after editing a template. On Windows its `amplification guard` and
    `three snapshots` rcon checks fail (UDP to a closed port resets instead of
    timing out); they pass on the Pi.

  BUMPING `SCHEMA_VERSION` BREAKS ANY SUITE THAT PINS THE LITERAL. 6 -> 7 broke
  test_join and test_replays, which know nothing about receipts; they compare
  the upgrade path to where a fresh database lands now. Do the same in a new
  one. test_board went unbumped for a day; it has one `HEAD_SCHEMA` now.

  Patches 424/425 (no schema bump; `replays_bound()` runs on every migrate):
  - `replays.bound` is 1 when the replay was filed against its file (header
    matches runid, map, track, leg, flags, tickrate). -1 means "not assessed"
    and is resolved from the disk by the next migrate, i.e. the next cron sweep;
    a row whose file cannot be read stays -1 until it can. After a deploy, check
    that the live rows came out 1: `SELECT kind, bound, COUNT(*) FROM replays
    GROUP BY 1, 2`.
    A reject hides the stage times of every bound replay's run.
  - `replays.sha` is the file's sha256 at filing and `sha_at` the `submitted`
    it belongs to. A re-post is new evidence only if player, ticks, bytes or a
    known, current sha differ; an unknown sha ('') falls back to "the header
    names another run". `_file_sha` hashes only the file whose header was just
    read, and caches by (path, inode, size, mtime_ns).
  - Tiers ending `@<runid>` are a rejected run's hidden stage times, and
    `^<its own runid>` (`^r<id>` recorded, `^-<submitted>` no runid) a time
    waiting behind a better one; neither reaches a public board. Reviews move
    them. Do not delete them by hand: a clear gives them back.
  - Patch 426's arms: `cfg/test/p426{cl,bcl,ccl,dcl}.cfg` against `p426sv.cfg`
    and the stub `b65stub.py cert 8131`. p426dcl needs `+set sv_mintic 0.1`
    on the server to make its same-physics-step race frequent (1 in 21 at the
    default step).
  - Before 425, test_board wrote `.rec` files into the DEFAULT `SURFD_RUNS`, the
    live run tree. It sets its own temp dir now. Point every suite at one.

  And the live database is `<SURFD_HOME>/data/surfd.db`, NOT
  `<SURFD_HOME>/surfd.db` -- a stray empty file at the second path has existed
  since 2026-09-21 and is not it.

### Observer deployment gates: resolve the live tool and bound verification

Measured 2026-10-06, frozen game `bf5153d` (P521/P522 and the tooling-only
`4c519b9` runtime installer). The old missing-similarity-tool note above was stale:
the installed recsim.py matched published `34c2984` exactly, with two native rows
and one stored pair. Its diff to the current canonical source was comments only.
Use the explicit resolved tool path and inspected predecessor hash; do not
blindly overwrite an unexpected file. `tools/simcheck_runtime.py` packages only
clean exact-commit bytes and installs one fixed path, dry-run by default, with
paired-reader hashes, predecessor guards and rollback. Installed long/short
controls passed on the Pi and both Windows installs; this is not new activation,
complete pair coverage, hardware provenance or calibration.

Two private post-swap gates failed while the destination hashes were already
correct. First, `_recsim()` returns `(module, loaded_path)` on success, not an
empty reason: check the path, do not reject a loaded module for its path string.
Second, a verification snapshot attempted `SELECT * FROM runs` into Python: the
live board had over three million rows and the probe was killed. Kernel evidence
did not establish the kill's cause; do not claim a confirmed OOM. Health stayed
at 12 lobbies. A replacement gate denied protected-table DML with SQLite's
authorizer (a denied no-op proves the guard acted), compared bounded metadata and
scalar board counts, and reported 0.093 s for the collector/post-history interval
with no new stored pairs. Never materialize the board to prove an observer did
not modify it.

Finish only missing controls after rechecking frozen destinations and rollback
copies; do not recopy source or overwrite the first backup. All 26 Linux suites
passed, installed API/storage/path controls acted, then master-preserving worker
replacement/ready log and health completed at 2026-10-06T23:42:33Z. Linux Node is
absent: actual DOM controls passed on Windows, not in a live browser. No automatic
historical metrics reconstruction, engine/progs/config/threshold/badge change.

### Comparison-reader deployment: P524-526

Frozen game `4f5c47f` deployed tools-only on 2026-10-07 at 00:27:07 UTC.
Only the fixed `tools/census/recsim.py` runtime changed on the Pi and both
Windows installs. Use the Git-pinned installer, paired-reader and predecessor
hash guards, and retain its `recsim.py.pre-<sha12>` rollback copies. Destination
hashes match the commit; nine Linux stage suites and installed long/short,
malformed/unreadable/no-input/measured-zero controls pass. The actual Pi caller
resolves the installed reader and a real pair is measured read-only. Protected
table counts and binary/progs/config/app/process state remain unchanged;
health stays OK with 12 lobbies. No reload or lobby restart is needed.

A private post-swap probe called a nonexistent locator after the tool was
already installed. Recheck hashes and the original backup, repair the probe to
use the actual shared locator with an isolated app HOME/DB, and finish missing
gates only: never recopy a correct destination or overwrite the first backup.
Isolated secretless app logs are not live heartbeat failures. Historical rows
are not reclassified; this does not establish pair coverage or calibration.


### Cleanup copies without crossing into live content

Measured Windows/NanoPi cleanup pitfalls (2026-10-08), not a product patch:

- **Windows `DirEntry.stat()` is not canonical identity.** Its cached results
  can have zero `st_dev`, `st_ino` and `st_nlink` while `Path.lstat()` returns
  the real values. Use no-follow `lstat` for reparse-point, hardlink and
  before/after identity checks. A real junction control must prove rejection
  and that unlinking only the junction leaves a target sentinel intact.
- **POSIX unlink changes surviving hardlink aliases' ctime.** A strict guard
  can stop after deleting one alias even though the other name's bytes have
  not changed. Do not broadly ignore ctime: accept only an inode this exact
  transaction already unlinked, with identical device/inode, mode, size and
  mtime, plus a fresh hash matching the preserved archive. After a partial
  stop, rehash/replan the remaining entries; never blindly retry or force.
- Archive and verify every ignored artifact before removing a published-clean
  worktree. Preserve dirty/untracked files, unique history, player data and
  owner configs. Check locks, descendants and process executable/args/cwd.
  Use normal `git worktree remove`; retain branch/history recovery.
- For test overlays, archive links as inert metadata and delete via anchored
  directory descriptors with `O_NOFOLLOW`. Reject linked roots and every
  mount boundary. Acted controls need a directory link, a regular hardlink
  pair and a target sentinel; the sentinel must survive the actual removal.
- Compare live map/static-file metadata, config/progs/binary hashes, existing
  backup names and lobby PIDs before/after. Separate new live data from loss:
  directory timestamps can change when new files arrive while every existing
  file remains unchanged. Keep raw inventories, process args and recovery
  archives private; never publish them as verification output.


## Chat and `say` — the contract, and it changed in 342

Getting this wrong kills the restart keys silently, so it gets its own section.

- `say` does NOT arrive via `registercommand` (engine commands beat
  CSQC_ConsoleCommand). The engine offers it to the `CSQC_ChatSay(args, team)`
  globalfunction before sending (patch 341, `zqtp.c`).
- BARE `say` opens the draft; `say <text>` is DECLINED so CL_Say sends it
  (patch 342). `say_team` is declined outright (no teams here), and `/me`
  (`CL_Say`'s `extra`) never reaches the hook at all. Taking text back breaks
  `bind r "say !r"` / `!m` in `default.cfg` (and `defaultuser.cfg`) —
  i.e. the restart keys — and the `cfg/test` fixtures that drive runs with it
  (seven today: b26a, b48d, b57eclipse, b57stage, b58ab, b86a, b86b).
- THE MESSAGE MUST REACH THE SERVER AS ONE ARGUMENT: SV_ParseClientCommand reads
  the whole thing from `argv(1)` and splits on the first space itself. CL_Say
  wraps it in the one quote pair SV_Say strips (exactly one, `sv_user.c:4385`),
  so plain `say !s 2` keeps its number; `cmd say !s 2` arrives as two arguments
  and the number is LOST (stage 0, silently). Cfgs, fixtures and the menu
  self-test use plain `say`. Corollary: a `%S`-quoted `say` line ships a second
  quote pair and leaves visible quotes in everybody's chat.
- The DRAFT's own submit is the exception and must stay `cmd say`: `set
  cl_safetmp %S` then `cmd say $cl_safetmp` — the buffer's `;` split is
  quote-aware, expansion runs after the split, and `cmd` bypasses CL_Say so the
  hook cannot re-enter itself. The cost is that the draft cannot send `!s N`
  (the tail splits); `!r`/`!m` are unaffected.
- Key presses reach CSQC_InputEvent BEFORE their bind runs, so chat keys are
  intercepted by stealing the key whose `getkeybind()` is `messagemode`,
  `messagemode2` or `chat_say` (cl_chat.qc:533) — not by claiming the command.
  `toggleconsole` is the one key a live draft gives back (it abandons the draft).
- Hooking any engine command intercepts YOUR OWN callers. Audit cfgs, fixtures
  and internal submitters before hooking one.
- Harness handles (Patch 370): `chat_say <text>` opens the draft prefilled
  (bare `chat_say` is unchanged); `chat_rows` prints the last draw's wrapped
  rows, widths and drawn y (`^` doubled so the log keeps codes). The chatbox
  wraps with the engine's markup units (`Chat_CodeLen`), so a new markup form
  in COM_ParseFunString needs a line there too.
- SYSTEM CHAT LINES (Patch 371) are PRINT_CHAT spelled `^C word:^7 text\n`
  (`server:`, `finish:`, `board:`, `lobby:`, `vote:`): a `^` right after the
  colon means the engine can never read one as a player's `name: ` chat
  (zqtp.c:2288). Send to the others with `Lobby_SayOthers`, name players with
  `Lobby_ChatName`, pass player text through `Lobby_Clean`. The server log's
  copy reads `said> ...` (dprint, log_developer) -- on a listen server it shares
  the client's log, so grep chat lines by what follows the timestamp.
- A JOIN IS PER CONNECTION: the `*ann` userinfo star key survives changelevel
  and map_restart (ClientConnect runs again on both; parms would not survive
  map_restart). Your own finish line is client-side (cl_banner.qc Bn_ChatSay,
  `banner chat`), so a harness client needs `menu_restart` + `ui_close` or
  notmenu skips Banner_Frame and no line is ever said.

## Map clock and votes (Patch 372)

- The rotation's deadline, its state, the next map and any running vote go
  out as serverinfo (grammar: sh_defs.qc, VOTE_*), written only by sv_vote.qc
  Vote_Publish. A change a vote decides is always EXECUTED BY Lobby_Cycle
  (lobby_vt_force / lobby_vt_next): a changelevel issued from a client command
  runs before StartFrame clears lobby_cyc_moving, and the runs it interrupts
  would park as `server` instead of `rotate`.
- Harness handles: `vote fake clock|next|open|label|votec|off` overrides
  serverinfo on the client only (HUD_SK); `vote key <scan> <0|1>` runs the
  whole CSQC_InputEvent chain, so it proves handler ORDER; `vote status`
  (client) and `cmd vote` (server) print both sides.
- A test that lowers lobby_cycle must raise it again before a map change: on
  the next map a short period opens the end-of-map vote on its first frame.

## Linux build, test rig and release (Patches 386-389, 0.1.11)

- **BEFORE CUTTING ANYTHING: does the feature you are shipping READ A GENERATED
  FILE?** If so it has to be named in `$ShipGameFiles` (`release.ps1:192`), which
  is an allowlist and not a glob. `ftesurf/data/*` is gitignored, so such a file
  exists on the build box and nowhere else, and the feature ships compiled-in,
  working and invisible. 0.1.15 exists because 0.1.14 did exactly that with
  `data/mapdl.txt`. Full account under the map-download section above.
- BUILD: `pwsh -NoProfile -File tools\linux\build-linux.ps1 -Commit <engine sha>
  -ExpectSonames -OutName linux-build-<x>` builds in a Debian bullseye chroot
  inside WSL `Ubuntu-22.04` (made once by `tools/linux/chroot-setup.sh`), from a
  fresh clone, offline, from `tarballs.sha256`. `-Commit` defaults to ENGINE.txt's
  pin, which is the right answer for a release. Output `dist\<OutName>\` with
  BUILDINFO.txt; `gates.sh` G1-G10 must all PASS (libc/libm only, glibc <= 2.31,
  zstd in the plugin -- Momentum's VTF 7.6 -- versioned sonames, clean stamp).
  `makelibs` runs at -j1: its two-target rules race under -j. Takes ~90 s when the
  chroot and its clone are warm.
- A WINDOWS EXE'S STAMP IS BAKED INTO OBJECTS, AND THEY DO NOT REBUILD WHEN
  `SVN_VERSION` CHANGES. 0.1.12 shipped an exe carrying TWO stamps
  (`ga72183e6b` from a .rc object, `g2b685797b-dirty` from a later sv_user.c), so
  nothing could say which commit it was and gate L2 refused to publish a Linux
  drop beside it. To re-stamp: find the objects that still hold the old string
  (`grep -rl` over `engine/release/**/*.o`), delete them, `touch client/sys_win.c
  common/common.c server/sv_user.c`, and rebuild with
  `SVN_VERSION=git-<count>-<describe> SVN_DATE=2026-09-23` passed ON MAKE'S
  COMMAND LINE (build.ps1's `$env:` does not reach it). Then read the stamps back
  out of the binary -- do not trust the build having run.
- TWO MSYS2 BUILD TRAPS, both environment rather than code: `make` inherits
  `TMP=/tmp`, and Windows gcc then dies with `Cannot create temporary file in
  C:\WINDOWS\: Permission denied` -- pass `TMP="C:\msys64\tmp"
  TEMP="C:\msys64\tmp"`. And an agent bash's `/tmp` is
  `C:\Users\Lex\AppData\Local\Temp`, NOT `/c/msys64/tmp`, so a scratch file
  written by one is invisible to the other.
- Call `wsl.exe -d <distro> --exec ...` from PowerShell. Git Bash rewrites
  /mnt/c paths, and without `--exec` the login shell expands `$vars`.
- A Windows exe built from a `git worktree` carries NO revision stamp (the
  Makefile tests `-d .git`, a file in a worktree): set `$env:SVN_VERSION =
  git-<rev-list --count + 29>-<describe --long --always>` and `$env:SVN_DATE`
  before `build.ps1 -Engine -Full -FteRoot <worktree>`.
  SET THEM FOR THE MAIN CHECKOUT TOO WHEN CUTTING A RELEASE. The Makefile stamps
  with `git describe --dirty` run under msys2, which sees the CRLF working copy
  as modified and writes `-dirty` even when Windows `git status` is clean --
  release gate L2 then refuses the drop ("names no clean commit"). `$env:SVN_DATE`
  MUST HAVE NO SPACES (`%cs`, i.e. `2026-09-21`): it reaches CFLAGS unquoted, and
  `Sep 21 2026` makes the compiler treat `21` and `2026` as linker inputs.
- RELEASE: `release.ps1 -Bump patch -BuildNumber <n> -Linux dist\<drop>`.
  `-BuildNumber` is REQUIRED unless a `Build NN:` commit is inside the last 200
  (the script derives the number from a subject and hard-fails without it; the
  last one, `QC build 89` f4b5051, is 224 back as of Patch 441 -- re-measure with
  `git rev-list --count HEAD ^f4b5051` rather than trusting a number here, and
  note it was 219 when this line was written, not the 228 it claimed). The Linux drop and ftesurf64.exe must come from the same
  engine commit (gate L2); build.ps1 recompiles the progs from `src`, so copy the
  lobby-deployed .dat back in before releasing. `ENGINE.txt`'s pin block is a gate
  too -- bump `commit`, `patch` and `qcbuild` with the engine or the run stops
  there.
  - STEP 18 USED TO FAIL ON WINDOWS. The fix in 6aaeebb did NOT work and was
    never run: it passed `-LiteralPath` to scp, which is a PowerShell parameter
    name, and a native exe answers `scp: unknown option -- L` and exits 1 -- the
    same failure at the same point, after the same unre-runnable uploads. Fixed
    for real in Patch 441 (a bare path argument, the shape the loop above it
    already used), and that shape was run against the Pi rather than reasoned
    about. The original defect: `scp -r "$pageDir\*"`
    passes the literal `*`, so the page never went up and the run threw AFTER both
    archives were uploaded -- the documented unre-runnable state, hit again on
    0.1.13, whose page was therefore deployed by hand: `scp dist\site-<v>\<each
    file>` to the Pi's `ftesurf-site/.incoming/<v>/`, the three site scripts
    beside them, then `sh publish.sh <v>` there. Check
    https://proto.bar/ftesurf/version.json afterwards, and download both archives
    back and compare bytes/md5/sha256 against the receipt -- the script's own
    "origin: size and md5 match" is the uploader's word, not the reader's.
- ONLY THE LOBBY PORTS ARE FORWARDED. A one-off server on a spare port is
  reachable from the LAN address (192.168.1.102), not from 180.150.62.57.
- TEST RIG: WSL `Debian` is a runtime-only player machine (user `surf`;
  `tools/linux/rig-setup.sh`), driven by `rig-install.sh` / `rig-run.sh` /
  `rig-steam.sh` / `rig-sv.sh`. Case tests need ext4 (`/home/surf/fakesteam`,
  `rig-fakesteam.sh`): /mnt/c is case-insensitive, and so slow that a lobby join
  over it timed out. A cfg's own `log_name` wins and logs APPEND: read the tail.
- Linux engine facts: loose files fold case ONLY through the name hash
  (fs_cache); a stale hash or an FSLF_IGNOREPURE lookup (`exec`) is exact-case.
  Linux runs are UNRANKED during the beta (Patch 389: SV_ProfileBroken demotes a
  profile without IPH_RAW; delete those three lines to lift it). Patch 387's
  entry lists what Linux input evidence cannot see.

## Source live-water depth (Patch 541)

`$refractiondepth` must set both HASREFRACT and HASREFRACTDEPTH; a sampler
read returning zero did not prove the pass acted. The fixed-camera raw-depth
control distinguished an absent attachment from real scene depth. Depth
capture avoids the colour-only oblique projection: reconstruct from the actual
m_projection, not near/far assumptions. In mode 1 leave sampler slot 1 null so
adding depth at slot 2 does not accidentally request a planar reflection.

For cloned BSP material controls, copy the map's actual `dep <map> <addon>`
rows, not invented CSV rows. Missing dependencies made sky/brush controls
invalid. One launch per map gave stable hundreds-of-draws readback; chained
map loads took almost 30 seconds and could screenshot a loading frame despite
waitmap/waitms. Prove contents at the camera: a point under a wet-looking slab
can be solid. Neutral-normal, fog-range and no-fog controls must visibly act.
Source water is still an approximation; modes 0/3/4 remain distinct choices.

## Source water and material menu (Patch 523)

- `hl2_water` defaults to 3. Mode 4 is an opt-in capture-free approximation:
  animated normals, alpha blending, fog colour and baked-cubemap reflection.
  It has no depth sampler, live reflection or depth-correct above-water fog.
  Modes 1/2 still capture refraction; 2 also captures reflection. Do not call
  mode 1 capture-free, or claim GPU/portable FPS from local wall-frame timings.
- P543: shader reload must compare old/new sort after successful parsed VMT
  and shader-file paths too, not only generator fallback. Early `continue`
  skipped resort: cold flat water worked while a live Full -> Flat switch
  drew before the floor. Sampler-free flat colour avoids GLSLONLY's missing
  compatibility progless path. Water Bayer cells floor gl_FragCoord (pixel
  centres are .5); glass intentionally keeps its older path. Coverage knobs
  now have narrow renderer-owned shader policies, not a wider plugin flag mask.
  `r_refractreflect_scale` is cached into material portalfboscale: change plus
  `flushshaders` and prove actual capture dimensions before timing. A no-flush
  scale arm is inert and proves nothing about CPU versus GPU cost.
- Plugin_GetCvar masks CVAR_SHADERSYSTEM. P523 opted water alone into the
  renderer's shader-rebuild policy; P543 also opts in the two coverage knobs. Cvar_Get2 does not retrofit that flag onto an
  existing variable. Preserve default/early user value/archive flags and test
  both initialization orders rather than widening every plugin flag at once.
- Patch 528 gates the live 0..4 row on LOCAL extension
  `FTE_CSQC_HL2_WATER_BUDGET`: native live policy, programmable OpenGL and a
  loaded plugin with embedded budget source are required. Cvar existence/value
  cannot substitute. Older engines, missing/older plugins and unverified
  backends retain 0..3 with `*`. Unsupported archived 4 becomes 3 and queues
  `flushshaders`, because pre-CSQC BSP generation may already have cached 4.
  Refresh at initialization/menu command/renderer restart; preserve milk's
  target invalidation. Availability does not promise GPU compilation success.
  Native P523 without the new extension conservatively uses the legacy row.
- Compatibility gates use actual old/new EXEs and both mixed plugin pairs,
  not a fake "force old" cvar. Legacy cycles need the advertised rebuild;
  capable cycles do not. Test the saved result as well as the readback. A
  matching menu fixture does not replace full downloadable-product CSQC tests.
- Graphics material rows carry `*` when their generated shader does not update
  automatically. Glass 0 is Translucent, not Opaque. `retry` can reuse cached
  BSP data: it is not a promise that every map-time setting gets reread. Keep
  that distinction in status and footer; readback alone is not rendered action.
- Water gates must show actual camera/draw/index submission and loaded programs
  plus full/cheap live-capture positive controls. Production builds contain no
  diagnostic hooks. Test menu cycling through 4, an explicit isolated archive
  save and fresh-process restore, and early startup override. Use fresh log
  names and waitms, not frame-count waits. Test the full product CSQC too, not
  only a standalone menu fixture; the latter intentionally omits gameplay.
- Fresh engine worktrees lack ignored SDK headers/libraries. Copy the existing
  dependency bundle into the owned worktree before building. Compare warnings
  against an identically configured baseline; existing warnings are not new.
  Build the shader generator from a relative source path so its generated
  banner does not embed a private worktree path in public source. The generated
  `mat_vmt_progs.h` must agree with the GLSL included by plugins/hl2/Makefile.
- `tools/test_water_menu.py --engine <checkout>` checks source contracts, not
  rendering. `test/p523water.cfg` is an optional isolated runtime menu smoke.
  Depth fog/capture sharing, other menu rows, glass and particle coverage retain
  their own acting-control gates in BACKLOG; this water patch does not close them.

## Missing-asset art (Patch 534) -- 2026-10-07

- `R2D_Init` requests the diffuse fallback as `no_texture`, with replacement
  allowed. The standard high-res search finds `textures/no_texture.png`:
  no engine rebuild is needed. `gfx/env/missingtexture.png` is the author's
  source image; the alias must remain byte-identical. `gl_load24bit 1` loads
  it at 64x64; 0 plus vid_restart restores the engine's 16x16 fallback.
  Normal/gloss placeholders stay 4x4, not magenta checker maps.
- `models/missing_error.md3` is a standalone extruded Impact ERROR asset,
  not an installed automatic failed-model replacement. Its opaque faces are
  fullbright red, sides darker; four small additive outline rings work with
  bloom off. No font binary/Source model is redistributed. Regeneration uses
  `tools/make_error_model.py` with a locally licensed Impact font; only the
  generator needs fonttools/shapely/mapbox-earcut/numpy. Runtime needs the MD3,
  `scripts/missing_assets.shader` and `gfx/env/missing_error_palette.png`.
- A pass-level `rgbgen const` with `program default2d` rendered this GPU alias
  mesh WHITE even though the script parsed. Use baked palette UVs instead;
  do not grade shader parsing as red pixels. The red front/angle/off controls
  distinguish actual rendering; 0 off pixels vs 58653/53639 red pixels, bloom0.
  The final quantized mesh has no degenerate triangles; tiny ones removed by
  MD3's 1/64 coordinate quantization do not change the frontal pixels.
- This replaces ENGINE CHECKERS, not every missing Source texture path.
  A valid Source UnlitGeneric whose explicit pass map is absent can remain
  black: `T_GEN_SINGLEMAP` does not use the `T_GEN_DIFFUSE` fallback. A missing
  VMT and a found VMT with a missing base texture are different controls.
  Failed-model fallback must retain failed-load diagnostics and must NOT
  change Source collision. Both integration tasks remain in BACKLOG.
- `tools/test_missing_assets.py` checks MD3 bounds/offsets/triangles/materials,
  PNG CRC/resolution/palette/alias and explicit release entries. The release
  globs for models/scripts are nonrecursive, so the MD3 sits at their top level.
  Do not silently put it into a subdirectory and call a local render a ship pass.

## Source fire sheets: loading is not animation -- 2026-10-07

- Particle VTFs can have ONE image frame and still contain an animated sprite
  sheet. The resource tag is binary 0x10, not SHT: fire_particle_4 is 2048x128
  with five 16-frame sequences; fire_particle_2 has an 18-frame sequence plus
  single-frame aliases. Use authored UV rectangles and durations, not a guessed
  uniform square grid. Inspect the VTF version/header bounds before walking a
  resource directory: 7.1 has no 7.3 directory. Preserve/report sequence flags
  rather than guessing their byte layout from a third-party parser.
- `p_script.c` tcoords/atlas randomize a static UV cell at spawn. They do not
  step it as the particle ages. Patch 531 adds separate native texframe/texanim
  tables, but does not change those legacy commands or integrate the fire baker.
  The PCF translator currently emits neither a
  sheet table nor animation, so registering a SpriteCard material or successfully
  baking a PCF is not evidence that its flames animate. A fit-to-life prototype
  needs a frozen pose with two different UV frames, repeated effects-off pixels
  to bound background drift, and a real-time animation control.
- Source c_fire_smoke.cpp:Start selects env_fire_tiny/small/medium/large with
  optional _smoke. These effects can live in shared game PCFs, even when a map
  embeds no PCF at all. Dune combines env_fire with custom/shared PCF systems;
  Anubis combines env_fire with hundreds of warm ParticleSphere smoke stacks.
  Material/class identity matters: do not replace every yellow orb with fire.
- Bright SpriteCard addself/overbrightfactor is not the same as $additive or
  full-screen bloom. One UV-stepped additive pass can approximate a bright
  flame without a capture/blur/light pass, but does not reproduce Source's
  depth blend, frame cross-fade or children. Keep those limits explicit.
- Polygon quads can batch by material and avoid one model entity per sprite;
  that does not make them free. Bound nearby/visible sites and sprite count,
  use smaller/fewer distant quads and measure overdraw. Equal-count polygon
  glow vs flame timings do not compare against the installed native emitter.
  A Dune camera with missing/checker materials is a UV diagnostic only, NOT a
  valid full-map performance or visual acceptance baseline.

### Native stepping prerequisite (Patch 531)

- `texframe duration s1 t1 s2 t2` appends a finite normalized rectangle, up to
  256 rows, with positive durations. `texanim static/lifetime/loop/clamp [rate]`
  steps the existing native normal-sprite UV fields in the same material batch.
  Lifetime mode uses the actual randomized particle lifespan. No cross-fade,
  secondary channel, per-particle allocation, extra sample/capture/light pass.
  `FTE_PART_TEXANIM` means compiled scripted-backend syntax; callers must still
  select that backend. Real old/new clients render and return extension 0/1.
- The isolated colored atlas acts for point and trail particles, lifetime
  expiry, loop/clamp, legacy static UVs, source-reset surviving retint, set unload
  and renderer restarts. All 256 rows survive actual QC query/export/re-exec;
  257th/NaN/negative/bad-type/no-frame controls visibly reject. The QC query and
  export buffers are enlarged to 64 KiB; their old 8 KiB cuts long tables.
- Native particles are drawn/simulated from the world walk in r_surf.c.
  `VF_DRAWWORLD 0` produces black native-particle tests with a nonempty pool:
  that is not an animation failure or a passing off control. Keep world draw
  enabled and inspect actual colored pixels and active/free pool counts.
- Let particle precache mappings refresh after exec/redefinition/restart before
  emitting via cached CSQC handles; same-command-stream emission can miss.
  Existing particle export omits trail step spacing; a replayed trail can emit
  nothing. This prerequisite leaves that unrelated omission alone. Restore the
  authored step for an acting trail control instead of interpreting silence.
- Shared env_fire definitions were located in the explicitly mounted HL2 VPK's
  particles/fire_01.pcf. The installed shared fire_burning_character VTF is 7.6,
  2048x2048: primary sequences3..5, secondary0..2, authored timing/flags. Do not
  substitute Dune's flame for Anubis or confuse its separate smoke stacks with
  flame. Inventory resolution is not yet a production shared-library resolver.
- Native Dune/Anubis flame-only rigs act with repeated-off images identical,
  an explicitly capped pool128, nearby sites<=8/range512 and <=72 emissions/sec.
  They approximate size/forces/alpha/material and omit graph children. Dune's
  diagnostic camera still has missing/checker materials. Uncapped alternating
  local wall-frame observations are NOT GPU/whole-map/installed-path acceptance.
  No product emitter, generated assets, owner install or fleet changed. Keep
  BACKLOG's integration/budget/compatibility/ship-set gates open.

## The milk visualizer (Patch 467)

- `src/milk_sys.qc` (both VMs, like sui_sys.qc) is a MilkDrop-style feedback
  renderer on render targets: scene -> warp -> sprites -> bloom -> composite, one
  tick at a FIXED 60 Hz. `src/menu/m_milk.qc` owns the menu's raymarched space
  (four stations; changing screen flies the camera) and the VISUALS / MUSIC
  screens; `src/client/cl_milk.qc` the sky (`r_skybox milk`). Shaders are
  `ftesurf/glsl/milk_*.glsl`; `milk_common.h` is the `w_user[]` slot table and
  must stay in step with `Milk_Pack`. GL only -- `Milk_Supported()` turns it off on
  any other renderer (Vulkan's 2D render-target switch is an empty function).
- Harness: `+set milk_bootcheck 1 +exec test/p467milk.cfg` photographs all four
  stations and quits; `3` shoots one station twice (diff them: identical = frozen
  sim); `4` with `test/p467perf.cfg` prints frame rate with the space on, then off.
  `test/p467sky.cfg` (surf_rookie, setpos-aimed) for the sky, with the map's own
  sky as the control. Screenshots are JPEG: a 2256x1380 PNG blocks the main thread
  ~2 s, and the harness steps are timed.
- Render-target rules that cost time here: configure a target with the 4-arg
  `setproperty(VF_RT_DESTCOLOUR, ...)` before the first `drawpic` whose material
  names it; `[shader] name ... prog 0` in the log means the program is on the PASS,
  not missing; a 2D polygon with a GLSL material falls back to something ugly off GL
  (MM_Shade drew a black half-screen on Vulkan).
- THE WORLDS AND THE IN-WORLD PANELS (2026-09-30). `milk_world` picks the menu's
  space: `lattice` (`glsl/milk_scene.glsl`), `monolith` (`milk_monolith.glsl`, a
  brutalist void), `vessel` (`milk_vessel.glsl`, one `#S0..#S3` variant per
  station, swapped halfway through a flight), `fractal` (`milk_fractal.glsl`,
  likewise: two pseudo-Kleinian cathedrals, a Mandelbulb, a Menger tunnel) or
  `shuffle`. `milk_panels 1` draws
  MAIN / VISUALS / MUSIC into render targets `mm_ui0/1` that the world raymarches
  as a slab's face; `milk_present.glsl #PANELS` redraws them crisply over it,
  gated by the scene target's alpha (+1 slab A, -1 B), and `MM_MouseToUI` traces
  the cursor back through the camera `milk_ud` holds. At rest a panel is laid out
  face-on at one texel per pixel (`MM_PanelPlace`), so its text is the font's
  raster; the camera orbits the panel only while the cursor is off it. The slabs
  are intersected (`panTrace`), never marched: in the SDF they cost the lattice
  4 ms a frame on the N100.
- `milk_scenediv 2`: every world raymarches every other tick while the feedback
  runs every tick -- except `milk_quality 4` ("ultra", high's resolution) and the
  lattice at high, which raymarch every tick. The camera and panel slots in
  `w_user` are only repacked on a raymarch tick, because the present and the
  cursor trace must match the image that is on screen.
- Resolutions: the targets are `180 + 180 * quality` high (360 / 540 / 720, by
  aspect; `MM_Frame`), the scene target a per-world 50-100% of that
  (`milk_scenescale`), bloom at 1/2 and 1/4, and the present stretches `out` to
  the screen bilinearly (or FSR 1's output, below). The present is a quad
  `MM_CROP` bigger than the screen, hanging off every edge (`mm_quad`), rather than
  a crop inside the shader -- which had scaled even a screen-sized image by
  1/0.97 -- so an image the quad's own size (native, FSR's) lands texel for
  pixel; the panel maths (`MM_PanelPlace`, `MM_MouseToUI`) take its per-axis crop
  (`mm_cropx/y`). Only the panels are drawn at screen resolution (the `#PANELS`
  overlay). The raymarch is the cost. N100, monolith MAIN, a tick a
  frame: ~19 ms a raymarch at medium (511x313), ~50 at high (942x576), against
  ~3 ms a frame for everything else the milk does -- `+set milk_bcdiv 1` against
  `999` (a harness knob pinning the raymarch to every Nth tick), 2026-09-30.
- THE FRACTAL WORLD (2026-09-30). Each station turns about its resting camera
  (the bulb about itself), so the camera can rest for the panels while the
  fractal moves: MAIN and PLAY are Knighty's pseudo-Kleinian with two fold
  boxes, the camera at a box corner (19 and 15 m from any surface, from a
  Python port of the DE -- the corners were the roomiest spots in all seven
  boxes scanned), VIS a
  power-8 Mandelbulb lit from just behind its rim, MUSIC a Menger slab drifting
  down its tunnel with the hole edges on the spectrum. The hit tolerance is the
  pixel's footprint (`PIXA`, from `dFdy(tc)`); 100-131 fps at medium on the
  N100, in-world panels. Its poses in `MM_PoseW` are the shader's `ORG`s; each
  anchor is the camera plus 400 m along that station's `LIGHT`, so the trails
  and the shafts come from the light. It plays `ftesurf_void` on "auto".
- KICK STREAKS (`milk_streaks`: 0 off, 1 menu, 2 the sky too; VISUALS -> look).
  `Milk_WaveSpawn` throws a wave on each rise of `milk_hit` (a kick an arc,
  sometimes the waveform line; a snare a comet), `Milk_WavesDraw` draws each as
  ribbons INTO the fresh feedback frame after the owner's sprites, and
  `glsl/milk_wave.glsl` bends each line by `milk_spec`'s waveform row, levelled
  to the mix's RMS. Lattice 1, vessel 0.8, fractal 0.7, monolith none. They fly
  at `milk_wavedepth` (the menu: the anchor's distance x1.05 + 2.5 m) and are not
  drawn where a model is nearer: the scene's alpha is now 2 + the distance for a
  hit the world calls a model (`milk_alpha` in `milk_common.h`; the lattice's
  cubes, towers and orbs, the vessel's cells, plankton and eye, the fractal
  everywhere but the Menger tunnel), a panel's mask as before, else 0 -- read it
  through `milk_panelmask()`. The test is at draw time, so the echoes already in
  the trails stay where they were drawn. Harness: `milk_bcwaves <s>` throws one
  every s seconds whatever plays (both VMs), `milk_bcwavekind` pins the kind, and
  `milk_bootcheck 9` shoots six frames.
- LIGHT SHAFTS: `glsl/milk_shafts.glsl` blurs the scene's brightest light toward
  `M_FOCUS.xy` into `<p>_b3` at 1/4 size, only while `milk_shafts > 0` (the
  fractal); the comp adds it at `M_FOCUS.z`, which is the menu's shaft strength
  and the sky's landing ring.
- THE SPEED PAGE (VISUALS -> speed): `milk_res 1` renders at the present's quad
  (`MM_Overscan`: the screen plus an even margin), scene scale 1; `milk_fsr 1` runs FSR 1 (`glsl/milk_fsr.glsl`, EASU then RCAS)
  once a tick into `<p>_up`/`_up2`, sized past the present's crop so the present
  still takes one tap; `milk_checker 1` raymarches a half-width target
  (`#CHECKER`, parity in `M_EVENT.z`) that `glsl/milk_resolve.glsl` fills out
  from its neighbours and the last frame (`<p>_scp`); `milk_cone 1` runs the
  world's `#CONE` variant at 1/4 size (`glsl/milk_cone.h`) and the scene pass
  (`#CONED`) starts each ray where that says nothing can be. All menu-only and
  all off by default; the page prints what it renders and the frame rate.
  N100, medium, a raymarch every tick (`milk_bcdiv 1`), MAIN: monolith 35-38 fps
  -> checkerboard 57, coarse pass 36-38 (noise); fractal 58 -> 99, 69, both 110.
  Lattice at normal settings: 123 fps, FSR 38, native 21, native+checkerboard 29.
- `show_fps` over the milk menu is the menu's own (`MM_DrawFps`, drawn last in
  `m_draw`): the engine draws its counter first, under the menu's full-screen
  backdrop. Over a live game the engine's still shows.
- More harness: `milk_bootcheck 10` runs `milk_bcseq`'s '|'-separated commands
  at the station `milk_bcstation` names, bare, a shot after each -- a sweep for
  tuning a look. A command with ';' in it goes in an alias in a cfg exec'd
  first (a ';' on the command line splits the `+set`). `milk_bcvispage 1` opens
  VISUALS on the speed page in the tour. `p467milk.cfg` and `p467perf.cfg` pin
  the streaks and the speed page too -- a new setting is the owner's own in every
  harness run until it is pinned (a tour shot showed their "menu + sky").
- THE BEAT GATES (2026-09-30). `milk_beat` pulses on every engine onset, hats
  included (7/s on `ftesurf_drive`). The visuals answer `milk_kick` (a bass onset
  gated by the bass ratio above 1.3) and `milk_hit` (a kick, or a treble onset
  with the mids above 1.2): `M_AUDIOATT.w` is `milk_hit`, `M_EVENT.w` `milk_kick`,
  and the flash is `milk_hit`. `Milk_ReactCurve` maps the cvar (0/1/2) to
  0 / 0.6 / 1.0 -- "wild" is the old "normal". `python tools/p468react.py LOG`
  replays a `cfg/test/p468react.cfg` trace through the same gates (keep the two in
  step); the menu tour (`milk_bootcheck 1`) prints `big hits N in T s` from the
  live QC to check it against.
- `milk_grade` (VISUALS "Colour grade", `M_TIME.y`): `milk_grade()` in
  `milk_common.h`, after `aces()` -- the image cooled and a little desaturated,
  colours near a pure red, green or blue kept and pushed.
- The vessel's x-ray films: `gfx/env/xray1.jpg` / `xray2.jpg`, grayscale JPEGs
  (q90, from the red channel the shader reads), tracked and in the ship set; the
  source PNGs beside them stay git-ignored. PLAY hangs one behind the plankton, VISUALS
  mirrors the other in the cornea; without them the maps are `$blackimage`. The
  harness start line prints `films` (bit 1, bit 2) and the art tour
  (`milk_bootcheck 7`) ends with `r_imagelist`, which says whether they loaded.
- Sound: `python tools/mkmusic.py` writes every generated track to
  `ftesurf/music/` (dream -- still `mkmenumusic.py`, byte-identical -- plus
  monolith, vessel, canopy, void, drive) and the menu's effects to
  `ftesurf/sound/milk/`. All git-ignored and deterministic; menu music "auto"
  plays the world's own track. The menu plays effects only if `click.wav` exists.
- More harness modes (`MM_BootTick`): `4` measures the station `milk_bcstation`
  names; `5` the panels (a fake cursor via `milk_fakemouse`: pick at rest, orbit,
  pick again); `7` every station bare -- run with `+set milk_panels 0` AFTER the
  exec, or the cfg's pin wins; `8` a dive into `milk_bcworld`. The harness cfgs
  now pin `milk_panels 1`, `milk_sfx 1` and `s_inactive 1`.
- The engine half: `snd_getvis` / `snd_visimage` analyse the software mix, and
  `snd_fx_lowpass` is the menu's "muffle the game". OpenAL output bypasses the
  mixer entirely, so there is nothing to analyse there.

## Pitfalls discovered the hard way

- **Native .inc scope is load-bearing:** ui_imgui/input.inc is included INSIDE
  FteImGui. Third-party and standard headers must stay at global scope in the
  parent .cpp; otherwise it declares nested FteImGui::ImGui/std and breaks the
  real compiler. P600's first local frozen gate caught a late include cleanup;
  new-location LSP errors were real, not the earlier missing-database cache.
  Restore global includes and repeat host/frozen/runtime gates BEFORE publication.
- **P601 native models are immutable revisioned snapshots, not array offsets:**
  Stage 0..count-1 inside the frontend draw bracket and commit before Draw.
  Malformed/incomplete/duplicate rows poison the transaction; only a complete
  counted copy publishes. Stable widget/row IDs and current revision govern
  actions, not label hashes or list indices. Replacement resets BOTH queued/held
  input and unpolled actions and revokes successful-draw authority until redraw.
  Literal ##/### labels must render as plain text rather than alter ImGui IDs.
  Checkbox updates are QC-owned new revisions, not mutations of copied values.
  Owner generation alone does not prove snapshot freshness. Keep implementation
  includes free of third-party headers inside namespaces (P600 scope failure).
  Synthetic diagnostic events are not real-device/panel acceptance. Contract and
  acting reorder/delete/held/queued/unpolled controls: tools/p601model.md.
- **P600 native input queues must be bounded across frames, not just per Draw:**
  ImGui trickles alternating edges across NewFrame. Resetting a per-frame event
  counter does not bound the residual queue. Limit BOTH host accepted events
  (128 per host frame, reopening cannot bypass) and actual ImGui queued events
  (128 across frames); reset must still act at the limit, clear queued/held
  keys/mouse/text and abandon active widgets/actions. The acting backlog control
  proves residual edges, repeated refill refusal and reset reclamation. Host
  failure closes once; polling is draw-bracket/success/VM/generation gated and
  capped at 16. No native command/bind/scancode interception. Compact keys and
  Unicode scalars are separate; build ALL upstream/adapter units with
  IMGUI_USE_WCHAR32 so supplementary text survives as exact UTF-8. Default atlas
  glyph coverage is NOT non-Latin font acceptance. Static interactive gallery
  owners 103/204 are not a dynamic model protocol: owner generation cannot stand
  in for snapshot/row generations. Synthetic QC events do not establish physical
  device routing, cursor ownership or movement-minus/modifier/real-panel safety.
  Exact scope, controls and remaining gates: tools/p600input.md. Probe namespace
  p599/P599 is retained solely for preregistered rig continuity; concurrent
  verifier P599 remains intact. No production panel/progs/Pi/Build/default change.

- **P598 minimal ImGui is a diagnostic prerequisite, not migrated UI:** optional
  pinned 1.91.9b plugin exports only NativeUI/1 service + shutdown/status; separate
  MQC/CSQC contexts/atlases, no implicit ini/log files, no Tick/Menu/Sbar drawing.
  Actual ImGui text/rounded control/1000-row clipped table/tooltip and overlap
  markers pass 23 screenshots at two virtual scales, physically identical.
  Real-source adapter/host controls pass 107 assertions per 16/32-bit arm including
  >64K rollover, whole-data rejection and bounded splitting. Fixed scratch buffers
  expand triangles; this is NOT cost acceptance. Submit failure returns false but
  cannot undo previous successful batches; fallback must redraw covering content.
  No input/widget/model transport, actual-panel/default/Build/release change.
  Pinned vendor needs `vendor/* -text` to preserve SHA256 bytes in autocrlf clones;
  unmodified vendor uses -O1 for GCC 16 range diagnostics, adapter -O2, both -Werror.
  C++/pthread runtime DLL imports are eliminated by static plugin linkage. Exact
  evidence and final frozen/delivery gates: tools/p598imgui.md. Provisional native
  P595 collided with concurrent surfd P595-597; preserve those entries and the
  already-published historical patch-595 tag. Canonical native source/tag is P598;
  test command/cvar/log prefixes remain p595 for retained-rig continuity.
  Canonical frozen d5e828f03 / patch-598 embeds git-7125-patch-598-0-gd5e828f03;
  74 compiler warning occurrences / 49 distinct fingerprints match P594, zero
  new, QC zero warnings. Guarded dual native-only delivery and repeated actual
  installed-path galleries (46 shots) pass at 2026-10-08T14:20:11Z; four target
  hashes/rollback and all 38 protected progs/config/data/server/DLL groups match.
  First whole-data gate was HOLD because the scheduled public-map sweep ACTED
  at 14:07 UTC; task/writer witness retained. Re-register a fresh whole-data
  baseline and repeat; do NOT stop the owner's task, restore data or exclude
  changed files to pretend the original gate passed. No progs/Pi/server swap.
- **`build.ps1 -NoDeploy` previously did not exist:** PowerShell silently accepted
  the unknown switch in `$args`; QC wrote into the integration install and native
  deployment still copied to the second install. P598 now declares the switch,
  adds CmdletBinding unknown-argument refusal and rejects NoDeploy+Pi/Run. It
  compiles through owned same-src-directory manifests (only output line changed)
  into fresh rig directories, removes its temporary manifests and blocks native
  deployment. This fteqcc's -o switches to new-style parsing; absolute input paths
  in old-style manifests also failed. Both are retained failed controls, not a
  workaround to ship dirty source. The real -Engine -NoDeploy control proves 65
  install/rollback/progs/cfg byte/path witnesses unchanged and three zero-warning
  QC builds. Earlier ignored-switch native copies were hash-guard restored from
  retained rollback files; new optional DLLs were parked before proceeding.
  Frozen worktree versioning also needs actual SVN_VERSION/SVNREVISION make
  inputs (+29 count offset): automatic .git-directory checks miss .git files,
  and FTEBUILDNO/FTEBUILDVERSION are not consumed. Verify embedded binary bytes,
  not just a wrapper's printed stamp. The unstamped provisional build was held.

- **P594 inherited native clipping: validate AFTER physical conversion.** Final
  P593 review found inherited clipping was intersected after P589's validation.
  NaN/Inf and finite virtual-to-physical overflow must fail before callback/flush,
  release the opened owner once and return explicit QC fallback. New acting host
  controls fail 12 assertions on P593; corrected actual-core controls pass 170
  assertions plus 24 grader controls. They use FTE-equivalent NaN/Inf bit semantics,
  not libc finite assumptions. This is host robustness, not malformed-driver
  injection or a native-module sandbox. `tools/p594clip.md` records the falsifier;
  published P593 tag remains immutable. Published source/tag `bed572f50` /
  `patch-594`; frozen game source/test `9e820a7`, integration `8206480` only adds
  peer off-ramp tooling/docs (not shipped). Clean full build stamped
  `git-7118-patch-594-0-gbed572f50`: same 74 baseline warning fingerprints, zero new;
  QC zero warnings. Frozen galleries `p590-bridge-u16xorn0` / `p589-mesh-n418owc1`
  pass. Actual installed Windows executable paths ACT in `p590-bridge-qksc2vm_` /
  `-ek419z65`, zero failed, after guarded native-only swaps retaining P593 rollback;
  destination hashes and progs/config/data/server/DLL preservation verified
  2026-10-08T11:34:11Z. No second Pi swap; existing P593 payloads are byte-identical.
  The no-flush assertions concern the rejected Draw path; resource cleanup may
  independently flush for P589 texture lifetime. No fixture DLL, QC/progs, panel,
  input/model ABI, preference, release or Build-number change in this fix.

- **P593 native bridge prerequisite: explicit QC draw sites, not plugin overlay
  hooks.** `NativeUI/1` copies an exact service table; optional named MQC/CSQC
  status/open/draw/close builtins provide one owner per VM, non-reused float-exact
  handles, per-host-frame dispatch, physical/virtual dimensions and inherited
  physical clip. QC-before/native/QC-after flushing restores caller colour, flags
  and backend scissor. Explicit close, failed open/draw, VM teardown, plugin unload
  and renderer shutdown release owners; renderer cleanup precedes P589 textures.
  Draw outside the frontend callback, stale/fractional/foreign/duplicate handles,
  exhausted handle space and render targets fail closed to caller QC fallback.
  Open/Close allocate/release only; trusted callbacks may not retain frame pointers
  or reenter engine services. This is not a hostile native-module sandbox.
  `src/shared/sh_nativeui.qc` supplies nested optional-builtin guards in both progs;
  no real panel, input chain, preference, default or Build-number change.
  Final candidate `p590-bridge-z7lgogbi` passes five acting arms and 52 screenshots:
  P589 legacy baseline, absent service, two MQC/simple-CSQC virtual scales and full
  CSQC UpdateView. Actual-core host controls: 149 assertions; grader controls: 24.
  P589 regression `p589-mesh-4jpv7z06` passes; its 33 grader controls also pass.
  Isolated predecessor/subject full builds have identical 74 compiler warning
  message/count fingerprints, zero new; QC compiles are zero-warning. Initial
  path/SDK/API/fixture failures remain recorded in `tools/p590bridge.md`; after a
  renderer reset, reacquire the SAME owner before testing alternate-owner rejection
  or the fixture itself creates another valid owner. P590 fixture names are kept
  after forward-renumbering to the one product patch 593 (peers published 590-592).
  Published engine implementation/tag: `25ad9d56e` / `patch-593`; main's
  `452c8814a` merge adds only the peer P590-592 delivery record. Game feature
  `d3b7174` is published. Clean frozen engine/tag and game feature rebuild stamped
  `git-7115-patch-593-0-g25ad9d56e`, with the same 74 baseline warning fingerprints;
  frozen `p590-bridge-3nyqfybl` and `p589-mesh-hei0vtp6` pass. Guarded dual Windows
  native+CSQC+MQC delivery kept rollback; unchanged SSQC was not replaced. Actual
  installed executable paths ACT in `p590-bridge-hmrva9oz` / `-gvq91c1r`, zero failed,
  at 2026-10-08T11:00:43Z; configs/data/server/DLL digests remain unchanged. Pi progs
  swap from exact game feature kept `.prev`, zero players, 12 fresh lobbies; all
  12 advertise the exact new cached CSQC CRC/size, protected engine/config and
  rollback hashes match, health 12, verified 2026-10-08T10:54:38Z. No Pi engine,
  Windows server/DLL, config, reader, evidence, release or Build change. Two private
  finish-only Pi probes failed on quoting and decimal-vs-hex size parsing; source
  confirms *csprogssize is hex. No recopy/restart was used to finish those gates.
  Next: minimal ImGui command-list service; widget/model/input transport, real
  panels, non-GL/device-input acceptance and CPU/GPU budgets remain separate gates.

- **P589 native indexed-2D prerequisite (2026-10-08):** separate exact-size
  `2DMesh/1`, immutable raw RGBA8 and non-repeating 64-bit plugin-owned tokens.
  Cleanup on release/plugin close and BEFORE renderer shader/image teardown.
  Whole-batch validation precedes real bounded mesh submission; CPU physical
  triangle clipping interpolates UV/color without touching backend-dependent
  `BE_Scissor`, caller color or blend flags. Linear/clamped straight-alpha atlas,
  both windings. Never treat this as a hostile-pointer/thread sandbox: trusted
  main-thread plugins call Submit only in a 2D drawing callback, not Tick.
  Per-Submit limits are 16,384 vertices, 65,535 consumed indices, 128 commands;
  32 textures/32 MiB per plugin and 256/128 MiB globally. No per-frame heap copy.
  Engine `69b2c1bdb`, tag `patch-589`, clean full stamp
  `git-7109-patch-589-0-g69b2c1bdb`; client SHA256 starts `7d125dedb98d`.
  C/header tree equals initially verified `516a6a1f5`; only patch notes/peer
  documentation changed before the final published tagged full rebuild.
  Full client/server/four-plugin build has the same 74 compiler warning messages
  and counts as P581, zero new. Engine plugin/renderer TUs have only baseline
  tidy warnings; standalone fixture/header diagnostics lack engine context.
  `tools/p589mesh.py`/`.md`: `p589-mesh-xro1c2lq` passes acting P581/subject1/
  subject2/disabled/no-renderer arms, offsets/alpha/winding/clips/chunks/order,
  invalid-second-command no-partial draw, 25 invalid/seven lifetime/61 count
  budget assertions, foreign destroy+submit rejection, automatic 32-texture
  cleanup, restart and main-plugin reload stale rejection. Physical screenshots
  inspected; scale1/2/repeat/restart/reload galleries are exactly identical.
  33 grader tests pass. Older atlas, font scales1/2 (exact P581 pixel equality)
  and 28 dedicated/editor controls pass. Initial snprintf macro/link failure,
  triangle-edge and bilinear-transition grader sample mistakes retained; corrected
  positions rather than relaxing tolerance. Disabled console animation is not a
  mesh regression; require absent sentinel/gallery pixels, not whole-screen
  equality. Forward-renumbered after peers published P586 then P587/588;
  preserve their full text and history; no published tag was moved.
  No QC/ImGui/service/input bridge yet. Next: VM-local explicit MQC/CSQC draw-site
  dispatch, with actual QC-before/native/QC-after and inherited-clip controls.
  Native MenuEvent here is only a fixture surface, not a substitute UI bridge.
  Non-GL parity, byte/global-budget stress, device and CPU/GPU cost remain open.
  Clean game-ref proof: `C:/FTESurf-mesh-proof` at game
  `2cad73344ccab9e4addeb0e638f1c98bf620afce`, engine/tag as above. Frozen
  native artifact plus clean QC compile (zero warnings), five-arm mesh gallery
  (`p589-mesh-bcynr8m7`) and 33 grader tests pass; proof source remains clean.
  Guarded native-only dual swap verified 2026-10-08T09:09:48Z: client plus
  matching hl2/cod/box3d/ode DLLs in both Windows installs, no server-binary swap.
  All ten destination hashes match the frozen candidate; `.prev` and
  `rig/deploy-p589-20261008T090946Z` retain predecessor/older-prev bytes.
  BOTH installed-client COPIES repeat all mesh arms (`p589-mesh-_9isse8e`,
  `p589-mesh-20f_971_`), zero failed; post-test hashes and protected cfg/progs/
  reader/server bytes still match. No owner process stopped, settings edited,
  peer dirty source deployed, progs/config/reader/asset/server/Pi/release swap or
  Build bump. This is not a claim that the owner/fleet rendered an ImGui panel.
  Next workstream starts from the published refs: implement the explicit
  VM-owned QC dispatch/service bridge, preregister mixed QC/native clipping and
  fallback/action controls, then build the minimal ImGui command-list service.
  Budget measurement and real-panel migration remain gated after that gallery.

- **P570 physical font contract:** `Font_LoadFont` converts virtual ladder
  heights to pixels; P566's QC physical conversion alone did NOT establish a
  native bake. Engine `loadfont ... "<ladder> pixels=1"` opts into physical
  rungs and reload preserves them. `Font_NativeSlot` is lazy/separate: retain
  `Font_Set`/`ui_font_cur` as the legacy face for `Font_Px`, use the physical
  mirror only during draw, then restore `drawfont`. Do not shrink the legacy
  virtual ladders (their larger scaled menu/HUD bakes are still required).
  Engine selection uses actual physical bake heights, each axis uses its own
  ratio, and near-integer/unit float round-trips are repaired. Gallery at
  1280x720 and console scales 1/1.5/2 is pixel-identical; pre-patch 1 versus 2
  changes 30,764 pixels. Same-process/menu/renderer repeats must agree and the
  unbaked +0.75px arm must visibly act on every crop. `tools/font_quality.md`
  documents hashes/commands/limits. This does not rank Apple-like aesthetics,
  measure recurring CPU/GPU cost or implement ImGui.
  Fleet verification 2026-10-08T04:19:39Z and delivery checkpoint: source
  `ae80bca` (published through
  merge `efcfe0d` with peer tooling/docs only), engine `60dfdc102`/`patch-570`.
  Clean proof `C:/FTESurf-font-proof` builds all QC with zero warnings; native
  client stamp is `git-7076-patch-570-0-g60dfdc102`. Pi qwprogs is unchanged,
  new csprogs SHA starts `80f2a137`; remote hashes match and all 12 units are
  active. A live Pi client reaches connection/editor actions; its whole-panel
  A/A pixel floor fails on the live scene (classic 11902, modern 1528), while
  the isolated static-map arms pass. Do not relax that reader or report a live
  pixel-noise pass. Windows deployment stopped BEFORE any swap because the
  owner's running `C:/FTESurf/ftesurf64.exe` is locked; do not terminate it.
  Dual Windows deployment completed at 2026-10-08T05:28:54Z after the owner
  closed the game; no process was stopped. Guarded script
  `C:/FTESurf-font-proof/rig/deploy-p570.ps1` verified both installs against the
  clean proof's five artifact hashes and supplied matching font/mask assets.
  `.prev` plus `rig/deploy-p570-20261008T052851Z` retain rollback copies and
  per-file provenance. Both installed-client copies pass the gallery/reload/
  unbaked controls (primary scale 1, second scale 2); matched images differ by
  zero pixels. Each actual dedicated/editor arm passes all 28 checks in its
  disposable rig (`font-quality-ho5psde5`, `font-quality-36f16w1n`,
  `ui-modern-20261008-162943`, `ui-modern-20261008-163011`). The second
  executable is `C:/FTEQuake/fteqw64.exe`, not ftesurf64.exe. The deployment
  JSON's `rows.name` is the logical source artifact name; map its secondary
  `ftesurf64.exe` row to `fteqw64.exe` for a later destination recheck. All 18
  artifact/asset hashes still match after testing. No primary peer
  sources/configs were changed. Next: Stage B's minimal ImGui bridge, with
  cost/aesthetic/device acceptance still separate.
- **P581 atlas prerequisite (2026-10-08):** native engine `710087cb7` /
  `patch-581` repairs the returned memory-image handle, guards encoded input
  before decoding and validates positive/in-range/live shader IDs. Old IDs
  are reference-counted shader-table slots, NOT generation-safe capabilities;
  reacquire after UpdateVideo and balance every successful reference. Initial
  number 577 collided with concurrently published reader P577-580; corrected
  forward without rewriting published `51dfe46ef`/`patch-577` history. Primary
  `tools/p581atlas_claim.md` advertised only 581 until publication completed.
  Harness names/markers retain P577 for their pre-registered reproduction.
  `tools/p577atlas.py --engine <subject> --control <old-client>` compiles an
  owned C fixture with `-Werror`; control's data handle is 0 while memory/disk
  lookup pixels ACT, subject's returned handle matches those crops exactly.
  Replacement, renderer restart, temporary release/reload (visible pixels),
  seven invalid inputs and four invalid-ID query/draw/quad/unload arms pass;
  disabled-plugin arm rejects commands/no sentinel. Startup root autoload
  proves no-renderer rejection before graphics; engine logging is not ready,
  so the fixture flushes begin/end markers to the per-child absolute
  `P577_NONE_MARKER` file. It subsequently opens GL and exits normally.
  Initial `-dedicated` client reached rejection then faulted during untouched
  shutdown; retained, NOT accepted or repaired. Do not weaken exit checks.
  `test_p577atlas_unit.py`: 30 mutation controls. Client/server compiler arms
  retain exactly 2/5 baseline warnings, zero new. Standalone fixture/header
  clangd lacks its engine context; engine plugin TU has only baseline tidy
  warnings. Actual GCC build is the gate, not that standalone diagnostic.
  Build with MSYS2 ucrt64/usr bins explicitly on PATH: otherwise cc detection
  can silently choose empty ARCHLIBS/NO_FREETYPE. Compute native SVN_VERSION
  with the clean Windows-Git checkout BEFORE prepending MSYS paths (different
  autocrlf context can give a false dirty stamp), and use an annotated tag.
  Final clean full build is `git-7096-patch-581-0-g710087cb7`; `clangdb.py`
  regenerated the database. Atlas, fonts at scales 1/2, exact approved-P570
  font pixel equality and 28 dedicated/editor controls pass. Clean proof
  `C:/FTESurf-atlas-proof` at game `e172392` repeats zero-warning QC, atlas and
  all 28 editor checks; frozen native SHA256 starts `f0fe4319ac3b`. Guarded
  native-only dual swap verified at 2026-10-08T07:51:06Z, keeping `.prev` plus
  `rig/deploy-p581-20261008T075105Z`. Both installed-client COPIES repeat all
  atlas arms (`p577-atlas-bcioqy63`, `p577-atlas-ifyudd87`); post-test hashes and
  protected cfg/progs/reader bytes match. No owner process stop, progs/config/
  reader/asset/server/Pi/release swap. Indexed-2D/QC/ImGui work is NEXT, not
  accepted by this delivery.
- **Stage B existing-ABI preflight (2026-10-08):** no ImGui implementation
  yet. Disposable native fixture against engine `3abccb525` (docs-only delta
  from deployed `60dfdc102`) accepts exact 2D/Input/Cmd sizes, rejects shortened
  2D, draws a magenta MenuEvent sentinel and disk 2x2 RGBA control, including
  half-alpha blue/white, before/after `vid_restart`. Disabled-plugin arm
  rejects commands/no sentinel; subject reaches 100 then 310 rendered frames.
  Valid memory TGA returns 0 and draws nothing because
  `cl_plugin.inc:Plug_Draw_LoadImage` explicitly sets NULL for type 3; this
  historical defect is now repaired by P581 above. Same-name `LoadImage` after `LoadImageData` retrieves the
  uploaded texture, exactly matching the disk crop before/after restart.
  This proves upload acted, not the one-call returned-handle contract. Do not
  call the prerequisite probe a passed native atlas/ImGui gallery.
  Evidence `C:/FTESurf-font-proof/rig/ui-plugin-preflight`: `preflight.c`,
  `run.py`, `PREDICTIONS.md`, final `same-name-memory-control/results.json`.
  `python .../run.py` compiles with GCC `-Wall -Wextra -Werror` and asserts the
  acting controls plus this known failure; it uses one-shot output dirs.
  Initial startup `-width/-height` did not set capture dimensions, and
  `vid_width/vid_height` alone still maximized to 1920x1111. The corrected arm
  also sets `vid_winmaximize 0` early and asserts 640x480 physical/virtual
  dimensions. Do not sample virtual coordinates as physical. A shader-name
  lookup workaround produced no memory texture; not accepted. Existing 2D
  exposes quads only; header handle persistence is not established, and the
  backend `srect_t` units differ (merged.h Patch 208). Next is the atlas path,
  then a separate versioned indexed-2D ABI plus explicit QC submission and
  clipped mixed-native/QC controls, not a pretend wrapper over Sbar callbacks.
- **P566 SUI/font tests:** `ui_style 1` is the opt-in HUD-editor sample;
  `shared/sh_ui.qc` is ordered after fonts/SUI in both VMs. Native font means
  the final PHYSICAL height is a baked size: convert first, snap with the
  selected face's ladder, then convert back on both axes. Pixel-align origins.
  Layout/scale screenshots passing is not font-quality acceptance. The new
  tooltip must measure with its cached drawfont/glyph size; a console probe's
  default font is not the font that drew it. Wrap only on changed text/face/
  size/width, not every frame, and do not reset a valid hover merely because
  a screenshot/slow frame took >250ms. IE_FOCUS mouse and keyboard arguments
  are independent, with -1 meaning unchanged; retain both and reset tooltips
  before any handler can consume focus. `getkeydest` exists in MQC, not this
  CSQC defs/table: trying it in shared CSQC made git-6681 qcc crash silently;
  a reduced compile isolated that reference. DP registercvar archive is 32,
  not 1; MENU does not define the CSQC `CVAR_ARCHIVE` convenience macro.
  Fresh menu rigs also need the offline-consent/chosen-name prerequisites
  and the p498 fixture's fixed geometry, not the owner's archived state.
  `HUD_EditClose` explicitly saves when dirty: automatic-save guards alone
  are insufficient. The UI driver creates a marked disposable basedir, uses
  `map ui_modern.map` (omitting the extension searches for a .bsp), seeds its
  exact csprogs and terminates only its own handles. On published `21cfeea`,
  build.ps1 has no NoDeploy option and QC-only builds stay in the worktree;
  inspect the actual script before relying on a different shared version.


### Source water and visual controls (Patch 538)

- `CVAR_NOSET` does not defeat an early command-line `+set`: cvar registration
  preserves an already created value. The server's `pm_sourceversion` therefore
  derives from `PMSRC_VERSION` and is force-set immediately after registration.
  A startup override to 2 must still advertise and record 3; later console writes
  must be refused. Do not let prediction follow a different mover from the pin.
- Reject non-finite ramp pins before version-3 dispatch. `IS_NAN` is an exponent
  bit test (also rejects infinity); floating-point unordered tests can be folded
  under fast-math. Both the header and a valid two-integer `pm` restatement need
  a native REFUSE control. A malformed restatement which the parser ignores is
  not that control.
- `CL_Fog_f` blends for one second. Wait at least 1.5 seconds after fog changes
  before comparing settled screenshots. A 750ms restore screenshot is not an
  identity test. Underwater material fog must act with `r_waterwarp 0`; the warp
  flag is not an immersion test. `fg_new` includes CoD/Doom: use `MDLF_SOURCEBSP`
  when disabling Quake's orange plain-water blend for VBSP only.
- Swimming is mover version 3; v1/v2 pins and old-server prediction retain their
  original water drift. A dry recording repinned to 3 is only a dry regression
  control. A fresh real-recorder wet+jump run reproduced 136/136 arrivals and
  native PASS (144 rows /154 ticks) on Windows and aarch64; the old native engine
  REFUSEd that version. Cross-architecture dry gates also matched all seven
  `pm_dettest` rows on bhop_eazy and surf_ace.
- Automatic visual knobs do not exec sticky map overrides: hue -999 and fog
  distance/density -1 choose map defaults; explicit settings remain the user's.
  Source hue runs after LUTs, scene-only. Neutral/no-LUT maps bypass the pass.
  `surf_sidistic` selects 150 degrees, distance 2, max-opacity multiplier .5.
  There is no scripted water-lip jump and no submerged portal/stair/carrier
  collision runtime claim. Portal maps reuse the prior portal-aware slider.


- **An isolated renderer rig must also isolate the executable's plugin directory.**
  `-basedir <rig>` plus an original-install executable can still load that
  executable's old HL2 DLL. For a plugin-only falsifier, copy the unchanged exe
  and the subject DLL into the rig, launch that exe explicitly, record hashes,
  and prove the new behavior/cvar acted. When adapting an old harness, assert
  every source replacement matched: a silently missed exe-path replacement
  produced a clean run of the OLD floor in the 508 investigation. That failed
  arm was discarded, not counted as verification. Do not overwrite owner
  installs merely to make an isolated test load the intended plugin.

- **`volume 0` DOES NOT MUTE MUSIC.** Music plays at `musicvolume * mastervolume`
  (`snd_dma.c:3512`) and `volume` only scales the rest, so a harness that
  "mutes" with `volume 0` plays its music out loud -- Patch 467's did, with the
  laptop's owner in the room. And every volume cvar is applied BEFORE the
  snd_vis tap, so muting music also blinds the analysis. Use a whisper instead:
  `set musicvolume 0.02` (the analysis is level-normalised), and test WAVs at
  -40 dBFS (`tools/p467visprobe.py`).
- **`+lookup` DOES NOTHING IN A MINIMIZED HARNESS.** To aim the camera, use the
  mod's `cmd setpos <x> <y> <z> <pitch> <yaw> <roll>` (taints the run -- fine for
  pixels) with coordinates from `cmd viewpos`; `cfg/test/p467pos.cfg` prints a
  map's spawn that way.
- **LAUNCHING `ftesurf64.exe` DIRECTLY SKIPS `ftesurf.bat`'S fs_addons SEEDING.**
  On a fresh clone that means no Steam mounts at all -- "FTESurf: 0 maps" -- and
  a harness that loads a map finds nothing. Copy `fs_addons.default.txt` to
  `fs_addons.txt` once, as the .bat does.
- **A PLAYER'S RUNNING GAME LOCKS `ftesurf64.exe`.** A deploy fails with "being
  used by another process" while the owner has the game open. Never kill it:
  wait on that PID (`Wait-Process -Id <pid>`) and copy after it exits.
- **A 2256x1380 PNG SCREENSHOT BLOCKS THE MAIN THREAD ~2 s.** A timed harness then
  shoots frames drawn before its own last step took effect -- Patch 467's first
  tour looked like a frozen sim for exactly that reason. `scr_sshot_type jpg`
  writes in milliseconds.
- **FTEQCC'S PRECEDENCE IS NOT C'S FOR `||` AGAINST ARITHMETIC.**
  `scene = div <= 1 || t - floor(t / div) * div == 0;` was never true, so the
  monolith drew nothing and measured 142 fps. Parenthesise, or spell it out with
  an `if`, and never trust a frame rate you have not looked at a frame of.
  MEASURED 2026-10-03 (`fteqcc64 -Fwasm` on a probe): it is the ASSIGNMENT --
  `r = a || b;` compiles to `STORE_F a, r; OR_F a, b` (`(r = a) || b`), and
  `r = (a || b);` is one `OR_F`. Conditions parse as in C: `a == b || c != d`,
  `a && b - c < d`. And neither operator short-circuits (both sides evaluated).
  Patch 477's `busy = !rw_on || rw_ack || rw_cd;` was this; a reviewer found it.
- **ON THE N100, SHADER SIZE COSTS AS MUCH AS SHADER WORK.** The monolith with
  its object groups skipped by a runtime switch ran 40 fps; a build with those
  groups (and its material code) compiled out ran 72 -- most likely register
  pressure on every pixel. So measure a feature by compiling it out, not by
  branching round it; loop from a `ZERO` the compiler cannot see so map() is
  inlined once per loop (unrolled, the first compile took 12 s); and keep one
  call site for march and shade (the water reflection is a second pass of the
  same loop, not a second call).
- **A CELL-BOUNDARY CLAMP OF `edge + 0.1` MAKES RAYS CRAWL.** Domain-repeated
  objects clamp the step at the cell edge because a neighbour may be nearer -- but
  with a tiny margin, every ray grazing a cell boundary takes 0.1 m steps. Use
  the real clearance (object to cell edge) as the margin: the monolith's far
  walls were at the 90-step cap in a step-count heat map and well under it after,
  and the lattice's PLAY station went from 29 to 41 fps.
- **THE SCENE TARGET'S ALPHA IS NOT ONLY THE PANEL MASK.** Since the streaks
  hide behind models it is 2 + a distance on a model's hit; `abs(a)` read as a
  mask is 1 over every one of them. Every reader goes through `milk_panelmask()`
  (present, comp, shafts); a world that writes plain `mask * (1 - fog)` (the
  monolith) still reads right, it just hides no streaks.
- **A 2D POLYGON IS BACK-FACE CULLED.** `R_BeginPolygon(..., TRUE)` with a
  script material culls by winding, and a ribbon built along its direction of
  travel winds either way: every waveform line and half the comets were simply
  not drawn. `cull none` on the material (`milk_wave` in `scripts/milk.shader`).
- **A HEADER SHARED BY BOTH STAGES CANNOT USE `dFdx` OR `gl_FragCoord` BARE.**
  `milk_common.h` is compiled into the vertex shader too; the speed options'
  helpers sit under `#ifdef FRAGMENT_SHADER`, or every world's variant fails with
  "'dFdx' : function is not known" in a VERTEX shader.
- **DO NOT WRAP `build.ps1` IN COREUTILS `timeout`.** Under `timeout 280 pwsh
  ...` fteqcc failed on `sv_progs.src` with no output at all, three times; the
  same build bare passed.
- **`clampmap` DOES NOT OPEN A TEXTURE UNIT IN A PROGRAM PASS.** Only `map`
  goes through `Shaderpass_DefineMap`, which starts the next merged pass; a
  `clampmap` line overwrites the current one. The vessel's films as `clampmap`s
  replaced `mm_ui1` at unit 3 and left units 4-5 empty (black) -- with no warning,
  and the log still said `passes 6`. Use `map $clamp:<path>`.
- **NEVER PUT AUDIO IN A RATE THAT MULTIPLIES TIME.** The leaf cells' phase was
  `T * speed` with the mids in `speed`, so a 0.5 swing in the mids a minute in
  moved every chloroplast ~12 radians in one tick -- the "freakout". Audio may
  scale an amplitude or a brightness; a rate needs a phase accumulated in QC.
- **A MARCH THAT RUNS OUT OF STEPS IS NOT SKY.** The monolith's corridor drew
  its step-exhausted rays in the void's haze colour: a grey wedge at the far end
  of a tunnel bored through rock. `march()` now returns minus the distance
  reached, and a miss inside the corridor ends in its own dark.
- **QC `&&` DOES NOT SHORT-CIRCUIT, AND A MISSING `#0:` BUILTIN ABORTS THE WHOLE
  VM.** Patch 467's `if (milk_hasvis && snd_getvis(...))` called `snd_getvis` on an
  engine that lacked it: "Builtin 0:snd_getvis not implemented", menu.dat shut
  down, and the engine dropped to the stock Quake menu. Gate an optional builtin
  with `checkbuiltin` and NESTED ifs (`if (a) if (b(...))`), never `&&`.
- **`git add <paths> && git commit` COMMITS THE WHOLE INDEX, including what the
  peer staged before you started.** Staging your files does not unstage theirs.
  On 2026-09-28 commit 7a3d194, titled as a zone-mirror change, carried the
  peer's AGENTS.md, BACKLOG.md, lextest.md, m_main.qc and a two-file rename --
  6 of its 8 files were theirs. `git commit -- <paths>` is mandatory in this
  tree, and read `--stat` on the result before pushing. (The separate, harder
  case is a peer's edit INSIDE a file you are also editing, which a pathspec
  cannot catch; that one needs `git diff --cached`.)
- **`./src/build.ps1` from the Bash tool silently does nothing** -- no output,
  exit 0, no build. A measurement taken between two runs used a build that had
  never happened, reported the previous number, and read as "the change had no
  effect". Build through the PowerShell tool, and check `menu.dat`'s mtime if
  the result surprises you.
- **`build.ps1` writes its warnings with `Write-Host`, so `2>&1` into a
  variable does not capture them.** A filter counting lines matching /warning/
  over the captured output returned 0 while the build printed 2 real Q302s.
  This is CLAUDE.md's filter trap in a new costume: the tool's own
  `Done. N warnings` line is the count to trust, and it was correct both times.
- **The staleness gate is doing double duty as a cross-session guard.**
  `release.ps1` gate 1 scopes its dirty check to the SHIP SET, and `.qc` files
  are not in it -- only the `.dat` they build. So a peer's uncommitted
  `m_main.qc` does not trip gate 1; what stops you shipping it is gate 2
  noticing the source is newer than the progs. Do not rely on gate 1 to tell
  you whose work you are about to publish; read `git status` yourself.
- A DEPLOY'S PROVENANCE CHECK GOES STALE THE MOMENT YOU FINISH IT, because the
  other session commits into the same working tree and `-Pi` ships the TREE.
  On 2026-09-28 I ran `git log <deployed>..HEAD`, cleared all four commits, built
  and deployed -- and the peer landed a commit in the two minutes in between, so
  the progs that went to twelve public lobbies were built from a HEAD I had never
  inspected. It was harmless (BACKLOG.md, a test cfg and a .py -- no QC), and that
  was luck, not method. Re-read `git log` and `git status` AFTER the build and
  BEFORE the swap, or build from a `git worktree add <tmp> <sha>` at the exact
  commit you checked so the artifact cannot move under you. The deploy prints the
  progs hashes: they are only meaningful against a commit you can name.
  **AND IT IS NOT ONLY THE DEPLOY -- THE SAME RACE RUNS THROUGH `git push`,**
  which is how this bullet got written too narrowly and then bit again the same
  day. Later on 2026-09-28 the peer asked me to push a commit of theirs, I read
  `git show --stat` on it to confirm it held no client code, and then pushed a
  chain that by then also contained their phase C client commit -- landed at
  15:43:25, inside the same command as my own `git commit`. Seven files of QC and
  cfg went public without either of us choosing the moment. Verifying a payload
  and then acting on a LATER HEAD is one mistake with two exits; `git push
  <sha>:main` publishes exactly what you inspected, and a bare `HEAD` publishes
  whatever arrived while you were reading. On a PUBLIC repo that is not
  rollbackable by any means you are allowed to use -- never force-push -- so the
  inspect-then-act gap has to close before the push, not after.
- A CLIENT NEVER SEES AN AUTOBUNNY HOP TOUCH DOWN, so anything keyed on an
  `onground` EDGE silently does not fire during a bhop chain.
  `PMSrc_CheckJumpButton` clears onground on the jump tick itself
  (`pm_source.c`, see the comment at :2991), and the client only ever observes
  end-of-tick state, so a clean `pm_autobunny` chain has no frame with onground
  set at all. `hud_seq_hopbreak` was written to split the segment column per hop
  on exactly that edge and had never once done so; the column merged whole chains
  and the energy percentage read over 100% because the ceiling counted one jump
  for N. Two ticks on the ground is enough to make it visible, which is why an
  imperfect hop behaves and a good one does not. If you need "a hop happened",
  take it from the impulse (an upward step in `vel_z`, which gravity and
  AirAccelerate cannot produce) or from the energy, not from the flag.
- TO FIND ENERGY A PLAYER CANNOT HAVE EARNED, WALK A `.rec` TICK BY TICK against
  `cap^2/2g`. `E = z + |v|^2/2g` is EXACTLY conserved by the engine's half-step
  gravity (`PMSrc_StartGravity`/`FinishGravity`: dE = 0 per tick, algebraically),
  and AirMove flattens wishdir so AirAccelerate adds nothing vertical -- so in
  free air the ONLY thing that can move the energy is strafing, bounded by
  `pm_maxairspeed^2 / 2g` per tick. Any tick over that is a booster, a push, a
  teleport or a jump, and the recorder's flag word says which. 300 files gave
  17021 such ticks in 4419 air runs and separated three causes in one pass;
  `tools/p452col.py`'s `samples()` is the parser and `p449mark` has the flag
  bits. Far cheaper than reproducing any of it in the game.
- `pwsh`, never `powershell`.
- AN ENTITY BOX FROM THE MODELS LUMP IS WHERE A BRUSH CAN BE, NOT WHERE IT IS —
  wrong by a wide margin three times; `tools/census/README.md` has the cases. Grade
  the claim before quoting it: `gap == 0` counts a zero-width plane contact as an
  overlap and is nearly meaningless, positive overlap VOLUME is better, and
  CONTAINMENT (the pad's whole box inside the zone) is the only figure that
  survives — and even that does not prove you can touch the brush. A `cmd viewpos`
  read back after a `setpos`, or a `.rec` row from a real player, beats all three.
- **A COMPACTED SUMMARY OF A DOCUMENT IS NOT THE DOCUMENT, AND THE CLAIM MOST
  LIABLE TO BE WRONG IS "THIS SOURCE IS WRONG".** A session resumed from compaction
  asserted that two of `ENGINE_SECURITY.md`'s citations were bad (`cl_main.c:3725`,
  `cl_parse.c:4791`) and built a conclusion on it -- that a traced-only list with
  drifted line numbers is a list nobody can check. The file cites `sv_ccmds.c:3256`
  and `sv_ccmds.c:3891`, and BOTH ARE EXACT; the invented numbers were the summary's,
  not the file's. It reached a pushed public commit before anyone opened the file.
  Two rules follow: never assert a defect in a source you have not just read, and
  treat a citation carried through compaction as unverified until it is checked.
  Related and cheaper to remember: the same entry claimed a finding the file had
  ALREADY stated, so the honest claim was the measurement, not the discovery -- say
  which of the two you are making.
- A `file:line` CITATION DIES WHEN ANYTHING ABOVE IT GROWS, in its own file and in
  every file that cites it: one added comment block invalidated ~10 numbers here,
  two of them in sv_timer.qc. Cite QC by FUNCTION NAME; keep line numbers for
  `pm_source.c` and other engine files this repo never edits. Cite a measurement to
  a committed script (`tools/census/`), never to a scratch path that will not exist
  for the next reader. AND AN ENGINE LINE NUMBER IS NOT SAFE EITHER JUST BECAUSE WE
  DO NOT EDIT THAT FILE: Patch 455 cited `pm_source.c:4696` for the prestrafe
  ceiling and that line is a single `{` — the essay is at `4679-4698` and the
  binding statement at `5001`. Open the line before you cite it.
- WHICH DIAGNOSTIC PRINTS ROUND, because a rounded readout bounds the claim you may
  make from it and this tree has several. Audited 2026-09-27: 53 `%.0f` sites in
  `src/`, of which these print a speed-like value where the precision can mislead —
  `cl_hud.qc` `Strafe_EquivSpeed`'s `%.0fu/s`, `cl_scores.qc`'s `speed %.0f..%.0f`
  band, `cl_watch.qc`'s `replay colours` speed range, and `sv_entities.qc`'s
  `basevel: OnJump ... vz %.0f`. The one that cost something was a speed printed at
  `%.0f` beside the cap it was being compared against: "260 u/s is at or below the
  cap 260" reads as a boundary equality and means only `[259.5, 260.0]`. The real
  margin was 6.6 u/s, and the crossing speed varied 243.9 to ~260 between runs — so
  a fixed boundary was inferred from a rounded number twice. A dprint costs nothing
  at `%.3f`; use it wherever the number is about to be compared to a limit.
- Deleting save dirs behind a running server does NOT clear its in-memory list;
  it rescans on map change/lobby flip/restart. Delete-all is `sl_delall`.
- SAVE-LOCKS SINCE PATCH 428 (sv_saveloc.qc): 999 a player a map, in memalloc'd
  columns (qwprogs sits at ~40k of 65535 globals -- do not grow them back into
  arrays). A lobby block is fresh only for the guid it was scanned for
  (SL_Fresh); only the newest 24 lobby saves keep their run -- older ones are
  DEMOTED to a position at rest; `sl_delall` sweeps 2 rows a server frame;
  20 `sl_` commands a second. A hold needs a load of that save in the same
  frame at its spot, a zone move releases it, and SV_TimerFrame runs no zone
  tests under it. Each rule closed a clean-run path in review: `cfg/test/
  p428hold.cfg` is the arm, and the open older holes are under Patch 428's Known.
- Two clients writing the same `log_name` interleave confusingly.
- TIME QC WITH DEVELOPER LOGGING OFF. `developer 1` + `log_developer 1` writes a
  `qcfopen(...)` line per QC fopen: 999 small reads measured 4.8 s against
  0.24 s without. `+set pr_enable_profiling 1` on the server, then
  `profile_ssqc` (over rcon from the harness client) gives per-function times.
- `cmd viewpos` is answered BEFORE spawn (`setpos 0 0 0`), so it proves nothing
  about a join; the server log's `said> server: <name> joined` does.
- A leftover test process (`ftesurf64*.exe`, `fteqwsv64.exe`) holds
  `fteplug_hl2_x64.dll`, so build.ps1's deploy aborts part-way and `C:\FTEQuake`
  keeps a stale server. Check `Get-Process ftesurf*,fteqw*` before `-Engine`.
  A server still in its closing `waitms` also keeps the port, and the next run's
  client joins IT and is dropped when it quits: kill leftovers between runs.
- Sessions share test fixtures (surf_666 + `p360sf.zones.json`, `data/runs`,
  `data/saves`, `data/resume`). Tell the other live session before a run that
  moves them, park rather than delete, restore and `diff -r` afterwards. The
  same goes for `build.ps1`: it redeploys the progs a running harness loads.
- Two-process harnesses drift: over a five-minute run the clients' `waitms`
  timeline ran 5-9 s ahead of the server's. Leave windows of 5 s or more
  between a server `set` and the client action that depends on it, and read the
  logs' timestamps rather than the cfg's arithmetic.
- A lobby process sees files another process wrote only after its own next map
  load (the name hash; `SV_MsAdopt` renames onto itself to force it). A
  cross-lobby test starts the second server after the first one's write.
- Agent shells: a Bash heredoc collapses `\\` to `\`, so an inline edit script
  that must match QC's literal `\n` fails or writes a real newline. Write such
  scripts with the file tool, or build the backslash with `chr(92)`. AND CHECK THE
  RESULT: `chr(92)+'n'` inside a `python -c "…"` string lands in the file as the
  literal text `' + NL + '`, which fteqcc rejects ("newline inside quote") or --
  worse -- compiles into a print that never fires. It cost four builds in one
  session. The reliable shape is a `python - <<'PYEOF'` heredoc that writes the
  file with `chr(92)` only where a real backslash-n is wanted, then `grep -n` the
  line back before building.
- Engine cvar `timeout` (default 65 s) is the dead-client drop; lobbies set 30.
- Unregistered cvar set by bare name in a cfg is "Unknown command" — `set` it.
- Engine `sv.active` is never assigned anywhere — every `if (sv.active)` is dead
  code; the live server test is `sv.state != ss_dead`.
- Engine `va()` is a small rotating buffer. Its pointer dies at the next `va()`
  anywhere, including inside FS calls: FS_Remove restarts the loader threads,
  whose names come from `va()`, and a download was saved as "loadworker_3". Copy
  with `Q_snprintfz` before holding it across a call. Also:
  `CL_CheckOrEnqueDownloadFile` returns FALSE when it STARTS a download.
- The QuakeWorld join is `SV_New_f`; `SVNQ_New_f` (NQPROT) is NetQuake's, and
  an edit there does nothing for FTESurf clients.
- THE PI TALKS UTC AND `git log` TALKS LOCAL (+10). Comparing a Pi file's mtime
  against a commit date silently misreads which build is live — it cost a fleet
  record that understated the fleet by nine patches. Pin a deploy with
  `TZ=UTC git log --date=iso-local`, and remember the Pi keeps no receipt: the
  DEPLOYED notes in ENGINE_PATCHES.md and the `.prev`/`.preNNN` files are the
  only record, so write one after every `-Pi`.
- Off the home LAN, 192.168.1.102 is dead but `proto@180.150.62.57` answers, and
  `build.ps1 -Pi -PiHost proto@180.150.62.57` deploys fine (its lobbies.json
  probe reaches :8084 too). Only the 12 lobby ports are forwarded, so a
  hand-started test server on another port is unreachable from outside — run
  that arm locally and say so in the entry.
- A player's guid is the `qkey` in the install ROOT, so two clients from one
  install are ONE player to the server. For a second player run the same exe
  with `-homedir <dir>` holding its own random `qkey` (FS_ROOT reads it there;
  its logs land in `<dir>/ftesurf/logs`) -- `p428slota/b`. Read both guids out
  of the server log as the control before believing the result.
- fteqcc: `arr[i]_x` does not compile ("Cannot cast from vector to float") —
  copy to a local vector first; sprintf takes ≤ 8 args (warns above, and DROPS
  the ninth silently); a lone `;` branch warns Q205 — use a comment-only block;
  big fixed arrays blow the globals/strings budget (4096 rows forced a 32-bit
  target — size them to the library). qwprogs is the 16-bit target and was at
  64547 of 65535 globals before Patch 428 moved the save columns into
  `memalloc` (`float *p = memalloc(n * sizeof(float))`, indexed as an array;
  the heap resets with the globals at every map load) -- check numglobals in
  the .dat header before adding an array.
- **GATING ONE LEG OF A COMMAND THAT RE-QUEUES TWO IS NOT GATING THE COMMAND.**
  `SV_MapFrom_f` ends in two `Cbuf_AddText(..., Cmd_ExecLevel)` calls, so both inherit
  the caller's restriction level: Patch 481's `fs_useaddons` gate refused the first,
  and the `map "@<argv(1)>/<argv(2)>"` beside it still ran. Measured on the unfixed
  build, a stuffed `mapfrom ftesurf bhop_eazy` printed `Blocking insecure command:
  fs_useaddons "ftesurf"` and then **`SpawnServer: bhop_eazy`** -- a remote server
  made the client HOST a map. It stayed open four patches because the refusal line in
  the log read as the command having been stopped. WHEN A HANDLER ENDS IN
  `Cbuf_AddText` OR `localcmd`, GATE THE HANDLER, not the things it queues: the
  queued commands inherit the level and each one is a separate decision somebody else
  made. Patch 485 gates `SV_MapFrom_f` itself. The corollary for an arm: a refusal
  line for command X is not evidence about command Y that X was about to run.
- **`Cmd_IsInsecure() && !Cmd_FromGamecode()` MEANS THE OPPOSITE OF WHAT IT READS.**
  Both are thresholds over ONE ordered value (`engine/common/cmd.h`): `RESTRICT_LOCAL`
  29 < `RESTRICT_INSECURE` 30 < `RESTRICT_SERVER` 31, `Cmd_IsInsecure()` is `>=30`,
  `Cmd_FromGamecode()` is `>=31`. The conjunction is therefore *exactly* level 30 --
  it blocks csprogs/menuqc and ADMITS a server's stufftext, which arrives at
  `RESTRICT_SERVER`. So the pair cannot separate "a remote server" from "ssqc", and
  the tree's policy is to refuse both (Patch 481's comment says so; its `fs_*` gates
  and `FS_RefuseInsecure` are plain `Cmd_IsInsecure()`). Cost an arm: a stuffed
  `fs_changegame 1` under that condition switched games and crashed the client with
  no `Blocking` line, while a strict gate beside it in the same run refused correctly.
  A local console/cfg caller is `RESTRICT_LOCAL` and is never insecure, so a strict
  gate costs the USER nothing -- it only costs QC. `grep` the QC before assuming that
  matters: `fs_changegame` has no caller in `src/`, and the engine's own mod menu
  uses `RESTRICT_LOCAL`.
- fteqcc parses `x = a && b` as `(x = a) && b`: assignment binds tighter than
  `&&` and `||` (measured: `t = !first && FALSE` gave 1). Wrap the whole
  right-hand side, `x = (a && b);`, as the tree mostly does. Still unwrapped in
  committed code, left for a decision because fixing them changes behaviour:
  `snapang` in trigger_teleport_touch (sv_entities.qc) and its mirror in
  TG_FireTeleport (cl_triggers.qc) -- the keep-angles flag is ignored on both
  sides; `probe`/`hit` in TG_ChainStart and Trig_ConsoleCommand (cl_triggers.qc);
  `lpd_active` in Portal_LoadForMap; `onpanel` in Ev_InputEvent; `vote_on` in
  Vote_Frame; `vbsp_retrigger` in SV_UpdateMovementServerInfo.
- **A QC INTEGER LITERAL IS A FLOAT UNLESS IT CARRIES AN `i` SUFFIX, AND AN `int`
  LOCAL ABSORBS ONE WITH NO WARNING.** Measured in both VMs (Patch 496): with
  `local int x`, `x = 2144999 * 1000 + 952` stores **2144999936** and
  `x = 2144999 * 1000i + 952i` stores **2144999952** -- the first promotes the
  product to float32, quantises it, and the assignment truncates back. So any
  integer arithmetic written with plain literals silently becomes float32
  arithmetic above 2^24, which is exactly the range an int was chosen for.
  Suffix every literal in an `int` expression (`1000i`, `0i`, `1i`), as
  `m_board.qc`'s ms split always did. THE ONLY THING THAT SAID ANYTHING was
  fteqcc's own **F324, `sprintf: %i requires int at arg N (got float)`** -- so
  `%i` in a sprintf is a type assertion worth making on purpose, and a QC file
  with int arithmetic should compile with 0 warnings rather than be read.
  Related and older: fteqcc takes NO exponent in a literal (`1e15` is `1` then
  the identifier `e15`, "bad suffix on number"), and `int` is a type while
  `double` is not ("`double` is not a type"), so an exact product has to be a
  compensated float32 pair rather than a wider scalar.
- Every QC GLOBAL is zeroed on every map load, `map_restart` (so `retry`)
  included. Anything that must identify state across one lives in a cvar or a
  file: a per-map rewind serial let a pre-retry save rewind "warm" across the
  counter restart (Patch 364 moved it to the `rec_serial` cvar).
- QC HAS NO FILE SCOPE, and fteqcc merges two same-named same-typed globals into
  ONE with no warning. That is the mechanism forward declarations rely on, and it
  is also a live hazard: build 48 added a `ui_rs_armed` in cl_results.qc that
  already existed in cl_board.qc, silently aliasing build 26's teleport guard,
  and BOTH features broke in opposite directions for several builds (see the
  essay at the declaration in cl_results.qc). `grep -rn "float  <name>" src/`
  before naming a new global.
- PARALLEL-ARRAY COLUMNS ARE A STANDING TRAP. cl_board.qc's `seq_*` column is
  TEN arrays (`kind gain de emax dur launch pct eend sub eref`) and the count in
  the file's own warning says SEVEN places move together: the SEQ_MAX scroll
  inside Seq_Push (cl_board.qc:2024) and Seq_Push's own row write (`Seq_Push` is
  at 1976), Seq_Mark, Seq_Unmark, Seq_Load, and the seq.txt pair
  Seq_Write/Seq_Read — PLUS the FOUR sites in cl_watch.qc that seven does not
  count: `Watch_SeqRow` (the replay CAPTURE into rec_wt_sq*), `Watch_SeqSave`,
  `Watch_SeqRestore` (the park pair, rec_wt_sv*) and `Watch_SeqApply`. That is
  exactly where `seq_eend` (build 65) and `seq_sub` (66) stayed stale for two
  builds — the park pair was fixed in 342 and the capture in 343. A new column
  needs BOTH rec_wt_ sets or a replay silently draws the run's last row on every
  line. `seq_mk_*` is a full ten-array MIRROR of the column (cl_board.qc:883-892)
  and moves with it.
  Miss one and the column draws happily with a single field a row out of step,
  which reads as a physics bug.
- Entity I/O's authoritative semantics live in `src/server/sv_entities.qc`
  (~7800 lines, heavily essayed): ED_ParseUnknownEpair (case-sensitive "On"
  prefix), SV_EntityIOBuild (five-field rows, ESC-or-comma), SV_FireOutput /
  SV_IODeliver (exact-then-case-insensitive lookup), SV_ApplyInput, SV_IOEnable,
  SV_TriggerIOTouch / SV_TriggerEndThink (edge tracking, 0.05 s end grace,
  once-retirement).
- Unimplemented server classes leave DORMANT wiring: `trigger_userinput` has no
  spawn function, so its 14 OnKeyPressed outputs on mom_training fire nowhere
  and its StartDisabled targets are dead server-side too. Before blaming client
  prediction for a "broken" map mechanism, grep sv_entities.qc for the class.
- Defining CSQC_Parse_Print routes EVERY svc_print into csprogs and the engine
  prints nothing: re-`print()` each level you do not handle or it vanishes from
  console and logs. Chat arrives pre-formatted by CL_PrintChat with console
  escapes (`\1`, `^[`, `^]`, `\player\N^`) — parse it into (slot, text), never
  blit it; the name comes back from the slot via getplayerkeyvalue.
- sui has ONE hit-test list and ONE input buffer per frame: sui_begin empties
  the list, sui_end clears the buffer, so a SECOND sui bracket in the same frame
  draws dead buttons. Clickable panels either share a bracket (Players_Panel
  draws inside Scores_Draw's) or refuse to coexist.
- sui_slidercontrol's THIRD component is a DIVISION COUNT, not a step size
  (`src/sui_sys.qc:1167` quantises by `rint(r*steps)/steps`): `[0, 255, 1]` is one
  division = the whole range, so every drag snaps to an endpoint.
  steps = stops − 1 (bytes: 255, off/trail/long: 2, binaries: 1).
- A second clearscene/renderscene during the 2D phase with VF_VIEWPORT +
  VF_DRAWWORLD 0 is a working subview (cl_avatar.qc's preview): park the stage
  outside every game frustum and emit its particles after the main renderscene,
  or the world view inherits them.
- Chain guards gate handlers: CL_InputChain offers Scores_InputEvent under
  `rec_sb_open || sc_held` — a handler written for a new state is dead code
  until the guard admits that state. Read the guard, not just the handler, when
  a key "does nothing".
- A PANEL WITH TWO WAYS IN NEEDS BOTH WAYS OUT TESTED. The board is held by
  `+showscores` and pinned by MOUSE2 — which is also `+jump`, so jumping while
  peeking pinned it by accident and the release did not clear the pin. When a
  state machine grows a second entry, walk every exit.
- WORK SPREAD PER PACKET IS NOT SPREAD. SV_ReadPackets drains the socket in one
  loop, so a batch in PlayerPostThink that costs about a packet interval runs
  back to back until done -- Patch 428's first delete-all sweep stalled the
  server as long as the one-call version, with no `took over a second` line.
  Spread server work from StartFrame, and measure it by a command answered
  mid-way, not by that warning.
- lobby.cfg sets `rcon_password ""`: a test server that execs it and needs rcon
  sets the password AFTER the exec (a `+set` loses; the log says `Bad rcon`).
- Build and verify (headless run + logs/screenshots, or Pi journal) before
  declaring any task complete.
- THE ENGINE'S FONT OUTLINE IS A BAKE, NOT A DRAW FLAG.  `outline=N` in loadfont's
  sizes string and `r_font_postprocess_outline` are read at slot definition for
  EVERY slot in the process -- they re-bake the console and menu fonts too -- so
  neither can be a HUD switch.  Patch 440 draws its ring instead (eight copies of
  the string one pixel out in each direction, under the body, in HUD_TextDraw,
  gated on `ui_font_cur == ui_font_mono`).  And ftefont is PREMULTIPLIED
  (`blendfunc gl_one gl_one_minus_src_alpha`, rgbgen vertex): the requested rgb
  reaches the framebuffer UNSCALED by the requested alpha, so an outline or
  shadow colour must be DARK -- a light grey at half alpha is a bright smear, not
  a shadow.  A second baked slot for one face doubles its cells in the four-plane
  glyph atlas every font in the process shares; a draw-side ring allocates none.
- A `.cfg` HAS NO BLOCK COMMENTS. The config parser knows `//` and nothing else,
  so every line inside a `/* ... */` goes to the command interpreter. Patch 462
  wrote its arm that way and the log filled with `Unknown command "AIR"`,
  `"because"`, `"pms_lockedmovevars"` — the first token of each prose line. That
  is noise until a line happens to BEGIN with a real cvar, at which point the
  comment silently sets it: two lines in that file opened `map,` and
  `hud_trainer_x/y` and were saved only by the punctuation making the token
  unmatchable. 1013 of the 1016 files in `cfg/test/` use `//` already; the three
  that did not are `b86b.cfg`, `tint02.cfg` (checked 2026-09-28 — 7 and 13 prose
  lines apiece, none of which can execute) and p462trn.cfg, now converted. Grade
  an arm's log for `Unknown command` as well as for its own verdict.
- A MOVER CVAR CANNOT BE SET FROM AN ARM WITHOUT `sv_cheats 1`, AND THE FAILURE
  IS SILENT. `sv_gravity`, `sv_airaccelerate`, `sv_maxspeed`, `pm_ticrate`,
  `sv_friction` and the rest are in `pms_lockedmovevars` under
  `pm_lockmovement 1`, and the lock cuts BOTH ways (`sv_phys.c:136` says so in
  the cvar's own help): every one is restored to the game's default AT MAP LOAD,
  and refused thereafter unless cheats are on. So a `set` above the `map` line is
  undone by the load, and a bare assignment below it is reverted inside
  `Cvar_Set` before any tick sees it. The only window is `map` -> `sv_cheats 1`
  -> the cvar. Read it back with a bare `cvar` line afterwards and treat a
  `(default)` suffix in the readback as a FAILED SET, not as cosmetic — that
  suffix is the whole diagnostic and it does not look like an error. Patch 462
  spent two arm cycles reading `"sv_gravity" is "800" (default)` as noise while
  every cut measured a body in free fall at `horizontal 0`.
  The two arms carrying `set sv_gravity 0` (`p440font.cfg:111`, `p457av.cfg:69`,
  both commented "a still camera") are NOT invalidated by this and were not
  corrected: neither sends any movement before its shots, and a grounded body
  with no input is equally still at 800 — their stillness never came from the
  line. Only an arm that needs gravity to actually CHANGE is affected.
- PIXEL-DIFF HARNESS RECIPE (`cfg/test/p440font.cfg`, `tools/p440font.py`): still
  the camera by sending no movement — the `sv_gravity 0` in that file is inert
  (see the bullet above) and a grounded body needs no help staying put; pick a
  map whose textures
  actually mount -- surf_kitsune's skyroom does not and a missing sky FLASHES
  between frames (the floor read 239133 changed pixels; surf_rookie's is exactly
  0); `con_notifytime 0`, because notify lines move AND, with notify on screen
  plus extra drawstring passes plus a busy HUD, unrelated glyphs tint to the
  console's ^7 white (BACKLOG, engine-side); park control regions off the sky
  (clouds move); a control region must not contain the feature's own widget (its
  chip has to change -- grade the panel's element rows, not the panel); and take
  the floor from a pair of shots at the SAME cvar ~0.7 s apart, grading regions
  against it, never the whole frame (the fps counter always moves).

### Similarity atomic peer flush and contention (P574-576, 2026-10-08)

Peer admission and observations share one short atomic flush after comparison;
source admission remains a separate pre-work checkpoint, not completion/reservation.
A real abort after the first insert must restore the old peer cursor AND discard
all new observations across reopen. All-failed admitted pairs still checkpoint,
without fake skips/zeros. File comparison must allow an independent writer to ACT.

Sweep explicitly owns the busy-handler slot for collection: --sims-lock-ms1000
(default) is per SQLite lock operation;0 is immediate/no wait, not disabled. Restore
previous numeric timeout before ordinary verification, including failure/interrupt.
Standalone unopted/dry-run waits remain unchanged. Python cannot retrieve/restore
an arbitrary native handler. This is not a total pass deadline or RSS/write cap.

Classify contention by actual SQLite BUSY/LOCKED primary result codes only. Stop
further source admission, preserve prior committed observations, and report fixed
coverage-not-measured availability; summary busy state has ALL counters unknown.
Python3.10 lacks these error-code attributes and retains generic failures;3.11/3.13
code-required controls ACT. Never infer result codes from exception prose.

The new Windows3.13 atomic test exposed that SQLite context managers COMMIT but
DO NOT CLOSE. Explicitly close owned reopened/concurrent writer fixture connections
before temp cleanup. The older untouched source fixture shows the same cleanup
failure on published baseline; do not repair unrelated tests to mask it. Windows
admin UDP/RCON failures still match baseline; Linux full tests pass after one
recorded unmodified rerun of the existing dynamic-board timestamp equality case.

Publication74dcca0 shipped ONLY simcheck.py/sweep.py via canonical -Only -NoReload;
installed Python3.11 passes15 unique new controls without skips. Additional WAL
writer/wrapper control proves short abstention, restoration/recovery and later
synthetic verification with prior wait. Explicit live mode=ro/DML-denial controls
leave cursor/sample history unchanged; original sims/receipts/verdicts/reviews rows
match the pre-copy backup via bounded SQL with ACTED changed/deleted-row fixtures.
Do not turn this into mutable board/replay preservation or live-contention proof.
Both destination hashes and health/auth checks pass; rollback files/mode600 DB
backup retained. No game/QC/engine/config/Windows artifact or owner-process restart.

### Bounded log, association and plot acquisition (P590-592, 2026-10-08)

Log tails size the opened handle, read only their byte window, and discard a
partial initial line from that buffer. Newline-free and rotated/growing files
must ACT in controls; output line limiting after an unsized read is not a bound.
Historical associations acquire cap+1 per direction (26), display 25 and expose
independent more flags. Their selected cumulative SQL allowance is opt-in only
on the request-owned connection. Exhaustion withholds both lists but preserves
the receipt; partial badges say 25+, never a manufactured exact total.
Plot max_bytes is an exact nonnegative integer. Every normal/drain read uses
remaining bytes, including zero/one/non-aligned boundaries. A budget-cut line
cannot become a sample. Exact-cap files conservatively show truncated without
an extra EOF probe; complete plots with allowance remaining retain semantics.

Three new real-file/DB/DOM suites pass six tests each. Combined selected controls
pass 25 with the following command from surfd/:

```sh
python -W error -m unittest test_admin_log_bounds test_admin_association_bounds test_recplot_budget test_admin_metric_bounds test_admin_similarity_budget
```

Node controls run locally with no skips; Linux lacks Node and skips two renderer
arms, not an independent DOM pass.
Existing receipt-fragment harnesses must include the actual association helper;
compare board evidence without its generated response timestamp t. These are
selected read/result/SQL-work bounds, not whole-request RSS/time/snapshot proof.

Clean baseline/final offline script comparison has zero new failures; the same
two legacy UDP admin failures remain. Reccheck: 306 checks, zero failures. Frozen
corpus: 269 recordings / 101 view files, still 170 faulting recordings, unchanged
manifest.
Independent native review inspected source/artifacts, did not rerun tests.
Frozen 2ea4035 shipped only eight selected surfd source/test files, after stage
gates, mode 600 DB backup and copy under sweep lock. All destination hashes match;
replacement worker acts on authenticated log/association/plot reads and health
reports 12 lobbies at 2026-10-08T10:16:14Z. Rollback copies retained. No game/QC,
engine/pin/tag/Build, verifier-tool, Windows artifact or owner-game restart.
Browser/readability acceptance remains in lextest.md; no live evidence collection.

### Authenticated observer fetch/work limits and dry schema (P586-588, 2026-10-08)

Stored journal/counts fields use cap+1 BLOB-prefix SQL projections, not TEXT substr:
NUL and multibyte payloads must retain a byte oversize sentinel. Strict UTF-8 and
existing typed/versioned validation preserve measured zero and legacy unavailable;
invalid snapshots do not trigger historical rereads/backfill. These are selected
result-field limits, not bounds on the entire review response, SQL scan or RSS.

The historical similarity panel owns only its fresh request connection's callback
slot. Existing ReadBudget supplies one million selected VM instructions over PRAGMA
and history reads. **P597 (2026-10-08)** also charges the initial sqlite_master probe
within that allowance; its former unbudgeted exception is now closed. An interrupted
probe says read_limit, not confirmed missing. Real initial-probe interruption and
handler teardown ACT in `surfd/test_admin_similarity_probe.py`.
ReadLimit withholds the entire optional panel (state read_limit), not partial pairs
or false empty history, while useful run review remains. Missing stays distinct;
other storage errors still error. Borrowed similarity_for calls default to no budget
and retain caller callbacks. Owner opt-in cannot restore an unknown foreign handler.
Actual related-pair sorting must ACT: unrelated rows can use indexes and prove no
exhaustion. Default recovery must retain a positive 80-opportunity control.

Only the similarity dry-run subsection is non-initializing: existence-aware scalar
counts/summary never create/ALTER sims or sim_cursor. Main/import general schema
setup still mutates. A real authorizer distinguishes absent, legacy and current
schemas; the actual normal collector must still initialize and store a comparison.
Python3.10 authorizer teardown uses an explicit allow callback in the new fixture.

Frozen b4f4d31: 60/60 explicit Linux programs; Windows59/60 with the same two UDP
assertions in byte-identical test_admin source reproduced on baseline56/57. Argument-
required momindex is excluded, not a pass. New3/4/4 tests are warning-clean; recorder
306/0, captured269REC/91VIEW hashes and full fault lists match (170 existing faulted
reports). Source/evidence review found no concrete blocker but did not rerun tests.
Windows actual Node DOM passes; Linux Node/conversion capability skips remain.

Canonical exact-commit -Only (repo-relative paths) shipped ONLY admin.py,
templates/admin_run.html and sweep.py, with NORMAL shipper tests, no skip/reload
flags. First preflight used wrong allowlist names and changed nothing; corrected
invocation used the shipper's actual NVMe staging. Master2479950 retained, new
worker/ready09:05:04UTC; all destination AND predecessor rollback blobs match.
Mode600 DB backup retained. Installed modules are bound to actual paths in isolated
HOME/DB:11cases, ten pass/one absent-Node skip; live authenticated detail200/anonymous
401 and read-only diagnostics ACT. Bounded SQLite EXCEPT proves original
sims/receipts/verdicts/reviews rows match backup, with exact/changed/deleted oracle
controls. Initial finish probes expected wrong summary state and streamed CRLF;
finish-only corrections completed, no recopy/reload. Final host09:11:25UTC healthOK,
12lobbies active. No live collection/reread, reader/engine/progs/Windows/config swap;
no mutable board/replay/cursor preservation, hard time/RSS, calibration or live-
browser acceptance claim. Shared peer trees are untouched.

### Similarity ownership and scalar diagnostics (P582-585, 2026-10-08)

Exact integer source/peer/pair limits reject negatives (SQLite LIMIT would mean
unlimited), booleans, fractional/string inputs and signed-64 overflow before
optional loading or queries. Zero does no loading/query work. CLI rejects before
main connects, not before surfd's existing import-time initialization.

Enabled collection/direct comparison require idle connections before schema/file
work or sweep handler-slot changes. Never commit/rollback unrelated caller DML to
make collection run. Source admission/schema writers reject active transactions;
read-only pending/summary and disabled calls preserve ownership. Real two-connection
controls prove pending DML stays invisible/rollbackable; an idle independent writer
ACTS during an 80-opportunity comparison. This is an embedded API fix, not a proved
cron-path leak. SQLite connection context managers commit/rollback but do NOT close;
main now explicitly closes its fresh connection on normal/dry/error/interrupt exits,
even when the caller retains the traceback. Borrowed step APIs remain usable.

Dry-run counts a capped eligible-ID subquery as one scalar, never replay payloads.
Share the pending predicate; rotating collection selection remains unchanged. Keep
one-million cap, print at least on equality, and retain whole-query unavailable plus
independent summary allowance. Wide-payload and real VM-interruption controls ACT;
cap-label branch is synthetic, not million-row performance or native RSS/scan/time
proof. No detector math, threshold, history, receipt, ranking or badge-gate change.

Frozen published705ce1b passed57/57 explicit Linux programs; Windows56/57 with the
same two UDP-admin failures reproduced on baseline. The argument-required momindex
integration rig is not a standalone pass. Initial Linux disk-floor failures came
from fixtures on the 4.8GB root filesystem; full unmodified rerun on NVMe passed.
Existing test_sweep fixture ResourceWarnings reproduce20/40/12lines in baseline;
new focused cases are warning-clean, not the entire suite. Recorder306/0;269REC and
91pairedVIEW full reports equal on captured bytes,170faulted reports unchanged.
Source/artifact reviewer did not re-execute or hash-attest Git; parent did. Waiting
for final artifacts exhausted its30min budget; clean/ref proof and same-native resume
completed review without fallback. Owned scratch was retained after failed rmdir.

Only installed simcheck.py/sweep.py shipped by canonical exact-commit -Only/-NoReload,
normal stage tests, rollback files and mode600 DB backup; no reader/progs/engine/
Windows/config swap or live collection. Installed synthetic HOME binds actual module
paths and reader, stores80opportunities, exercises all four seams. Protected bounded
SQL with exact/changed/deleted controls proves original sims/receipts/verdicts/reviews
rows match backup. Final UTC2026-10-08T08:06:26 health/auth gates pass. Mutable board/
replay/cursor preservation, complete scheduling and hard resource bounds unclaimed.
The shipper infers repo from PSScriptRoot; it has no -Repo parameter. Read its actual
parameters. Existing primary-Windows reader peer-ownership blocker remains untouched.

### Truthful historical observation follow-ups (P595-597, 2026-10-08)

Verdict history acquires201/displays200 with owner-only limit/more metadata;
partial summaries never call omitted history all-stale. Journal/counts typed
JSON projections reject duplicate decoded keys at every nesting level. Initial
similarity table existence now shares the owned cumulative SQL allowance with
PRAGMA/history; exhaustion is unknown/read_limit, not confirmed missing.
Actual predecessor behavior reds and source/fetch/DOM/SQLite greens are in
`tools/p595observers.md`; source review was read-only, not a deploy attestation.

Frozen38eb243 passes59Linux programs (includingrecorder); Windows57/58 with
only the same two admin UDP assertions reproduced on untouched4f066479.
New focused tests are warning-clean; full legacy fixtures are not. Node runs on
Windows, not the Pi. Installed-source complete isolated harness22tests/fourDOM
skips, authentic-worker API/anonymous401, worker replacement/health12, selected
history/public board and protected support/progs/config/reader bytes ACT.
Only admin.py/template shipped; no partially installed test-helper chain.

A live online backup can restart forever under heartbeat churn. The first
private attempt timed out BEFORE swaps and its partial file was retained/marked
incomplete; exact owned process only was stopped. Stable source read transaction
plus explicit90second progress deadline completes. `BEGIN` alone is deferred:
P599's first attempt still timed out before swaps; actually read sqlite_master
(or another safe table) before backup to establish the source snapshot. Its
corrected completed backup preceded the selected source copy. RELEASE it before fresh
preservation checks or the snapshot could conceal later writes. Keep mode600
completed backups and .prev files. This Pi kernel lacks task/<pid>/children;
portable parentage must prove worker replacement. Wrong probe-cookie name and
that unsupported interface were private procedure failures, not product bugs.
The interface failure restored exact predecessor files. An untouched legacy
counts test compared transient board t across a second: advancing-clock baseline
red/stable-clock green proves flake; freeze only isolated fixture clock, never
repair production to satisfy it. BACKLOG retains the site/falsifier. Final
verified UTC2026-10-08T13:59:52Z; human browser/calibration and hard whole-request
bounds remain unverified. Read actual surfd-deploy parameters, not guessed names.

### Similarity reliability batch (P577-580, 2026-10-08)

Optional reader budgets are configuration: invalid integer/type/read-size limits
reject before I/O, not as evidence skips. None and valid zero/exact bounds retain
behavior. Collector flush counts use insertion-local rowcount, not buffered results
or total_changes; same-key overlapping winners and trigger writes cannot fabricate
new additions. Admission still is not completion/reservation/exactly-once.

The canonical capsule requires integer version1 bounded-input/capture capabilities
and ACTED disposable80-row exact-capture and whole byte/move-limit abstention
controls before destination mutation. This is trusted-code smoke testing, not
sandbox/authenticity/hard resource proof. A collection pass uses one initially
resolved module; direct calls and later passes re-resolve their explicit tools path.
No process-global cache or atomic recording-content snapshot is implied.

Frozen952d586 reviewed without blockers and published. All52explicit Linux programs
pass across51first-run passes plus one retained unmodified dynamic-board timestamp
rerun; established skips remain. Windows51/52, unchanged admin's same2UDP assertions
reproduced on the byte-identical baseline. Recorder306/0;269REC with pairedVIEW,
combined170faulted reports: exact source manifests and reports equal baseline.

Pi reader installed07:00:37UTC and ONLY simcheck.py via canonical -Only -NoReload
-SkipTests (52program stage already completed). Hashes/rollback/mode600DB backup
verified;25installed cases including5inherited and isolated installed sweep wrapper
ACT. Read-only live DML-denial/read-budget controls and bounded exact/changed/deleted
SQL gates preserve original sims/receipts/verdicts/reviews rows vs pre-copy backup;
no mutable board/replay preservation or live collection claim. Final gates
07:02:31UTC, health/auth OK. Secondary Windows reader installed07:01:07UTC; exact
hash, rollback and3installed source controls pass. PRIMARY Windows deployment is
BLOCKED by tracked modified reader in the shared checkout: preserved unchanged,
not overwritten. No engine/QC/progs/config/release/Build or owner-process restart.

### Selected similarity SQL read budgets (P571-573, 2026-10-08)

Sweep opts into a pass-wide 1,000,000 SQLite VM instruction allowance through
`--sims-sql-steps`; zero disables collection. Source cursor/pending and peer cursor/
candidate/late-recheck queries share it. Dry-run summary has an independent fresh
allowance. Whole-query interruption means unknown/unavailable, never partial
selection, prefix aggregates, zero agreement or full coverage. A late recheck
must flush prior successful observations and checkpoint only admitted work.

`ReadBudget` is explicit CONNECTION-OWNER authority: Python SQLite cannot retrieve
and restore an unknown existing progress callback. Use only on the owner's otherwise
unused slot; no-budget APIs preserve caller callbacks. Guard execution AND fetching,
close cursors and clear callbacks before file comparison/checkpoints/writes, including
ordinary SQL errors. Reserve a final callback quantum per statement to cover residual
instructions conservatively; small queries may abstain before the actual cap. This
is selected VM work, not lock waits, schema/writes, native/UDF cost, wall time, RSS,
fairness, concurrent reservations or completion. Actual expensive SQL plus positive
80-opportunity controls are required; mocked budget depletion alone is insufficient.

The exact publication passed 43 explicit Linux programs and 15 installed SQL cases
plus an actual installed sweep-wrapper comparison. Windows admin has the same two
UDP/RCON failures on the untouched baseline; do not repair unrelated code. Operator
import audits needing external input arguments are not standalone test programs.
Keep TMPDIR on NVMe for unchanged worker free-space floors; dynamic board `t` can
make the existing full-dict equality test flaky (see prior notes and BACKLOG).

Live board rows are mutable independently of deployment and outside the sweep lock.
An early all-table preservation gate saw board drift already in the pre-copy backup;
evidence/verifier/review/replay tables stayed exact. Do not assert a frozen board or
reinterpret that failure as six-table preservation. Never mirror a fleet-sized board
into two Python dictionaries for diffing: use bounded SQL/projections or explicitly
leave mutable-board preservation unverified. Bound lock waits and read work, retain
failed gates, and stop only the specifically proven owned diagnostic if necessary.

### Similarity retry admission controls (P563-565, 2026-10-08)

`sim_cursor` is additive INTERNAL admission state: one source position and an
independent peer position per source. Select greater eligible IDs first, then
wrap ascending. Only admitted work advances; reads never initialize or advance
state. Historical direct `compare_run` callers may have only `sims`, so create
cursor schema at the first actual checkpoint, not a read/disabled call.

Source checkpoints commit before file work; peer checkpoints commit once per
source call, including pair exceptions. Comparison/result-building faults leave
that pair unobserved and keep successful neighbors eligible for normal atomic
flush. A measured zero needs a positive comparison denominator; no fake skip or
zero is created for thrown pairs. Selection/checkpoint/storage failures are still
row failures; an ACTED mid-insert trigger proves observation rollback. Cursor
progress originally was not atomic with observations. P574 now commits peer progress
and observations together; source admission still precedes work. Neither reserves
work across competing collectors. Crashes/races can leave source admission ahead;
that is NOT completion, byte binding, exactly-once or full fleet-fairness proof.

Installed-module checks ran 55 cases including inherited fixtures, not 55 unique
coverage claims. Mock fault controls use denominator 1; separate installed bounded
reader checks ACT on real 80-opportunity fixtures: unavailable source rotation
survives connection restarts, a faulting first peer yields to later peers then
wraps, and a middle fault preserves successful neighbors. Additive live schema
init preserves sample/verdict rows; protected mode=ro checks preserve cursor state
as well. No live collection needed for temporary-fixture proof.

Windows RCON polling assertions in unchanged `test_admin.py` failed identically
in clean published-baseline and subject trees; source equality was captured, no
unrelated repair or Windows-pass claim. Frozen Linux admin and all 31 programs
pass. The already-recorded dynamic-board timestamp test failed once in an earlier
stage and passed one recorded rerun; the exact publication stage passes unmodified.
Both source reviews are read-only. Scoped `watchdog_diff` rejects an absolute
external worktree; pause/record the exact failure and bounded clean/ref/diff proof,
then explicitly distinguish parent attestation from reviewer independent source
inspection. No silent alternate runner or broader tooling fallback.

### Similarity eligibility and summary controls (P557-559, 2026-10-08)

`simcheck.pending()` means an eligible native pair remains unobserved, not that
its source has no stored observation. Stored pairs in either orientation must be
excluded BEFORE the peer LIMIT. Four sources with row/pair budgets one should
ACT six times, then go idle; a primary with 200 observed older peers must still
reach newer peers. This is eligibility, not fair retry or full-coverage proof.
The summary returns <=13 fixed aggregate rows in Python. Unbudgeted standalone
SQLite reads and working memory/cooperative elapsed completion remain unbounded;
P571-573 add optional owner-only selected-read VM budgeting, not a total RSS cap.

Frozen Linux suites passed at the inspected deployment commit; 23 focused
controls also passed with `sys.modules['simcheck']` bound to the INSTALLED file.
Real installed-reader controls completed six 80-opportunity pairs across budgeted
passes, then five new peers beyond a mixed-orientation 200-observation window.
Live metadata checks used mode=ro while holding the sweep lock; no real collection
or verdict/sample mutation was needed to prove the temporary fixtures ACTED.

An unchanged `test_admin_metrics` run failed its full public-board dict comparison.
That response includes dynamic `t` and can cross a wall-clock second; the failure
artifact did not retain the earlier timestamp separately. Same source bytes
had passed in the previous frozen stages and passed one recorded rerun. Keep the
failed artifact, source proof and rerun; do not repair unrelated product code or
claim that changing authentication/metrics changed the board. A deterministic
clock-boundary falsifier is recorded in BACKLOG.md.

### The public web surface (`/board/`) -- what may leave the process

- **A PUBLISHED `runs.player` WOULD BE A PUBLISHED IDENTITY.** That column is
  the client's guid, 32 hex derived from its qkey, and a client writes its own
  qkey -- so anyone holding a guid could file times as that player from a keyed
  server. `web_map`'s `del row["player"]` is load-bearing, not tidiness. The
  public id is `web_handle()` = sha256(guid)[:12]; 128 bits of guid does not
  come back out of 48 bits of digest. Never add a route that returns `player`.
- **The one exception is gated in one function.** `web_ext()` publishes an
  imported row's steamid64 -- which Momentum's own board publishes -- and
  returns None for every other tier whatever the value looks like. One
  predicate, one place, and test_web.py pins that a ranked row never carries it.
- **The run viewer's header is an ALLOWLIST (`WEB_HEAD_KEYS`).** A `.rec`
  carries `mapcrc`, `zonecrc`, `zonerule`, `nonce` and `pmpin`; those are the
  integrity surface and a blocklist ships whatever key is added next. The
  fixture .rec in test_web.py contains all of them on purpose, so the arm can
  fail. `evidence` rows, `community` runs and rejected runs are 404 there too.
  **IT IS THE SECOND OF TWO LISTS, and the first one filters silently.**
  `recplot.HEAD_KEYS` decides which header keys `parse()` returns at all, and an
  unlisted key yields no note and no counter (the `unknown records` note counts
  BODY records), so a key added to `WEB_HEAD_KEYS` alone publishes nothing and the
  symptom is a missing field rather than an error. `momdemo` needed both. Move them
  together.
- **`tier` on `/board/api/map` falls back, it does not 400.** The route shipped
  ignoring that parameter, so links carrying `tier=community` exist and
  test_web.py pins that they open ranked. A 400 there is a 400 on a bookmark.
- **`/board/shot/<name>` gets its safety from `clean_map`, not an allowlist.**
  Every other `/board/` file route has a fixed filename map; this one cannot
  (630 maps and growing), so the name goes through the SAME validator that
  decides what a map may be called on submit -- `..` refused, `_MAPNAME_OK`,
  `MAX_MAP_LEN` -- and the result is joined to one directory. Images are named
  for the MAP, not Momentum's uuid, so surfd needs no `mapmeta.txt`; the join
  happens once in `tools/mapshots_web.py`. A miss is a 404 with no placeholder
  and `board.js` loads through a detached `Image()` before showing the element,
  so the 110 maps without one lay out as though the hero was never there.
  test_web.py section 6c drives eight traversal shapes against a real file one
  directory up, WITH a control proving that file exists and is readable.
- **The nav tab is a function of the hash, not of the markup.** `aria-current`
  was written into board.html once and never moved, so Leaderboard stayed lit
  on top of a profile and Players never lit at all. `route()` owns it now; a
  new view must call `navTab()` or it inherits the previous view's highlight.
- **Two rules are spelled twice and must be changed twice**: the Quake colour
  strip (`board.js plain()` / `surfd.py web_plain()`), and the no-markup rule
  that test_board.py's private-word guard enforces by bare substring -- so a
  COMMENT containing `innerHTML` or `reason` fails the build. Both happened.
- **A missing map-difficulty catalogue reads as UNKNOWN, never as zero.**
  `map_tiers()` returns None when `momtracks.tsv` is absent and the page says
  tiers are unavailable. "0 of 64 tier-1 maps" for a box with no catalogue is a
  lie about a player, not a low score.
- **Ranking a profile is not ranking a board.** Two obvious orderings both put
  nonsense on top of a real profile: by placing it led with #1 of 1 (that
  profile has 35 such boards and 0 contested firsts), by board size it led with
  #501 of 501. It orders by `of - rk`, people beaten. Likewise `wr` counts
  first places and `wrc` counts the contested ones; the page leads with `wrc`.

### The ship set is an allowlist, and three things it never named -- 2026-09-28

**IF THE GAME NAMES A FILE, SOMETHING IN `$ShipGlobs` OR `$ShipGameFiles` HAS
TO NAME IT TOO, AND NOTHING CHECKS THAT.** Three separate "it's broken"
reports in one session were one cause: content referenced by a string literal
in QC that no ship-set line carried, so the code was correct and the archive
was empty.

| Referenced from | Missing for | Presented as |
|---|---|---|
| `Zone_LoadForMap`, `maps/zones/local/<map>.json` | every release to 0.1.17 | "this map has no zone file, so it has no legs and no times" on all 589 zoned maps |
| `cl_players.qc:403`, `gfx/thumbnails/speaking_off` | every release ever | an error texture beside EVERY player's name, permanently |
| `ui_bgprobe`, `gfx/mapshots/<uuid>-<size>.jpg` | every release ever (1.1 GB, never shippable) | a full-screen error texture behind the create panel |

**WHY IT IS INVISIBLE HERE AND FATAL THERE:** the build box has all of it, so
no amount of local testing reproduces any of the three. The only honest check
is against the ARCHIVE -- download the published file and list it, which is
also how each of these was confirmed fixed. `release.ps1` verifies the archive
matches the STAGE, and the stage matches the allowlist; nothing verifies the
allowlist matches what the code asks for.

A gate exists now: `python tools/shipguard.py` (2026-10-05) sweeps the QC for
literal asset paths and asserts each resolves in the ship set, exit 1 on an
unexplained miss. It PARSES `$ShipRootFiles`/`$ShipGameFiles`/`$ShipGlobs` out of
release.ps1 rather than copying them, because a copy drifts and then the gate grades
a ship set nobody ships. `--mutate N` hides the Nth glob and asserts a MISS appears
-- run it, because a gate nobody has watched fire is not a gate. TWO THINGS IT
TAUGHT, both of which read as a clean pass and both now in its docstring: a PREFIX
deny key swallows its own subtree (`maps/` excused `maps/zones/local/`, the largest
of the three faults above), and **`fopen` IS A LOAD WHEN THE MODE IS `FILE_READ`,
NOT A PROBE** -- classing it as a probe hid `data/mapdl.txt` entirely, i.e. the
0.1.15 fault passed clean. A read whose failure is silent is the worst thing to call
optional. It reaches 9 of the 13 globs (a 14th since, #13 `gfx/env` `xray*.jpg`, is
reached by m_milk.qc's bind literal); the other four (`cfg`, `glsl`, `scripts`,
`gfx/env`) are ENGINE-CONVENTION -- `r_skybox milk` builds `gfx/env/milk.png`, a
shader's `prog milk_scene` builds the glsl filename -- so no literal sweep of
anything we author can see them, and a clean run means "no literal path in src/ is
missing", not "the archive is complete". **WIRED 2026-10-05: `release.ps1` gate 4**, in the Gates
step -- before staging and packing, so ONE call site covers the Windows and the Linux drop, which
share `$ShipGlobs`. It has no override (gates 1-3 each have one), it hard-Fails if the tool or
`python` is missing because a gate that cannot run must not read as a pass, and it echoes the tool's
own stdout into the release log so a run records what it saw and not only that it passed. Its
falsifier was run rather than reasoned about: deleting `'ftesurf/data/mapdl.txt'` from
`$ShipGameFiles` -- 0.1.14's actual fault -- made `-Bump patch -BuildNumber 89 -DryRun` stop at
`MISS data/mapdl.txt src/menu/m_main.qc:2117` / `FAILED: 1 literal asset path(s)` with no `[5] Stage`
step at all; restored, the same command ran all eleven steps to exit 0 with zero warnings. (That run
needed `-AllowDirty -AllowStale` to get past gates 1 and 2, because a concurrent session had
`ftesurf/cfg/default.cfg` modified and its QC newer than the installed .dat -- gate 4 has neither.)

**AND A MISS IS NOT A NO-OP.** `drawpic` substitutes
`R2D_SafeCachePic("no_texture")` and draws it (`pr_menu.c:622-632`), so a
missing pic is a visible error texture rather than nothing. `drawsubpic`
(`:688-712`) does not, and `precache_pic` (`:820-861`) never draws at all --
with flag 512 it returns `""` when an image will not load, which is an
existence test that does not go through `fopen`. Three builtins, three
behaviours; a comment that claimed `drawpic` no-ops on a miss is what kept the
blind fallback in `ui_map_backdrop` alive for as long as it lived.

### Zone files: what ships, what is fetched, and what the server must never read

- **The library ships now** (`release.ps1` `$ShipGlobs`, 609 files, 2.5 MB). It
  had never shipped before 2026-09-28, so every archive up to 0.1.17 gave a
  player no zones for any map. `local\` and not `online\`, which looks backwards
  and is not: `online\` resolves into the Momentum install, so on a machine
  without Momentum it is not a directory at all. The Pi is the mirror image --
  its `game/ftesurf/maps/zones/local` holds only 66 overrides because its
  Momentum mount supplies the other 537, which is why the nginx alias points at
  `ftesurf-site/zones` (the shipped set) and NOT at the server's own copy.
- **`cl_zonedl.qc` fetches what a release could not know about.** Client only.
  `sv_zones.qc` does not read `maps/zones/dl/` and must not: the server's table
  is what the clock is a function of, and it is not going to come from an HTTP
  fetch made by the box being timed. What the fetch buys is the DISPLAY.
- **The URL is a client cvar (`cl_download_zonesrc`), never `sv_dlURL`.** That
  one arrives in serverinfo and is whatever host you connected to; a zone file
  from there would be a stranger deciding where this client thinks the start
  zone is. A server cannot set a client cvar. Empty switches it off.
- **`dl/` is tried LAST of the three file sources, and that is the safety
  property rather than a preference.** A fetched file can never beat a shipped
  one or your own edit, so a bad mirror stops mattering at the next release.
- **It lands in `ftesurf/data/maps/zones/dl/`, not `ftesurf/maps/zones/dl/`.**
  QC fopen READS the whole VFS but WRITES into the `data/` sandbox, so the same
  relative path means two places depending on the verb. Both halves work
  because the read goes through the VFS the write landed in; what it costs is
  that a human clearing these by hand must go to `data/`. Measured, after the
  first version of this note named the wrong directory.
- **Proven end to end, once** (`cfg/test/b89zdl.cfg`, 2026-09-28): with BOTH
  local copies parked -- ours and Momentum's `online/` -- the log reads
  `zones: none for surf_rookie`, then `zones: 19 on surf_rookie
  (maps/zones/dl) crc d1eaee84`. The crc is the same one Momentum's own copy
  produces, and the fetched bytes hash equal to the mirror and to the shipped
  file. The first run of that arm measured nothing (no `waitms` before `map`,
  no `waitmap`, so the map never loaded and `zone_reload` came back
  `Unknown command` because CSQC does not exist without a map); the second
  named `maps/zones/online` because only OUR copy had been parked, which is
  the fixture's own stated falsification criterion firing.
- **`ZSRC_DL` is appended, not inserted**, so the three values the `.rec` header
  has always carried keep their numbers. The server never emits it.

### The boards are 2.8% of what exists, and one literal was why -- 2026-09-29

- **`momfetch.py` built every URL with `&skip=0`, so `--take 25` was a CEILING and
  not a default.** Measured against the cache it produced: **81,290 times held of
  2,927,709** that exist, with 2,914 of 3,726 boards stopped at exactly 25 places.
  The API pages fine -- `skip=100` returns ranks 101-200, contiguous, probed by
  hand. Nothing had ever asked it to. `--depth` now exists (`-1` = whole board),
  the unit of work is a PAGE, and `len(rows)` of the cached file is the cursor, so
  a sweep resumes with no bookkeeping.
- **The unit matters because one board can be 262 pages.** surf_kitsune stage 1 is
  26,112 times -- more than a whole sitting's budget for one board out of 3,726.
  Pages sort by depth, so every board reaches page 2 before any reaches page 3 and
  an interrupted deep sweep leaves the corpus EVEN.
- **What the depth targets cost**, all reconciled against an independent count
  before anything was fetched:

  | target | times | % | pages | at 1.5 s |
  |---|---|---|---|---|
  | held before | 81,290 | 2.8 | -- | -- |
  | top-100 | 262,942 | 9.0 | 3,671 | 1.5 h |
  | top-200 | 450,743 | 15.4 | 4,866 | 2.0 h |
  | everything | 2,927,709 | 100 | 30,058 | 12.5 h |

  `surfd.py`'s `BOARD_LIMIT_MAX = 200` is the deepest rank anything we serve can
  render, so top-200 is ~100% of what is visible today and full depth is for a
  rank-lookup feature that does not exist yet. Lex chose full depth anyway, on
  purpose, via `--backfill`.
- **THREE MERGE TRAPS, none of which reading found.** (1) `--refresh` at skip=0
  must MERGE and not replace, because momwatch passes it every 7 minutes and
  replacing truncates a deep board to one page per tick. (2) A short later page
  must clamp `total` to what is held, or an off-by-a-few `totalCount` is an
  INFINITE ASK that a backfill loops on forever. (3) Rows merge by `replayHash`
  ordered by time, because a board gaining a record mid-paging shifts every rank
  below it; the API's `rank` is kept but ADVISORY, which is checked rather than
  assumed -- `momboards.py` never reads it and surfd derives rank from
  `BOARD_ORDER` at query time.
- **The cost of merging is that nothing purges a run deleted upstream.** A union
  never shrinks. Deleting the board's json is the only way and it costs the whole
  depth. Deliberate trade; stated in the docstring.

### Three things now drive the top-up, and one of them is the website -- 2026-09-29

- **`momwatch.py` knew whether a board was FRESH and had no idea whether it was
  DEEP**, so a board holding 25 of 322 stayed at 25 forever however many people
  played the map. It takes `--depth` now, and a board that is fresh but SHORT is
  work.
- **`--refresh` made a tight tick pointless, and this is the one line to
  remember.** Its skip=0 pages sort ahead of every depth page, so with `--max 2`
  against two thin boards both requests re-read ranks 1-25 already held and the
  tick gained **0 rows** -- while the backfill beside it gained 50 from the same
  budget. `--refresh` is now passed only when a board is genuinely STALE.
- **`--want N` reads surfd's `mapwant` table (schema 9), written by
  `/board/api/map`.** A QUEUE AND NOT A FETCH: a public unauthenticated GET must
  never become an outbound request to somebody else's API while the visitor waits.
  Recorded only AFTER the route's own 404, so a sweep of invented names fills
  nothing, and one row per map means it cannot outgrow the library. `note_want`
  never raises -- a board page that 500s over a counter would be the worse bug.
- **`--backfill N` has its own cap on purpose**, so a busy fleet cannot starve the
  crawl and a long crawl cannot delay a map somebody is standing on. It needs no
  state: momfetch already sorts pages by depth, so a backfill is that tool with a
  small `--max` and no `--map`. **Live on the Pi's crontab** at `--depth -1 --want
  25 --backfill 15`, which is ~3,000 requests/day and ~10 days to full depth, at
  roughly a twelfth of the rate that tripped a 429.
- **`--take` now defaults to 100** in both tools. 25 was the old ceiling and is
  otherwise four times the requests for the same rows.
- **momboards had to become incremental first, and that was a prerequisite rather
  than a tidy-up.** It re-read all 3,726 files and re-upserted every row every 7
  minutes: 2.0 s and 66 MB at 84k rows, which extrapolates to ~70 s and ~2.3 GB at
  full depth against a Pi with **1.0 GB available**. Now it reads only files newer
  than `<boards>/.indexed`, flushes in chunks, and advances the watermark to the
  highest mtime PROCESSED rather than to `now`.
- **A WATERMARK MUST BE `st_mtime_ns`.** No decimal spelling of `st_mtime`
  round-trips: truncated to whole seconds, every file touched in that last second
  stays dirty; written as `%.6f` it rounds DOWN below the true value and the single
  newest file stays dirty. Both were measured, each left exactly one file re-read
  forever, and both would have looked like "incremental works" to any check that
  did not demand **zero**.
- **Bumping `SCHEMA_VERSION` still breaks `test_board.py`'s `HEAD_SCHEMA`.** 8 ->
  9 caught it on three arms that know nothing about a want-queue. The warning
  further down this file is accurate; heed it.

### Keeping the imported boards fresh -- KSF and the demo grab are cronned since 5 Oct

- **`momwatch.py` is on the Pi's crontab, every 7 minutes**, `--stale 24
  --max 40 --delay 1.5 --index`, under `flock`. It reads the `lobbies` table,
  refreshes only boards that are missing or stale for maps the fleet is on, and
  on a fresh fleet makes ZERO outbound requests -- verified on the first tick:
  "live maps 12, boards already fresh 44, boards to refresh 0". 1.5 s rather
  than the 1.0 s measured tripping Momentum's 429 after 2,164 consecutive
  requests, because this one runs unattended.
- **KSF IS CRONNED SINCE 2026-10-05, BY LEX'S EXPLICIT DECISION** ("slowly
  fill up my record list over time"); until then the rule here was "never
  automatic", and the docstring changed first, as that rule asked.
  `ksfimport.py --watch --go` every 5 minutes under `flock -n
  /tmp/surfd-ksfwatch.lock`: 10 requests 3 s apart, the next unseen page of
  every board in all four styles, maps in `mapwant` first; a refusal parks it
  6 h doubling to 48 h (`data/ksf/.refused`). Its own lock (`data/ksf/.lock`)
  also keeps a by-hand `--from-maps` from running beside it. `data/ksf/owed/`
  holds boards fetched and not yet filed; a non-empty one after a quiet hour is
  a failing write, not a backlog. Log: `logs/ksfwatch.log`.
- **`momgrab.py` fetches the Momentum demos the Pi does not hold** (cron, every
  5 minutes, `flock -n /tmp/surfd-momgrab.lock`): 6 demos a tick from
  cdn.momentum-mod.org, the top 10 of every board, converted with
  `tools/momreimport.py`'s rules. It imports momreplay/momimport/momreimport
  from the game's `tools/` (sweep.py's TOOLS), which `surfd-deploy.ps1` does
  NOT ship: copy them like the sweep's tools (`install` + `mv` under the sweep
  flock, `git hash-object` on the Pi). zstd demos (3%) need the `zstandard`
  module in the cron user's Python. State: `data/momgrab/`; demos kept in
  `data/momdemos/`. Log: `logs/momgrab.log`.
- **KSF's per-map boards ARE a paged JSON API; this file said the opposite for a
  morning.** On 2026-09-29 the board looked server-embedded in `/maps/<map>` and
  "there is no API route to find" was written up as structure. The leaderboard is
  fetched by the browser on `/maps/<map>/records`, a page neither search opened.
  Routes and traps: `ksfimport.py`'s docstring.
- **Two claims in `ksfimport.py`'s docstring were false and are corrected.** It
  said "no demo URL in any endpoint found" -- `/api/players/{id}/replays/{map}`
  returns per-zone `file` names like `replay_css_6201_0_712551_1790101734.rec` (a
  shavit .rec, no download path located, so "reachable" is still unproven). And it
  said a KSF row's build "CANNOT BE CHECKED, EVER" -- `/api/files/<map>.zip`
  answers `{"exists":true}`, and a published archive is a hashable one. Both
  conclusions stand; their reasons did not. A wrong reason under a right
  conclusion is the kind of thing this file exists to catch.
- The map roster stays a Windows scheduled task (`FTESurf map scan`, PT6H) for
  the reason already recorded: it hashes builds that live on this workstation.
