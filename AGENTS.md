# AGENTS.md

Working notes for coding-agent sessions in this repo. Read CONTRIBUTING.md too
(git identity, `git clean -x`, line endings, `.src` ordering).
Keep code comments concise; long-form reasoning belongs in ENGINE_PATCHES.md
essays, not in source files. See CLAUDE.md for the comment-style rules.
Beta phase, not release: building, deploying and restarting the Pi lobbies are
routine — do not hesitate when a change needs it.

THIS WORK SPANS THREE DIRECTORIES AND A FRESH SESSION IS GIVEN ONE. Before
starting anything that reaches past the gamedir, add the other two:

    /add-dir C:\msys64\home\Lex\fteqw     engine C + ENGINE_PATCHES.md
    /add-dir C:\FTESurf-private           anti-cheat plan, cheat samples, report

The engine one is not optional for anything anti-cheat, movement or renderer:
the mover, the recorder's consumer (`pm_recsim`) and every patch entry live
there, and this repo ships only a prebuilt binary. `C:\FTEQuake` is the second
install used for client-vs-server tests — add it too when you need one.

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
  OUTSIDE the mover by a map entity. `ride` = the basevelocity carrier handed to
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

## The run line (Patches 432, 449-453)

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

## Rewind (Patch 477)

- **The rewind rides the replay's pin, marked as its own: `rec_watch 1 rw`.** A
  pinned RUNNING run is frozen and practice, and EVERY way out of a rewind ends
  that run rather than thawing it -- a thaw past an unrecorded freeze convicts its
  angles (the held-run fault, under Anti-cheat). ENTER and ESC resume through
  `sl_saveat <ticks> x y z go` (an IDLE row). A refused resume, `rec_watch 0`
  (plain or `void`), a warp the server serves (SV_RewindWarped: AFTER the warp,
  and only if it moved the body), `retry`, a Multi-Session park and a lobby flip
  void it (SV_WatchLetGo). A replay's pin (no `rw`) behaves as before 477.
- **The state is the server's, never the client's.** SV_RewindSample keeps 4000
  samples a slot, one every 2 run ticks, only while running and unheld; the
  client's x y z only picks among samples within 0.5 s of its tick. A run start
  wipes the ring; a warp under the rewind marks it over, so the next start does.
- **STAT_FS_PIN (111) is the rewind's open serial while its pin is held, 0
  when not** (`rec_watch 1 rw <serial> <state at the open>`). The client closes
  the mode on a release it did not ask for, and latches only its own serial, so
  an earlier open's pin or release in flight is never mistaken for it. The
  server refuses to pin a run that started since the client asked.
- **A replay opened while browsing takes the pin over in the same frame**
  (Watch_Open calls Rewind_HandOver before its own `rec_watch 1`).
- **A frozen run's kept-abandon `inend` is the mover tick at the freeze**
  (`run_t_frzmt`), because the `in` rows stop there; pm_verify flies a last row
  to `inend`.
- Harness: `tools/p477rewind.py` (parks data/saves/surf_dune; its last section
  changes map to surf_embrace). `rewind key <scan> [up]` feeds the real input
  handler; `rewind status|seek|step|go|save` drive the rest.

