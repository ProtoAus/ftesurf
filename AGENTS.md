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
    commits back (Build 88 was 228). It now takes the number explicitly, because
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
- QC-only change → default build is enough. Treat "0 warnings" as the bar, but
  check whether a warning is yours: this tree usually carries other people's
  uncommitted work (`cl_hud.qc:2007`, a 9-arg sprintf, is a standing example).

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
- Test-cfg recipe: `cl_idlefps 0` AND `cl_maxfps 100` (uncapped fps starves
  async loads); `menu_restart` before any menu-VM command in a `+exec` run
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
  starts and there is no sidecar; `run_rearmhop 1` re-arms on the FIRST jump out
  ("start re-armed -- one jump out of the start"); the start rule refuses the
  second ("hopped start -- one jump out of the start, or walk out"); and `+right`
  alone only TURNS. Walk out, then prove the run with `cmd timer` reading
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

- Three recordings of one run, joined by filename through `FS_RunPath`: `.rec`
  (server, `sv_timer.qc`), `.view` (CSQC per-frame angles, `cl_replay.qc`),
  `.hid` (engine raw-input journal, `in_generic.c`). A forgery has to be
  consistent across all three. Taint bits demote and never accuse:
  `TF_CHEAT/NOJOURNAL/NORULESET/NOPROFILE/NOMAP/NOCLOCK` in `sh_defs.qc`,
  consumed by surfd's `certifiable()`.
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

## Pi operations (public lobbies)

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
  last one, `QC build 88` f4b5051, is 224 back as of Patch 441 -- re-measure with
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

## Pitfalls discovered the hard way

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
  for the next reader.
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
- PIXEL-DIFF HARNESS RECIPE (`cfg/test/p440font.cfg`, `tools/p440font.py`): still
  the camera with `sv_gravity 0` BEFORE the map; pick a map whose textures
  actually mount -- surf_kitsune's skyroom does not and a missing sky FLASHES
  between frames (the floor read 239133 changed pixels; surf_rookie's is exactly
  0); `con_notifytime 0`, because notify lines move AND, with notify on screen
  plus extra drawstring passes plus a busy HUD, unrelated glyphs tint to the
  console's ^7 white (BACKLOG, engine-side); park control regions off the sky
  (clouds move); a control region must not contain the feature's own widget (its
  chip has to change -- grade the panel's element rows, not the panel); and take
  the floor from a pair of shots at the SAME cvar ~0.7 s apart, grading regions
  against it, never the whole frame (the fps counter always moves).
