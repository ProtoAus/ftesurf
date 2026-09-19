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
- QC-only change → default build is enough. Treat "0 warnings" as the bar, but
  check whether a warning is yours: this tree usually carries other people's
  uncommitted work (`cl_hud.qc:2007`, a 9-arg sprintf, is a standing example).

## Run and test

- Normal launch: `./ftesurf64.exe` (or `ftesurf.bat`).
- Headless: `./ftesurf64.exe -WindowStyle Minimized +exec <name>` with cfgs in
  `ftesurf/cfg/test/`; output in `ftesurf/logs/<log_name>.log` and
  `ftesurf/screenshots/`. Verify by reading logs and screenshots.
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
- DRIVING A RUN: the clock starts when you LEAVE THE START BOX. `+jump` hops in
  place (~80 u in 4 s on a bhop map) and never starts it; `+forward` walks at
  `sv_maxspeed` (260, `default.cfg:432` — the move values are 450 precisely so
  they cap nothing) and clears the box in about a second. `timer` prints the
  client latches, `cmd timer` the server's.
- MEASURING A DRAW: with no console dump, take two screenshots with exactly one
  variable changed between them and diff the numbers — a frozen column beside a
  live readout that moved is a measurement, one picture is not.
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
    (`cheated`), which is fine once no measurement depends on the clock. On maps
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

## Generated / never edit

`ftesurf/*.dat`, `*.lno`, `src/defs/*.qc`, `ftesurf/ftesurf.cfg` (auto-saved
archive), `ftesurf/data/**` (player data), `installed.lst`, `crashaddr.txt`.

## Conventions

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
    number. Fix a collision forward by renumbering yours; `patch` never moves
    down.
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
  omitted row is a cvar the reset button cannot recover), and a documented
  `set` line in `default.cfg`.

## Boundaries and interfaces

- Server QC is authoritative (saveloc lists, timer/zones, heartbeat, board
  submits). Client QC renders/predicts. Menu QC is offline UI + directory.
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
  same binary and pin. It replays with the file's own trace cvars
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
- A LOBBY STREAMS, AND A STREAM CANNOT REWIND. A `retry` reads it back into a
  buffer first (Patch 368, SV_RecDestream); a lobby save-load still drops the
  recording, so a segmented lobby run has no replay (`rt1cl.cfg`).
- Experiment convention: numbered (E1…), one cfg per arm in `cfg/test/`.
  PRE-REGISTER the predictions and the falsifier in the cfg header before
  running; keep a CONTROL that must still fail (a harness that merely got looser
  improves both); write the result back into the header afterwards, INCLUDING
  the predictions that failed — build 85's did, and the failure was the finding.
  Each prediction must name an observable the change can actually move, and
  every changed call site needs a subject that only it affects. p358 first
  "verified" a restore through a cvar string the patch never writes.
- Capture pattern for a live recording: a run only closes at the finish, which a
  scripted walk never reaches. So the harness holds the run open at the end and
  an outside poller copies `data/parts/0.rec` during that window (an abandoned
  stream is removed on quit -- unless the run passed `run_resume_min`, see
  below). `b85ride.cfg` is the current worked example.
  On a lobby, copy `data/parts/p<port>-<slot>.rec` from the Pi over ssh during the hold
  (`p352live.cfg`). A copy taken mid-write ends in half a row.
- Multi-Session (Patch 365): a run of at least `run_resume_min` s is PARKED on
  every disconnect, map change and quit (QC `SV_Shutdown`; not `retry`) into
  `data/resume/<map>/@<guid|local>/save000/`. A fixture that reloads or quits
  mid-run leaves a slot there that the next run on that map is offered: clean it
  with the rest of the test data, or `set run_resume 0`.

## Pi operations (public lobbies)

- 12 lobbies, systemd `ftesurf@1..12`, basedir `/srv/nvme/ftesurf-server/game`;
  lobby cfgs sourced from this repo's `ftesurf/cfg/lobby/` — edit here, scp there.
- Restart: sudoers is per-unit only — loop `sudo -n systemctl restart ftesurf@$i`
  for i in 1..12.
- Deploy server progs with `./build.ps1 -Pi` (refuses while players are
  connected, scp's both .new files, hash-verifies on the Pi, swaps in ONE ssh
  command keeping `.prev`, restarts every active lobby); menu.dat stays local.
  `-PiForce` overrides the refusal — beta phase, and the connected player is
  usually the reporter; say so when you use it.
  `-Pi` SHIPS THE WORKING TREE. When the tree carries other sessions'
  uncommitted QC, build from a clean `git worktree add <tmp> HEAD` instead, and
  remove the worktree afterwards.
- The lobbies run a NATIVE aarch64 engine, `game/fteqw-svarm64`, built on the Pi
  in `/srv/nvme/p349build`. That tree is NOT a git checkout: send changed files
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

## Chat and `say` — the contract, and it changed in 342

Getting this wrong kills the restart keys silently, so it gets its own section.

- `say` does NOT arrive via `registercommand` (engine commands beat
  CSQC_ConsoleCommand). The engine offers it to the `CSQC_ChatSay(args, team)`
  globalfunction before sending (patch 341, `zqtp.c`).
- BARE `say` opens the draft; `say <text>` is DECLINED so CL_Say sends it
  (patch 342). `say_team` is declined outright (no teams here), and `/me`
  (`CL_Say`'s `extra`) never reaches the hook at all. Taking text back breaks
  `bind r "say !r"` / `!m` in `default.cfg:864-865` (and `defaultuser.cfg`) —
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

## Pitfalls discovered the hard way

- `pwsh`, never `powershell`.
- Deleting save dirs behind a running server does NOT clear its in-memory list;
  it rescans on map change/lobby flip/restart. Delete-all is `sl_delall`.
- Two clients writing the same `log_name` interleave confusingly.
- A leftover test process (`ftesurf64*.exe`, `fteqwsv64.exe`) holds
  `fteplug_hl2_x64.dll`, so build.ps1's deploy aborts part-way and `C:\FTEQuake`
  keeps a stale server. Check `Get-Process ftesurf*,fteqw*` before `-Engine`.
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
- fteqcc: `arr[i]_x` does not compile ("Cannot cast from vector to float") —
  copy to a local vector first; sprintf takes ≤ 8 args (warns above, and DROPS
  the ninth silently); a lone `;` branch warns Q205 — use a comment-only block;
  big fixed arrays blow the globals/strings budget (4096 rows forced a 32-bit
  target — size them to the library).
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
- Build and verify (headless run + logs/screenshots, or Pi journal) before
  declaring any task complete.