## Imported runs: Momentum Mod and KSF

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
- **WHAT A MOMENTUM DEMO DOES NOT CONTAIN** -- proven negatives over the whole
  reference, not failed searches: view angles, buttons, ground contact. So the
  replay camera is DERIVED from the direction of travel, `fl`/`keys`/movement
  are 0, and the plane is `0 0 0` (which reccheck requires when neither contact
  bit is set -- a plane without one is a "stray plane" fault). **Never write a
  `.view` sidecar for an import**: that file is mouse evidence and a derived
  angle filed there is a measurement that never happened.
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
  explicitly unstable qsort. `ui_refilter` uses a counting sort over 11 ranks,
  which is stable by construction rather than by assumption.
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
  file, because the sweeper uses the new binary at once. An ssh that starts a
  background server does not return, so run it in the background. Run
  hand tests on a port other than 27698, which is the sweeper's. Swap by
  `cp` to `.new` then `mv -f`, keeping `fteqw-svarm64.preNNN-<stamp>`. Running
  lobbies keep the old binary until restarted; the sweeper picks up the new one
  immediately.
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
- surfd is `surfd.service` (gunicorn :8084 behind nginx), and its app log is
  `/srv/nvme/surfd/logs/surfd.log`. To deploy:
  1. Take the files FROM THE COMMIT, not the tree:
     `git -c core.autocrlf=false archive HEAD surfd/... | ssh … tar -x` into a
     /tmp stage.
  2. Run the suite there, with `TMPDIR` set to a private dir; the tests leave
     their temp dirs behind.
  3. Back up `data/surfd.db` with sqlite's backup API.
  4. Copy the files in under `flock /tmp/surfd-sweep.lock`.
  5. Reload with `kill -HUP $(systemctl show surfd -p MainPID --value)` (no
     sudo), then read the log for `surfd ready`.

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
- The vessel's x-ray films: `gfx/env/xray1.png` / `xray2.png`, local images,
  git-ignored and never shipped. PLAY hangs one behind the plankton, VISUALS
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
- fteqcc parses `x = a && b` as `(x = a) && b`: assignment binds tighter than
  `&&` and `||` (measured: `t = !first && FALSE` gave 1). Wrap the whole
  right-hand side, `x = (a && b);`, as the tree mostly does. Still unwrapped in
  committed code, left for a decision because fixing them changes behaviour:
  `snapang` in trigger_teleport_touch (sv_entities.qc) and its mirror in
  TG_FireTeleport (cl_triggers.qc) -- the keep-angles flag is ignored on both
  sides; `probe`/`hit` in TG_ChainStart and Trig_ConsoleCommand (cl_triggers.qc);
  `lpd_active` in Portal_LoadForMap; `onpanel` in Ev_InputEvent; `vote_on` in
  Vote_Frame; `vbsp_retrigger` in SV_UpdateMovementServerInfo.
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
| `Zone_LoadForMap`, `maps/zones/local/<map>.json` | every release to 0.1.17 | "this map has no zone file, so it has no legs and no times" on all 587 zoned maps |
| `cl_players.qc:403`, `gfx/thumbnails/speaking_off` | every release ever | an error texture beside EVERY player's name, permanently |
| `ui_bgprobe`, `gfx/mapshots/<uuid>-<size>.jpg` | every release ever (1.1 GB, never shippable) | a full-screen error texture behind the create panel |

**WHY IT IS INVISIBLE HERE AND FATAL THERE:** the build box has all of it, so
no amount of local testing reproduces any of the three. The only honest check
is against the ARCHIVE -- download the published file and list it, which is
also how each of these was confirmed fixed. `release.ps1` verifies the archive
matches the STAGE, and the stage matches the allowlist; nothing verifies the
allowlist matches what the code asks for.

A gate could: sweep the QC for literal asset paths and assert each resolves in
the ship set. It does not exist; BACKLOG carries it.

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

### Keeping the imported boards fresh -- and the one source that is never cronned

- **`momwatch.py` is on the Pi's crontab, every 7 minutes**, `--stale 24
  --max 40 --delay 1.5 --index`, under `flock`. It reads the `lobbies` table,
  refreshes only boards that are missing or stale for maps the fleet is on, and
  on a fresh fleet makes ZERO outbound requests -- verified on the first tick:
  "live maps 12, boards already fresh 44, boards to refresh 0". 1.5 s rather
  than the 1.0 s measured tripping Momentum's 429 after 2,164 consecutive
  requests, because this one runs unattended.
- **KSF IS DELIBERATELY NOT AUTOMATED AND MUST NOT BE.** `ksfimport.py`'s own
  politeness contract says "never automatic: every run of this is a person
  typing it", reasoned against that host in the wrlines reference. Do not cron
  it; if the operator wants KSF refreshed on a schedule that is their decision
  to make explicitly, and the docstring should change first.
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
