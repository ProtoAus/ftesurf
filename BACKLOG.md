# BACKLOG.md

Open bugs and follow-ups that someone found and did not fix. One entry each:
what, where, how to check it, where it came from. Add what you find and leave;
delete the entry in the commit that fixes it. A "Known" paragraph in
ENGINE_PATCHES.md is a record, not a to-do -- put the item here as well.

## conbridge: what its guards do not cover -- 2026-10-10

`tools/conbridge.py`, left open by its one review. `Session.push` refuses
`map`/`devmap`/`changelevel` typed at the CLIENT, but an alias, an exec'd cfg or
the menu's own PLAY still starts a listen server with `run_resume 1` on the
owner's profile. An explicit `cfg_save` (hud_edit's save runs one) still writes
the session's window and fps cvars into ftesurf.cfg: the tool keeps the
pre-session copy and exits 1, it neither prevents nor restores. And `cmd_serve`
runs the pipe handshake inside `listener.accept()`, so a local process that
opens the pipe and says nothing stalls every request (reviewer-reproduced).
Falsifier for the last: hold `\\.\pipe\ftesurf-bridge-<name>-*` open and
silent; `status` must still answer.

## Dedicated server exits 0xC0000005 on a map it cannot find -- 2026-10-10

`C:\FTEQuake\fteqwsv64.exe` (FTE git-7144-patch-606) started with `+map` naming
a map that is not installed asks `https://play.proto.bar/maps/<name>.bsp`, gets
404, logs `SV_Error: Couldn't download map <name>.` and ends with exit status
3221225477 (access violation), not an error exit; crashaddr.txt is not written.
Two runs of two, both under `-plugin` with piped stdin. Not reduced: unknown
without `-plugin`, on the Linux lobby binary, or for `map` on a running server.
Falsifier: `python tools/conbridge.py start --no-client --map no_such_map_zz`
prints `process exited rc 3221225477`; fixed, the status is a plain error exit
or the server stays up. Found testing tools/conbridge.py.

## P577-580 primary Windows reader deployment blocked -- 2026-10-08

`C:/FTESurf/tools/census/recsim.py` is tracked and modified in the shared
checkout, so the verified bounded reader was not installed over it. Existing
bytes and paired readers were preserved. Pi and secondary Windows reader
installations are verified; this is incomplete dual deployment, not a reader
code failure. Resolve destination ownership before using the commit-pinned
`tools/simcheck_runtime.py` capsule; do not overwrite/stash/revert peer edits.

Falsifier: owner-coordinated primary target accepts the exact predecessor and
paired-reader hashes, dry/apply succeed with rollback preserved, installed
source-limit controls ACT, and both Windows destination hashes match the same
verified reader. Recorded with P580 and the similarity reliability notes.

## Refract dither with explicit translucent flags -- 2026-10-07

`plugins/hl2/mat_vmt.c:Refract` plus the shared translucent tail: a synthetic
Refract with `$translucent 1` / `$alpha 0.4` in mode 2 changes the dither pass
into a blended pass. On GLSL-only compatibility OpenGL that pass can disappear.
The matching plain Refract control draws an acting dither and remains
pixel-identical across P543. Not fixed as part of water readability.
Falsifier: identical synthetic pane geometry/texture with and without those
keys; prove shader bits/program and covered pixels, then preserve the chosen
mode's discard coverage rather than silently selecting the progless blend path.

## Source live water: parity and depth-cost coverage -- 2026-10-07

P541 fixes depth binding and shallow distortion/fog in live modes 1/2;
`plugins/hl2/glsl/vmt/water.glsl` uses eye-depth gap, not Source's fog-alpha
capture or volumetric ray length. P543 fixes mode 0 visibility/live sorting,
strengthens water-only dither, and limits dark baked reflection in modes 1/4;
these low-cost modes remain approximations.
OpenGL controls pass on surf_aesthetic and neutral/fog-range/no-fog variants;
other materials and backends are not yet runtime-verified. Falsifier: matching
Source/reference captures from above/below, grazing/rotated and foreground
views, with an acting depth control per arm; measure frame cost as well as
appearance. Do not infer universal FPS from no additional scene capture.

## Source swimmer: exit and collision coverage -- 2026-10-07

Patch 538 restores actual swimming input/drag and versioned wet replay. Remaining
Source-parity/assurance work is separate from the fixed drift and orange tint:

- `engine/common/pm_source.c:PMSrc_FullWalkMove` still has no Source scripted
  water-lip jump. Falsifier: a level-2 submerged player pressing forward at a
  climbable lip gets the Source reference's timed exit impulse; controls for a
  solid ceiling, no lip and jump release do not get an unsolicited teleport.
- `PMSrc_WaterMove` reuses the old portal-aware slider on portal maps, avoiding a
  speculative down-step at an exit. Submerged portal crossing, aperture edges,
  water stairs/sliding and carrier-collision cases are not runtime-verified.
  Falsifier: a proven submerged portal control transforms destination/angles/
  velocity and increments crossing count; basevelocity is removed exactly once;
  blocked/free stair and moving-carrier arms both act and a fresh version-3 wet
  replay reproduces them on Windows and aarch64. Do not infer this coverage from
  ordinary free-water swimming or the dry determinism/replay gates.

## Missing-asset selection: Source pass maps and model failures -- 2026-10-07

Patch 534 ships the 64x64 engine-checker override and a red/fullbright extruded
Impact `models/missing_error.md3` asset, NOT automatic model-error selection.

- `plugins/hl2/mat_vmt.c:Shader_GenerateFromVMT` can emit an explicit pass map
  for UnlitGeneric; `engine/gl/gl_backend.c:Shader_BindTextureForPass`'s T_GEN_SINGLEMAP
  binds the failed image rather than the T_GEN_DIFFUSE missing_texture fallback.
  The isolated found-VMT/missing-$basetexture control remains black even with
  the authored fallback loaded at64x64. Falsifier: found/missing VMT and
  found/missing base-texture controls must produce the intended visible checker;
  keep legitimate black/optional masks, normal/gloss fallbacks and loading
  textures distinct. Do not generalize the successful missing drawpic control
  into all Source shader behavior.
- `engine/gl/gl_model.c:Mod_LoadModelWorker` sets MLS_FAILED and returns NULL
  at the required-load boundary; optional/static-prop paths can retain mod_dummy entries.
  Hook the ERROR model only in the appropriate renderer submission paths,
  preserving warnings, original bounds/identity/collision and server behavior.
  Falsifier: missing Source prop and missing ordinary model act visually while
  real models remain identical; error-model absent/corrupt cannot recurse or
  crash; PVS/distance/bounds and many-missing-prop costs remain bounded. No
  loading-success lie or collision substitution belongs in an art patch.

## Source particles and water: coverage and budget audit -- 2026-10-06

Lex requested expected HL2 visuals without sacrificing high FPS. This is an
AUDIT, not a renderer fix/deployment. Particle evidence is reproducible with
`python tools/census/particlecoverage.py --json <report.json>` (nine synthetic
control tests in `test_particlecoverage.py`). Water source inspected at engine
`c4f372ab2`; the installed binary's runtime was exercised separately, not treated
as proof that every source path was built into it. No FPS improvement is claimed.

- **Particle coverage stops at two maps.** `tools/pcf.py:main` defaults `--all`
  to tensor2/boreas; `src/client/cl_emit.qc:Emit_PsysIndex` loads only registered
  bakes from `data/mapparticles.txt`. In 1,349 installed BSPs, 144 maps contain
  8,000 `info_particle_system` entities, 96 embed PCFs, and 94 of those have no
  registered bake. `surf_kitsune2` alone has 36 start-active entities referring
  to five translatable, unbaked effects. Both existing cfgs reproduce exactly
  with the current translator (20 tensor2 systems; 13 boreas systems plus one
  skipped instantaneous prefill). This is not proof of Source-equivalent
  motion/materials: the translator reports approximations, and default child
  emission is off. Falsifier for expansion: every intended effect resolves and
  ACTUALLY emits after a cold load/map return, with Source reference captures,
  missing-operator/material reporting and a measured particle budget. Do not
  blindly generate a cfg for every BSP: shared game-pack libraries need their
  own resolver and many maps contain no particle systems.
- **Bulk baking currently overwrites multi-PCF maps; v5/corrupt libraries block
  coverage.** `tools/pcf.py:main` writes `<map>.cfg` and replaces that map's index
  rows INSIDE its per-library loop. Twenty-three particle maps embed multiple
  PCFs (`surf_ace` has two; `surf_board_this` five). Union definitions before
  writing, report name collisions and preserve child links. The read-only audit
  unions libraries but does not change that writer. `tools/dmx.py:parse` refuses
  ten DMX binary-v5 PCFs; `surf_map_h`/`surf_map_njv` additionally have bad CRCs
  for `particles/thw_river.pcf`. Falsifier: a synthetic two-library map retains
  both effect sets and one combined index, a v5 parser reaches exact EOF on real
  fixtures, and corrupt input remains a visible failure rather than a partial
  successful overwrite.
- **Boreas smoke material cannot load.** Isolated cold runtime prints
  `materials/project_tendies/tendies_smoke.vtf: unsupported VTF image format 19`
  and draws the missing texture. `plugins/hl2/img_vtf.c:ImageVTF_VtfToFTE` leaves
  `VMF_BGRA4444=19` unsupported. Correctly generated particle scripts cannot fix
  this. Falsifier: decode BGRA4444 channel/alpha fixtures exactly, load the real
  smoke texture with no fallback, and inspect emitted smoke against Source.
- **Fire still uses generic orbs or unanimated sheets.** Lex identified
  `surf_dune`/`surf_anubis`. `src/client/cl_emit.qc:Emit_LoadForMap` maps
  `env_fire` to the generic `FX_FIRE`; its smoke-stack approximation does not
  select the authored material. `tools/pcf.py:translate` emits a texture stem
  but no VTF sheet frame selection; native `engine/client/p_script.c`'s
  `tcoords`/`atlas` select a static cell at spawn, not animation over its life.
  Patch 531 supplies separate native texframe/texanim stepping with bounded
  arbitrary UV tables, lifetime/loop/clamp and a compiled-backend extension.
  It is only the renderer prerequisite: product emitters/bake/installed bytes
  are unchanged. Native colored-atlas and actual Dune/Anubis sheet controls act
  in isolation; full map budgets, Source parity and deployment are not accepted.
  Dune has 65 env_fire and 42 PCF fire instances (21 dune_fire_medium_03,
  13 fire_medium_02, 8 fire_medium_02_nosmoke); Anubis has 161 env_fire and
  498 env_smokestack. All Anubis stacks name particle/SmokeStack.vmt, a
  ParticleSphere material: do not reinterpret every yellow stack as atlas fire.
  Dune's custom flame selects sequence 2 of fire_particle_4, a 16-frame
  sequence in VTF resource 0x10. Its SpriteCard VMT asks for addself .75 and
  overbrightfactor 3.5; neither is equivalent to merely checking $additive.
  A private single-pass, four-sprites/site, UV-stepped prototype produced
  visible flames with bloom off, but is NOT a shipped or Source-exact loader.
  Falsifier for the product fix: resolve the shared env_fire libraries as well
  as embedded PCFs; consume authored UVs/timing/sequence and size/flags; preserve
  child graph references and report unsupported material/operators. Verify
  frozen-pose frame-only pixel changes, a repeated no-effect control, real
  map return/cold load and archived off/low settings. Enforce visible-site,
  sprite and overdraw budgets/LOD. Compare CPU/GPU costs against the ACTUAL
  current emitter path, not just a matching-count polygon glow control;
  production shared-PCF resolution, smoke/embers, old-client support and ship-set
  checks remain open. Do not add mandatory full-screen bloom, depth captures or
  dynamic-light/shadow passes to obtain a cheap bright flame.
- **Water's depth fog/capture budget remains incomplete.** Patch 523 adds
  capture-free mode 4 and repairs cheap reflection tint/view frame/signed scroll.
  Mode 1 still captures refraction; mode 2 captures refraction/reflection.
  `plugins/hl2/mat_vmt.c:Shader_GenerateFromVMT` emits no `#DEPTH` sampler, so
  above-water depth fog is disabled; `water.glsl`'s dormant branch hardcodes
  4096 rather than material fog start/end, and screen-UV correction hardcodes
  1080. `waterbudget.glsl` deliberately approximates fog colour/transparency:
  it is not a depth-correct or Source-exact replacement. Source references:
  `watercheap_ps20b.fxc`, `water_ps2x_helper.h`, `water_vs20.fxc` in the SDK.
  Falsifier: shallow/deep/underwater views respect authored fog; above/below,
  normal/no-normal and cube/no-cube cases act rather than silently fall back.
  Balanced/full paths should share captures per plane and enforce explicit
  resolution/update/visibility budgets with full-capture positive controls.
  Measure scene passes and CPU/GPU time; local fixed-camera wall-frame timings
  are not a portable FPS claim or Source visual acceptance.
- **Graphics menu still needs a complete acting per-row audit and glass baseline.**
  `src/client/cl_gfx.qc:Gfx_Def`/`Gfx_Inert` and engine VMT/BSP consumers must
  agree on default/range/meaning/inert conditions and application boundary.
  Patch 523 fixes glass 0's Translucent label and warns cached material rows
  need rebuilding; retry can reuse BSP data. It does not widen Plugin_GetCvar's
  masked shader/map flags. Falsifier: for each row, exercise an affected rendered
  object, a live/rebuild/fresh-map control, menu/readback and fresh-process
  persistence. In particular prove `hl2_refract` 0/1/2 on an actual pane, alpha
  and visible scene-copy policy with an acting full-refraction control before
  deciding whether a new low-budget glass shader is needed.

## Credentials at rest, and 9.3 GB of database backups -- 2026-10-05

FIXED HERE: `data/surfd.db` was `-rw-r--r--` on the Pi, and it holds `runs.player`
for every ranked row -- a guid, which is what a keyed lobby authenticates a submit
by. surfd now installs `os.umask(0o077)` at import and `_harden_db_files()` at the
end of `connect()`: the umask covers what libraries create (sqlite's `-wal`/`-shm`
appear on the first write, AFTER connect() has returned, and are unlinked again
when the last connection closes, so neither is reachable from a startup-only
chmod), and the chmod covers a database that already exists loose, which no umask
can reach. `tools/surfd-deploy.ps1` chmods the backup it makes, refuses to continue
if that backup is not 600, and tightens every `surfd.db*` file on every run --
which is what fixed the 35 copies already on the host (`TIGHTENED=36`,
`STILL_LOOSE=0`, live db now 600, /health and `/board/api/map` still answering).
The arm is `test_surfd.py` section 10; it SKIPS OFF WINDOWS with a printed line
(Windows reports no group/other bits, so both halves would be fiction) and was run
under WSL against HEAD's `surfd.py` as a control: 4 FAILs there, 0 here, with "the
owner can still write the hardened database" passing in both -- the half that would
have taken the board down if a chmod had cleared the owner's write bit.

Two things this measurement turned up that need a DECISION, not code:

- **THE GAME'S OWN DATA TREE IS WORLD-READABLE AND ITS FILENAMES ARE GUIDS.**
  Measured on the Pi: 10,938 of 10,938 files under
  `/srv/nvme/ftesurf-server/game/ftesurf/data` are 0644, including 64 `.rec` named
  `<ticks>_<name>-<guid8>_run.rec`, 37 evidence files, 45 saves and 30 resume
  slots; `data/` and `data/runs/` are 2755. A DIRECTORY LISTING ALONE IS ENOUGH,
  so file modes do not cover it -- the guid is in the name. The live lobby unit
  says `UMask=0022` (`systemctl show ftesurf@1 -p UMask`), which is why. The fix is
  `UMask=0077` in `surfd/server/ftesurf@.service` plus a reinstall (Lex's sudo) and
  12 restarts, and it only helps files created afterwards, so the existing tree
  wants `chmod -R go-rwx data` and `chmod 700 data` in the same pass. Nothing else
  on the box reads those files as another uid -- surfd reads them as `proto`, nginx
  proxies to :8084 and never aliases into the tree -- so the cost is only that a
  future tool run as another user stops working. UNCHECKED BEFORE DOING IT: the
  unit also has `StandardOutput=append:.../server%i.log`, and whether systemd
  applies the service's umask to a file the MANAGER opens was not established; if it
  does, a fresh install's log could end up root-owned 0600.
  Falsifier: `find <basedir>/data -perm /077 | wc -l` reads 0, and a lobby still
  writes a recording afterwards (join with `cfg/test/p339pi.cfg`, then
  `ls -l data/parts`).
- **THE DATABASE BACKUPS ARE 9.3 GB AND NOTHING PRUNED THEM.** 11 written by
  surfd-deploy.ps1 (7,535 MiB, ten of them on 5 Oct alone) plus 24 hand-made copies
  (1,814 MiB: `surfd.db.pre*`, `.post*`, `.prewipe`, `.bak-preboard`), on a 458 GB
  volume at 88% with 53 GB free. The database is 700 MB and grows with the
  full-depth board crawl, so the price is one copy per deploy, forever.
  `-KeepDbBackups N` now prunes the script's own oldest after the deploy has
  verified, and reports the hand-made ones without ever touching them (the glob is
  anchored on `bak-<sha>-<stamp>`, because `surfd.db.bak-*` alone would have
  swallowed `surfd.db.bak-preboard`). The default is 0 = REPORT AND DELETE NOTHING,
  because a deploy that made the backup is not a deploy that may decide to destroy
  older ones. Lex's call: what N is, and whether the 24 hand-made copies and
  `game/ftesurf/data/momentum.pre-mtv-20261004-093119` (1.4 GB) are still wanted.
  Every deploy prints the figures at step 7.

## surf_voyager: Source's brush test -- engine Patch 492, 2026-10-05

Reported by Lex: the auto-surf map fell short here and flies in Momentum/CS:S.
Engine Patch 492 (with its review round) puts Source's brush test and current
Momentum's slide-bug rule behind `pm_fixrampbugs 2`, which default.cfg now sets.
Against his Momentum run (`data/momentum/surf_voyager/main/0004418_proto-
2da02252_run.rec`, 66.27 s, %.2f per tick) the game now finishes in 1:06.270,
the same 4418 ticks, with every tick to 11.64 s equal (ENGINE_PATCHES.md, 492).

- **Left: the V trough at t 11.655.** Ours (-2675.63, 0.98, -2682.72) against
  (-2676.22, 0.19, -2682.12); 0.6-0.8 u/s, then contacts land a tick apart and
  positions drift to ~5 units by the finish. Not a rule this patch can name yet.
- **Times across the switch: wiped** (Lex, 5 Oct). The fleet's 173 runs and 61
  replays set before the 10:09 UTC deploy were deleted from the board, backup
  `data/surfd.db.prewipe492-20261005-102446`; the imported archives stay. A future
  rules change wants a ruleset epoch on board rows instead.
- **SL_RowGrounded** (sv_saveloc.qc) uses QC `tracebox`, which keeps the Quake 2
  test while the mover uses Source's; both probe 1 unit down, so they can differ
  only at brush ties and edges (a player gains at most ~1 unit).
- **Bumps:** `pm_bumpcount 8` matches Momentum 0.10's `mom_mv_bumpcount` (8, read
  from its console by Lex).
- **Triangles and props are not on Source's rules yet** (review round 2 of 492).
  Under the clip they keep Quake 2's test on true fractions while brushes decide
  on the adjusted enter; running them through the brush's rules, as Source's
  `dispcoll_common.cpp` does, needs ground truth on a displacement or prop map
  (surf_boreas's ramps are .phy props). The final review measured what the mix
  costs: a brush plane just under 1/32 behind a triangle face can win and leave
  the box up to 0.004 behind that face at large coordinates (176 of 9,134 crafted
  near-ties; 0 with the clip off). And Source's own leave epsilon lets a box
  clipping a wall's top by 0.02 end up to 1/32 inside it, brushes only, as in
  Source. Physics only: a replay runs the same code. Nit: pm_verify's refusal
  prints fixrampbugs with %g, so 1.9999999 reads as 2.
- **Generated edge bevels:** voyager compiled without them and `hl2_brushbevels 1`
  adds 13,802 planes; Source traces the brushes as compiled. The match to 11.64 s
  says they did not matter there; another map could differ on them.
- **Tools:** engine worktree `C:\tmp\ftevoy` (branch `p492-test`) carries the
  per-tick dump (`pm_dispprobe 5`); a flight is `+back` for 600 ms from
  `zone_goto 0` with `run_startjitter 0`, and the recording's rows compare
  directly with the Momentum file's (17 fields, t x y z vx vy vz ...).

## The player pages: what they left — 2026-10-05

- **No link to a Momentum profile.** `dashboard.momentum-mod.org/profile/<id>`
  takes Momentum's user number, and no row carries it (`momfetch` drops
  `user.id`), so a player links to Steam. Keeping that number per SteamID
  would give the real link.
- **KSF's map link opens Forward.** A Sideways, Half-Sideways or Backwards
  row's "KSF" button lands on the Forward records; whether ksf.surf takes the
  style in its URL is not established.

## The KSF crawl, the demo grab and the site: what they left — 2026-10-05

- **No per-row "Get demo".** `surfd/momgrab.py` takes the top 10 of every
  Momentum board on its own (maps people view first); a run deeper than that
  never gets its demo. A button needs a queue the web GET can write (a table,
  so a schema bump -- `test_board.py` pins `HEAD_SCHEMA`) and momgrab reading
  it first. ROADMAP 4.
- **The game's board has no style picker.** KSF's Sideways, Half-Sideways and
  Backwards (styles `sw`/`hsw`/`bw`) are tabbed on the website only;
  `cl_online.qc` sends whatever style the HUD asks for and the HUD only knows
  clean/segmented. ROADMAP 5.
- **KSF players who enter a board between its first page and our cursor are
  never fetched.** Page-1 refreshes (every 14 days) catch new records and the
  cursor catches the tail; the middle needs a re-walk, which costs the whole
  board. Nothing purges a run deleted upstream either. `ksfimport.py`'s
  docstring, "WHAT IT CANNOT SEE".
- **KSF's 100-tick boards (`game=css100t`) are not imported.** A different
  tick rate is a different measurement -- its own tier if wanted.
- **Many Momentum WR demos are on an older build of their map, and momgrab
  refuses them** (the line would be drawn on geometry the player never
  touched). First real tick: surf_nebula's WR demo is AF9C49E4, the installed
  map F8DA5606. Count after a week: `python3 -c "import json;
  d=json.load(open('data/momgrab/state.json'))['done'];
  print(sum(v=='otherbuild' for v in d.values()), len(d))"` on the Pi.
  Holding the old builds would need a per-build map store (ROADMAP 8).
- **The leg-0 cap scan now runs BEFORE the write lock** (contention with other
  writers gone -- it used to hold the lock 0.37 s on every first finish), **but
  the scan itself is still 0.37 s**: it walks the imported rows (639k on the Pi)
  to count the network's own. Both suggested follow-ups have teeth, so this stays
  open rather than being "just add an index": an index on `(leg, tier)` only pays
  off if `_runs_full` is rewritten to a POSITIVE tier list, and that changes what
  is counted -- today's `tier NOT IN (imported)` counts hidden `tier@runid` rows,
  a positive list would silently drop them. A count kept beside the table has to
  stay in step across submit, sweep, reject cleanup and migration. Throughput-only.
- **The site's two in-game pictures are crops of test captures** (debug text
  cropped out). A clean screenshot session on Lex's PC would do better; not
  taken on 5 Oct because the other sessions' arms refuse to run beside a second
  game.
- **test_admin.py fails two checks on this PC** ("names the amplification
  guard", "three snapshots cost no more packets than one: got 8, want 4"),
  identically on 9fc2703 before any of this.

## Input evidence: built, and still unwired at one end — 2026-10-05

Found while triaging the fifteen samples in the private `Cheats/` corpus. Ten of
them are in-process CreateMove rewrites (recorders, TAS with segmented
checkpoints and re-recording, strafe optimisers with gain/strength/"silent"
modes) and that layer is the one nothing here has been aimed at: `.rec`, `.view`
and the engine's own angle accumulator all come to describe the SAME angles, so
`pm_verify` PASSes (the trajectory is exact — that is the tool's job), the receipt
signs mutually consistent digests, and `.rec`-vs-`.view` agrees by construction.
The one artifact that can object is the `.hid`, because `IN_Commands` journals
each event BEFORE dispatching it. Patch 484 wired the journal's contents into the
sweep and closed the pitch axis; **Patch 486 then shipped the counter's consumer**
(`cl_replay.qc` reads the five `in_jrn484_*` cvars under `IJH_IDENT` and sends them
at most once a second, `sv_timer.qc` keeps the latest as `run_t_ij*` and prints it
in `cmd timer`.  NOTHING WRITES THEM INTO THE RECORDING -- an earlier line here
said the server did -- so no file binds them to the evidence they describe).  What is left
below is the collection side and the rules that still only note.

- **THE FLEET COLLECTS ZERO JOURNALS, so there is no `.hid` corpus to calibrate
  against.** Measured on the live host 2026-10-05: `19 rcpt, 14 view, 4 rec, 0
  hid`, both lobby cfgs at `run_evidence_ul 1`. Raising it to `2` does not work
  either — at 110 KB/s the client's 4 MiB staging cap refuses any journal past
  ~38 s of run, and the transport is one ≤768-byte chunk per round trip. Two
  exits: a transport that is not the netchan (the plan's own open item), or
  ship the VERDICT instead of the file, which is what 484's counters are for and
  costs bytes proportional to nothing -- **486 shipped that exit, so this item is
  now about the raw files only, not about having no fleet signal at all.**
  Falsifier:
  `find <basedir>/data/evidence -name '*.hid' | wc -l` on the Pi. Until this
  moves, every `.hid` rule below is calibrated on local journals only.

  **AND NOTE WHICH CORPORA ARE FLEET-SIZED ALREADY, because it is not this one.**
  The `.rec` half IS available: the Pi's `data/runs/` holds the runs real players
  posted, and `tools/census/README.md` now records how to fetch it read-only and
  what it moved for `recsim.py` and `assist.py` (both of which had filed
  themselves as blocked on exactly that corpus).  `.hid` files are the ones that
  cannot be had remotely, because they are the artifact the netchan cannot carry.

- **THE GHOST RULE IS A NOTE, AND NOTHING PERFORMS THE CORROBORATION IT ASKS
  FOR.** `hidcheck.check_identity`: a frame whose angle moved with zero device
  counts and zero recorded keyboard turn lands in `ghost`, which is `r.note()`
  and never `r.fault()` — and its own text says "A server angle set looks like
  this and so does an injected turn -- corroborate against the .rec before
  concluding either." No tool does: `reccheck` joins `.rec` to `.view`,
  `hidcheck.cross_check` joins `.hid` to `.view`, and nothing joins `.hid` ghosts
  to `.rec`. The two causes DO separate — a `setangles` is discrete, rare,
  coincident with a `warp` record or a teleport, with the angle unchanged on every
  tick either side; an injected turn is continuous airborne steering alternating
  in step with the strafe key, on a run with no `warp` anywhere near it. `.rec`
  carries all of it (`fl` bit 1, `keys` FSI_LEFT/RIGHT, per-tick yaw). Falsifier:
  `grep -rn 'identity_ghosts' tools/ surfd/` shows the counter published and read
  by nothing but the grader. **BLOCKED on the corpus above** — a threshold set
  without one is a guess, and this tree's rule is that a check which faults an
  honest run is worse than no check.

  **Whole-angle frames are now in the same bucket** (`identity_whole`, unresolved,
  the sweep stores the journal as BLIND): a teleport on a frame that carried
  counts read as YAW/PITCH IDENTITY BROKEN, and 3 of the 4 local PBs faulted on
  exactly that (18 frames, all both-axis). The cost is that a rewrite of the
  WHOLE view angle no longer faults either, and a single-axis one faults only
  where the other axis was judged on that frame (or, for yaw, pitch is not live
  anywhere in the run). The review of 692503c drove both ways round it: a
  mid-run `-mlook` or `m_pitch 0` leaves pitch unjudged on those frames, and
  0.001 deg of pitch a frame makes any yaw rewrite whole-angle -- each stores
  BLIND, as most local journals do (84 of 123 at 9c672d1), so BLIND does not
  separate a cheat from an honest run. The `.hid`-to-`.rec` join -- unresolved frames
  against `warp ... tele` rows -- is what would give that fault back. A cheaper
  discriminator to test against a real corpus: a server angle set breaks ONE
  frame, a continuous rewrite breaks runs of adjacent ones.

  **What the receipt sweep still cannot see** (integrity review of 70f1ea3):
  Patch 505 now checks a final late `.hid` even after the journal was observed
  ABSENT, using its stored receipt identity and preserving earlier faults/key
  sightings. Unknown legacy identities still need explicit baseline permission.
  Patch 507 adds identity-bound late-view retries when a completed full read
  actually captured its absence; older unknown readiness is not inferred.
  Co-ready view/HID sources alternate, preserving old faults, journal findings
  and key sightings. Patch 510 retains separate identity-bound recording
  readiness after a completed full read found no recording, retaining it
  through a view-only completion without inventing readiness for a previously
  completed or historically unknown recording source. Late matching recordings now run nonce/angle joins
  without HID, history resets or key recounts; all co-ready sources get turns.
  Completed-source replacements, unknown historical readiness and initial
  partial full reads without a later complete observation remain outside
  automatic arrival scheduling. Header-only recording hints are bounded to
  64 lines (4095 characters each); unusual longer headers require explicit
  full rereads. Discovery cost at fleet scale is not yet calibrated.
  The no-mouse BLIND rule asks only
  whether any count exists: one 1-count frame turns a console-driven run OK again.

- **NO CROSS-RUN SIMILARITY CHECK, so the same playback twice is two clean
  runs.** `surfd/` compares no run's move stream against another's. `replays.sha`
  is a whole-file sha256 and the re-post rule asks whether "player, ticks, bytes
  or a known, current sha differ" — but two playbacks of one recording differ in
  the header `nonce` (fresh 128 bits at every `SV_RecOpen`) and in the
  `.view`/`.hid` digests, so they differ in bytes and both read as new evidence.
  The comparison that would catch it is on the `in` move columns only
  (`<mt> <carry> <movement> <angles>`), normalised for tick epoch — and it is over
  a file the SERVER wrote, which is the strongest position in the whole evidence
  chain: no client-side artifact is involved, so there is nothing on the
  attacker's side to forge. Two design constraints, both from the save machinery
  rather than from cheaters: start after the last `pause`/load or honest segmented
  play self-matches, and expect only posted runs (a main-leg abandon keeps no
  `.rec`). Falsifier: submit the same recording's move stream twice under two
  runids and watch both file.

  **MEASURED 2026-10-05, `tools/census/recsim.py` — the statistic is chosen and
  the threshold is not, and the reason is the corpus.**  Over 20 independent long
  runs (>=2000 moves, all different sha256) giving 376 ordered negative pairs,
  against synthetic positives made by re-parsing one file and perturbing it:

  | case | match | cover |
  |---|---|---|
  | exact replay, shifted tick epoch | **1.0000** | 1.0000 |
  | replay, first half only (the trimmed playback) | **1.0000** | 0.4998 |
  | replay, ONE move perturbed at 1% of the run | **0.9997** | 0.0098 |
  | replay, 0.1% of moves perturbed | **0.9990** | 0.0047 |
  | replay, 1% of moves perturbed | **0.9900** | 0.0006 |
  | 376 pairs of genuinely different runs — max | **0.5242** | 0.0078 |
  | 376 pairs of genuinely different runs — median | **0.1660** | 0.0000 |

  **`match` (agreement over compared rows) IS THE DISCRIMINATOR, and `cover`
  (exact contiguous prefix) is diagnostic only.**  That was measured, not chosen:
  cover separates further on an exact replay (1.0000 vs 0.0078) and looks like the
  better statistic, but it fails on the two attacks that matter — it is BRITTLE
  (one perturbed move early drops it to 0.0098, so a playback tool that edits a
  single input anywhere reads as completely unrelated) and it MISSES THE TRIMMED
  PLAYBACK, the cheapest attack there is, which reads 0.4998 while `match` still
  reads 1.0000 correctly.  A discriminator that fails on the weakest version of
  the attack is not a discriminator.  The first cut of the tool reported cover as
  the headline and would have shipped a gate that a partial playback walks past.

  `match` separates 1.0000 against 0.5242 — **a margin of 1.91x** — and the
  highest negative is two runs of the same map that share a common opening
  (holding forward out of a start box, standing idle) and agree nowhere else.
  A gate would want `match >= ~0.95` AND `compared >= ~1000` rows, so a short run
  cannot reach the threshold by luck.

  **WHY THERE IS STILL NO THRESHOLD AND NO CODE IN surfd: THE LOCAL CORPUS CANNOT
  CALIBRATE ONE.**  It holds no two genuinely independent runs of one map.  Every
  multi-run group here is harness output, and finding that took three passes at
  the fixture filter, each of which let a class through:
  * pass 1 filtered two directories and reported `surf_derpis`'s nine files as the
    false-positive risk — they are `tools/test_reccheck.py`'s own mutants
    (`n1late`, `n2noopen`, `n3noclose`, `n4steer`, `n6late`, `n7pe`, `n8move`,
    `p5lag`).
  * pass 2 added names and still reported `b88fin` vs `p356_v10` at match 1.0000 —
    those live in `data/runs/bhop_eazy/main/`, **a real directory holding harness
    output**.  There is no way to tell them apart by path, only by name.
  * pass 3 found `surf_666`'s `anna-ab9ae4aa` group: three runs 2.5 min apart
    sharing a 299-move identical prefix, all with **different sha256 and different
    runids**.  They are the `p371*` harness on port 27641 (`cfg/test/p371sv.cfg`
    maps surf_666).  A name filter cannot catch that either, because a harness can
    use any player name.
  * `surf_aura` and `surf_aweles` each turned out to be ONE FILE STORED TWICE —
    byte-identical, same sha256, one copy under `data/p369/` and one under
    `data/online/`.  **A byte-identical copy needs no move-column comparison at
    all: `replays.sha` already catches it.**  What similarity adds is the
    NON-identical duplicate — one performance recorded twice, with a different
    nonce, a different absolute tick epoch and different file bytes.
  * And 45 of the pairs are runs of 7–13 moves, stubs a harness produced by
    walking out of a start box.  Two 9-move runs agree over all 9 and report a
    perfect score.  Nine quaternions of move+buttons is not enough to identify a
    performance, so `MIN_LEN` exists and a pair below it is NOT COMPARED and is
    counted separately — a low score for a pair that could not have been judged is
    the same false reading as a high one.

  So `recsim.py` ships as a **census tool**, and it prints its own caveat when it
  fires ("THIS CORPUS CANNOT CALIBRATE A THRESHOLD — it holds no two genuinely
  independent runs of one map") rather than a bare OVERLAP that reads as "the
  metric failed".

  **THE FLEET CORPUS HAS NOW BEEN RUN, AND THE DISCRIMINATOR SEPARATES ON IT.**
  Measured 2026-10-05 on the Pi's `data/runs/` (64 `.rec`, fetched read-only; the
  recipe is in `tools/census/README.md`): 9 map/leg groups hold more than one
  comparable run, giving **20 negative pairs of genuinely independent posted
  runs**, and

  | | value |
  |---|---|
  | positive min (an exact replay) | **1.0000** |
  | negative max | **0.5866** |
  | separation | **CLEAN, margin 1.70x** |
  | negative max, SAME identity | 0.5866 (12 pairs) |
  | negative max, CROSS identity | 0.2146 (8 pairs) |

  The worst pair is `surf_utopia` 0004216 vs 0004224 — one install, two runs 8
  ticks apart in length, cover 0.0000 and prefix 0, agreeing on 59% of compared
  rows and sharing no contiguous opening at all.  So a gate at `match >= 0.95`
  sits 1.62x above the worst SAME-PLAYER pair and 4.4x above the worst
  cross-player one.  `recsim.py pairs` now prints that identity split itself,
  because which case was measured is a property of the corpus and not of the
  metric: the local corpus has **zero** cross-identity pairs, so every number it
  produced is a same-player-or-unattributed figure.

  **STILL NO THRESHOLD, and the reason has narrowed rather than gone.**  20 pairs
  is a small sample and only 8 of them are cross-identity, while the local corpus's
  376 pairs are contaminated by harness output as catalogued above.

  **THE SURFD SIDE IS NOW BUILT AND STORES RATHER THAN GATES** (schema 10,
  `surfd/simcheck.py`, `surfd/test_simcheck.py`, and a `similarity_step` in
  `sweep.py`).  It compares each submitted run against the other run-kind rows on
  its map/leg and stores `match`, `cover`, `prefix`, the identity split and — when
  a pair could not be judged — a named skip with its reason.  **Nothing in `VER_SQL`
  reads `sims`, no badge moves, no run is demoted and no public route exposes it**,
  exactly as schema 7's `receipts` table was introduced.  That is a deliberate stop
  short, not an unfinished one: the statistic separates cleanly and the SAMPLE is
  too small to pick a number from, so the sweep now accumulates the cross-identity
  pairs the calibration lacks from live submissions.  **What remains is the threshold
  and the decision to enforce it, and both need the accumulated sample rather than
  more engineering.**  `sweep.py --dry-run` prints the pending count and the split;
  `--sims 0` turns the step off.

  Note the identity is the 8-hex `FS_GuidId` in the filename (sha256 of the
  install's `qkey`), so it survives a rename and does NOT separate two netnames on
  one install: the fleet holds four identities and 53 of its 64 files are one of
  them.  `recsim.who_of` matches the trailing hex without requiring a dash, which
  costs an ambiguity (a netname ending in 8 hex characters reads as an identity)
  and reads the bare-id segment FS_PlayerSeg writes for a name that slugs to "",
  which a dash-anchored pattern reads as no identity.  The ambiguity is in the
  safe direction: it can merge two identities and so UNDER-report cross-identity
  pairs, never invent them.

  Also measured and worth keeping: the alignment offset is searched over the
  DIFFERENCE OF THE FIRST TICKS ±4 rows, and on all 25 synthetic positives the
  offset found was 0 — the epoch shift was absorbed with no row shift, which is
  what a playback does.  A wide search window was deliberately not used: a wide
  search finds agreement that is not there, the same mistake as a join window in
  the angle rules (`reccheck`'s `angle_lag` is read OFF the files for that reason).

- **THE TIMING ASSISTS HAVE NO DETECTOR, AND THE EVENT CLASSIFIER ALREADY
  EXISTS.** `Edgebug assist`, `Jumpbug assist`, `null strafe`, `Longjump`,
  `Pixelsurf` produce physics-LEGAL motion, so `pm_verify` PASSes them by design
  and the energy walk in `tools/p452col.py` finds nothing — no tick exceeds what
  strafing can produce. Repo-wide grep for
  `edgebug|jumpbug|null.?cancel|null.?strafe|landing precision|frame.?perfect`
  returns two hits, both in `cl_board.qc`'s `Board_Frame` comment, which is the
  Segments/gain DISPLAY and already holds the hard part: it grades the contact
  event and is calibrated ("the 25 u/s rule alone grades 84% of events perfect,
  because sustained surfing clips every single tick. The airborne-first gate in
  the engine is the real filter"). What is missing is the statistic that
  separates a human from an assist — SUCCESS RATE PER OPPORTUNITY, not per-event
  perfection — measurable from a kept `.rec` alone (`fl` bit 1 gives ground
  contact per tick, `vz` the approach), needing no `.hid` and no engine work.
  Falsifier: no tool in `tools/` prints a per-map or per-player landing success
  rate. **Blocked on a calibration corpus**, and per the tree's own rule a
  threshold from one framerate or one map is not a threshold.

  **SUPERSEDED BY THE MEASUREMENT BELOW, AND WRONG IN ITS PREMISE.**  The
  falsifier is now answered — `tools/census/assist.py` prints exactly that rate,
  per run and pooled, with a `control` arm.  But **`fl` bit 1 is NOT ground contact
  on a surf run**: Source sets FL_ONGROUND only on walkable ground and sliding a
  ramp leaves it clear, which is the whole mechanic, so only 45 of 5414 local files
  were judgeable on it.  The bit that works is 16 (`run_rampcontact`), written only
  by our server.  The fleet corpus then inverted the coverage (54 of 64 files carry
  ramp ticks, 27 runs judgeable, all reading 0.0000) and the remaining blocker is
  an assist sample that can be DRIVEN, which the CS:GO DLLs in `Cheats/` cannot be.
  Read the paragraph above as the proposal and the measurement below as what
  happened to it.

  **MEASURED 2026-10-05, `tools/census/assist.py` — the statistic is built and
  the premise it was filed on is falsified.** The proposal above was to read a
  success rate per opportunity off "`fl` bit 1 gives ground contact per tick".
  Over 5571 `.rec` files (5281 Momentum imports, 130 native, 157 with no rows)
  that does not hold, for three separately measured reasons:

  | the obstacle | measured |
  |---|---|
  | `fl` bit 1 is NOT contact on a surf run — Source sets FL_ONGROUND only on walkable ground, and sliding a ramp leaves it clear, which is the whole mechanic | 5369 of the 5414 files that have rows hold fewer than `MIN_OPP` 20 fresh-press landings; **45 are judgeable at all** |
  | and a landing is not a jump opportunity | of 9855 ground-bit landings with no jump held beforehand, **9122 (92.6%) see no press within 40 ticks** — on a surf map you land and keep going |
  | bit 16 (`run_rampcontact`) IS the signal that would work, and only our server writes it — a `.mtv` records no contact plane, so `momreimport.py` says "Never 16" | **101 of 5571 files have one ramp tick, every one native**; 90 hold such a landing; 16 delays total. The corpus with the signal has no players, the corpus with players has no signal |
  | the null observable is not the one assumed | `keys` is DERIVED from the move signs by both writers (SV_RecKeys; momreimport applies "the same rule"), so FSI_LEFT/FSI_RIGHT are mutually exclusive by construction and an overlap check reads perfect for everybody. Corollary, measured: `fl` bit 4 and `keys` FSI_JUMP agree on **every row of all 5571 files** — they are both `e.button2`, so a `.rec` carries ONE witness for a jump, not two |
  | and the null observable that does exist does not separate | clean-switch rate over 4237 judgeable runs: median 0.9038, p95 1.0000, and **364 runs (8.59%) read exactly 1.0000** (native 4 of 60). A gate at 1.0000 false-accuses one human run in twelve |

  This is cheatanalysis Finding E's self-referential trap one layer over, and the
  `keys` half was caught before the tool was written rather than after.

  **THE ONE STATISTIC WITH COVERAGE NEEDS NO GROUND BIT.** The jump impulse is
  visible in `vz` alone: over 200 files, 255,592 upward steps form a sharply
  bimodal distribution — 89.6% below 150 u/s (a ramp converting horizontal to
  vertical), **a spike of 16,428 in the 275-300 bucket alone** (`pm_jumpvelocity`
  ~289 added in ONE tick), 3,847 above 320 (boosters, pads, teleports).
  `assist.py steps` prints that histogram, so `HOP_MIN`/`HOP_MAX` are a measured
  cut placed in the valley. Interval regularity over it reads **min 0.5487,
  median 0.9130 on 204 judgeable human runs against 0.0000 for a synthetic
  periodic chain** — wide-looking, but it bounds separation from ONE side only:
  no real assist sample exists in this tree, and a timer-driven assist still has
  to react to terrain, so its cv is not 0. Treat 0.5487 as the human floor.

  **A FALSIFIED EXPLANATION, kept because it is the reason no gate was written.**
  73 of the 733 landings that do see a press arrive within 2 ticks — far faster
  than the ~150-250 ms (10-17 ticks) a reaction to an unanticipated contact
  needs — and 46 runs (1.30%) contain one. I predicted jump MASHING: a player
  spamming the key lands with it already down often enough to look frame-perfect.
  `assist.py delays` buckets runs by the fraction of ticks jump is held, and the
  prediction is BACKWARDS — the fast rate is **32.9% in the 0-5% bucket against
  0.68% in the 75-100% one**. Two explanations survive and neither is tested,
  because there is no assist sample to test against: (a) a selection artifact of
  the autobunny exclusion (landings during a tap are removed, so what remains is
  biased toward "the tap starts just after this contact"); (b) a PREDICTED press,
  timed to a landing the player can see coming, which has no reaction delay and is
  legitimate play. Both say the same thing about a gate: a small delay is ordinary
  human play, so delay cannot accuse.

  So the falsifier above is now answered — `assist.py` prints a per-run and a
  pooled landing rate — and it prints the coverage beside it, because the honest
  reading is that **45 of the 5414 files with sample rows can be judged on
  landings, and not one Momentum run can be judged on ramp contact at all**. `control` rewrites a real run into an assist-shaped
  one and asserts each statistic reaches 1.0000 (and the periodic chain cv 0), so
  a zero in the output reads as coverage and not as a broken statistic.

  **THE FLEET CORPUS INVERTS THE COVERAGE PROBLEM, AND THAT IS THE FINDING.**
  Measured 2026-10-05 on the Pi's `data/runs/` (64 `.rec`, all native; recipe in
  `tools/census/README.md`).  The local obstacle was that bit 16 is written only
  by our server, so the 5281 Momentum imports carry none of it and the corpus
  with the signal had no players.  The fleet is the other way round:

  | | local `ftesurf/data` | fleet `data/runs` |
  |---|---|---|
  | files with a ramp-contact tick (bit 16) | 101 of 5571 | **54 of 64** |
  | runs judgeable on `land(bit16)` | 90 | **27** |
  | their frame-perfect-landing rate | — | **0.0000, every one of the 27** |
  | runs reading `null` exactly 1.0000 | 364 of 4237 (8.59%) | **4 of 57 (7.02%)** |
  | hop-interval cv floor | 0.5487 | **0.6023** |

  So **on this game's own runs not one honest landing out of thousands was
  frame-perfect**, and `null` is still unusable as a sole gate (7.02% of honest
  fleet runs read exactly 1.0000, matching the local 8.59%).  `control` now
  proves the bit-16 statistic is LIVE rather than dead on a fleet run
  (`surf_4am`, 19132 ticks: **146 ramp-contact opportunities, 0.0000 as
  recorded, 1.0000 rewritten assist-shaped**), which it could not do before —
  `synth_assist` only rewrote bit 1, so the control exercised `landg` and said
  nothing about `landr`, the one statistic that actually has coverage here.
  Its auto-search also only accepted Momentum files, so on a fleet corpus it
  printed "no source run" and returned 1: **the control arm was unusable on
  exactly the corpus that has the ramp coverage.**  It now falls back to native,
  prefers a source that exercises BOTH landing bits, and qualifies its own
  verdict (`EVERY STATISTIC THAT RAN, FIRED` plus a NOT-EXERCISED list) rather
  than printing a green beside a statistic nobody has seen fire.

  Still no threshold and no surfd code.  **The blocker has moved from "there is
  no corpus" to "there is no assist sample that can be DRIVEN"**: 27 judgeable
  fleet runs all read 0.0000, so the human side of the cut is measured, and the
  cheat side is not.  **The samples exist and cannot be run.**  The private
  `Cheats/` corpus holds `movementoptimizer_hotguyyy69`, `movementoptimizer_yifed256`
  (each a `shithop_[unknowncheats.me]_.dll`) and `strafeoptimizer_Tokyodidit`
  ("Tranquility", the one the `Edgebug assist` / `Jumpbug assist` feature names
  came from), and every one is an IN-PROCESS DLL FOR CS:GO — its own
  `webpagetext.md` says to inject it into CS:GO with `-disable_d3d9ex`.  There is
  no way to inject one into this client and no headless harness can drive it, so
  the feature list is documented and the behaviour is not measurable here.  What
  would unblock a cut is a native FTESurf/Momentum assist someone can run against
  a lobby; a synthetic assist-shaped `.rec` (which is what `control` builds) proves
  the statistic fires but is the author's model of a cheat rather than a cheat.
  Until one exists, any cut is one-sided, and the tree's own rule says a threshold
  from one side is not a threshold.

- **`reccheck`'s key-mask check is self-referential.** It derives `want` from the
  `fwd`/`side` columns and compares to the direction bits of `keys`, which reads
  as a cross-check of two independent facts and is not one: the server reads both
  out of the one received usercmd (`SV_SetEntityButtons(ucmd->buttons)` beside
  `xv->movement[] = ucmd->forwardmove/…`), and `sv_timer.qc`'s own comment over
  the writer says so in terms. A client that reports movement with NO matching
  button — the shape an optimiser that writes `sidemove` and leaves `buttons`
  alone produces — passes it, correctly. It catches a corrupted or hand-edited
  FILE. Now commented as such at the check site; the independent ground truth for
  buttons is the `.hid`'s `+`/`-` scancode events, and nothing compares them to
  the `.rec`'s `keys` column either. Falsifier: hand-edit an `in` row's `keys`
  to contradict its `fwd`/`side` and watch reccheck fault, then hand-edit the
  `.hid`'s button events to contradict the same row and watch nothing happen.

- **RESOLVED 2026-10-05: `hidcheck.py`'s sign comment was wrong and no longer
  exists.** It said "The sign convention is the OPPOSITE of what it looks like:
  mouse_x is positive to the right and a positive dx should turn the view RIGHT
  (increasing yaw), so the identity is `dyaw == +k*dx`, NOT `-k*dx`." Measured
  over two real PBs, `dyaw == -k*dx` gives 0 violations against 38,744 for
  `+k*dx`, which is what the engine does at `IN_MoveMouse`
  (`viewanglechange[YAW] -= m_yaw * mouse_x`). The CHECK was always right; only
  the comment misleads, and a future reader "fixing" the check to match its own
  comment would break the tree's flagship input check.  **Patch 484 corrected the
  comment as part of shipping the pitch axis**, so `grep -n "positive to the
  right" tools/hidcheck.py` now returns nothing — the item is closed, and it
  stays here only as the shape to watch for: a comment that contradicts the code
  beside it is a defect with a long fuse.  Falsifier, still re-runnable:
  `tools/p484ident.py` Part 2, which sweeps all eight (angle, key, count, sign)
  combinations.

- **RESOLVED 2026-10-05: the `f`-record split is not a mystery, and half of this
  item was wrong.** It read: 61 of 123 journals have zero `f` records, the empty
  half includes "THREE real gameplay recordings", and "the two counters do not
  agree about what a frame is". All three claims were checked and two are false.

  THE MECHANISM, from the call site: `IN_Journal_Frame()` is called in exactly one
  place (`in_generic.c`, inside `if (events_used != events_available)` in
  IN_Commands' drain loop), so **`f` is written if and only if a device event was
  drained that frame.** Its own grammar line already says so ("a drain of
  IN_Commands began") and the header comment names a file with no rows "a journal
  of nothing happening". The census follows exactly: files split **61 zero-`f` /
  62 with-`f`, and the split is identical to "has any device-event record at
  all" (`m`,`+`,`-`,`a`,`x`,`j`,`d`,`g`,`b`) with zero exceptions either way** —
  the 62 have 34-6830 `f` rows, the 61 have none and no device events either.

  THE FALSE CLAIM: `0000007_pb.hid`, `0000008_pb.hid` and `0000009_pb.hid` are not
  gameplay recordings. They are 2130-byte files whose own trailer reads
  `end 143712 0.143748 0 0 ...` — a **0.14-second session, 0 events, 0 frames, one
  `v` row**, with a ~6 KB `.rec` beside them. Stub runs. Naming them "real
  gameplay" is what made the split look unexplained; the half that has no device
  events is the half where no device was read.

  THE TWO "FRAMES" COUNTERS ARE TWO DEFINITIONS, not a disagreement, and the
  relation between them is exact:

  - `end <dt> <abs> <events> <frames> <dropped> <hidden>` — **`frames` counts
    DRAINS, i.e. `f` rows.** Verified: `p484_B.hid` has 678 `f` rows and its
    trailer says 678.
  - `in_jrn484_frames` counts VIEW SAMPLES THE IDENTITY GOVERNED, i.e. `v` rows
    minus the abstentions. Verified: `p486_B.hid` has 182 `v` rows and
    `ftesurf/logs/p486injrn.log` reads `"in_jrn484_frames" is "181"` with
    `in_jrn484_skipped` 0 — the difference is the first view, which
    `IN_Journal_CheckIdentity` returns on before `vcount++` (`!in_jrn_vhavelast`).
    So **`#v == in_jrn484_frames + in_jrn484_skipped + 1`** whenever no abstention
    arm fires, and `CheckIdentity` sits above the `v` write and below the
    quiet-frame return, which is what makes the identity hold per row.

  **What survives of the original worry, and it is smaller than stated:** a check
  built on `f` covers only journals where a device was read — but that is the
  population a device check is about, and `tools/hidcheck.py` already reconciles
  the trailer against the body (`end`'s events/frames/dropped/hidden against the
  `+`/`-`/`f`/`!` rows) and treats a missing `end` as an unclosed file rather than
  as clean. So the "clean-by-absence" shape this item feared is already covered by
  an existing check. Falsifier, still re-runnable: a Counter over the first token
  of every `.hid` in `ftesurf/data/`, split on whether any device-event token is
  present, must equal the split on `f`.

- **TWO INTUITIVE PLAYBACK STATISTICS ARE MEASURED DEAD, and they are written down
  here so that the next session does not re-propose either.** Measured 2026-10-05
  over the fleet corpus (63 `.rec` files fetched read-only from the Pi's
  `data/runs/`; 436,110 derived moves, 446,897 yaw deltas). Both are the first
  answer anyone gives to "how do we see a playback from evidence the server wrote",
  and both are wrong on real players. The scripts are private
  (`cheatanalysis/dtcensus.py`, `cheatanalysis/yawstat.py`) on the rule that a
  NEGATIVE result belongs beside the document that proposed the direction, not
  beside the tools that get run on cron.

  - **COMMAND CADENCE / PERIODICITY — DEAD, and a gate on it would accuse seven
    players in ten.** A playback only reproduces if its cadence matches the
    recording, so a pinned frametime looked like a signature. The per-move
    frametime is derived exactly (`(mt[i+1]-mt[i]) * movetickrate +
    (carry[i+1]-carry[i])`; the grammar block over `SV_RecOpen` in `sv_timer.qc`),
    and its coefficient of variation is **EXACTLY 0 in 44 of 63 honest runs
    (69.8%)** — p50 0.0000, p75 0.0044, p95 0.0427, max 0.1651. A constant
    frametime is the NORMAL state of an honest run, because a client at or above
    the tick rate builds one usercmd per rendered frame.
    Two traps for whoever re-runs it. "Exactly one tick per move with an unchanged
    carry" is one spelling of periodicity and reads as its ABSENCE in another:
    five files score frac 0.0000 *with* cv 0.0000 because that client runs BELOW
    the tick rate and the carry moves every move — so cv(dt) is the statistic and
    frac is detail. And break the epoch on `dmt <= 0 or dmt > 8`, not on `dmt < 0`:
    a Multi-Session resume jumps `mt` by thousands, and one such row produced the
    two most quotable numbers of the first run (p100 frac 1.3306, p100 cv 33.38),
    both of them artifacts of the parser rather than of any player.
  - **TURN ROUGHNESS — DEAD, with a control that fired first.** An optimiser's
    turn is a deterministic function of the run's own speed, smoothed and
    quantised to integer device counts, so its per-move yaw delta should read as a
    sampled curve where a human's reads as a sequence of corrections. The
    statistic (`mean|d[i+1]-d[i]| / mean|d[i]|` over per-move yaw deltas, needing
    only the server-written `in` rows — no `.hid`, no `.view`, no join between two
    differently-sampled streams) does not separate: a reimplementation of the
    published optimiser loop scores **0.1256 at full gain, between human p25
    (0.1063) and p50 (0.1410)** — about a third of honest runs are SMOOTHER than
    it — and **0.3044 at quarter gain, rougher than the human median**, i.e. it
    INVERTS with the tool's own preset. The reason is structural rather than a bad
    choice of statistic: an optimiser with gain and power presets produces a family
    of turn traces that spans the human range. The one column with any gap is the
    sign-flip rate (control 0.000–0.001 against human p0 0.0042), and a p0 over 62
    files is a minimum, not a distribution's edge — a note at most, never a gate.
    Falsifier for both: re-run either script over a corpus that contains a real
    playback and watch neither move it out of the honest range.
    Anything aimed at that class has to use the hard evidence — the `.hid` angle
    identity (built, Patches 484/486) or the move columns (next item).

- **THE MOVE COLUMNS ARE PINNED TO NO CONFIG, and Patch 493's bound is a constant
  for want of one.** `run_movebound 2000` is a judgement over a corpus, not over a
  rule: the four cvars that produce a move value (`cl_forwardspeed`,
  `cl_sidespeed`, `cl_upspeed` and the `cl_movespeedkey` multiplier) are ordinary
  ARCHIVED client cvars, so a player may set them and nothing in the run says what
  they were.  The ranked input profile is the mechanism that already solves this
  shape of problem -- `cl_replay.qc`'s `Rec_InputCvar` reads a named cvar and
  refuses the run when its value is not the recorded one, and `IPH_*` is
  RAW|FILTER|ACCEL|GRANT over four of them (`in_rawinput`, `m_filter`, `m_accel`,
  `in_rawmice`).  Adding the four move cvars would need a fifth bit, a fifth
  column in the `inprof` header key and the client-side refusal, and then a move
  value could be judged against the config the client itself reported instead of
  against 2000.
  **WHY IT IS NOT DONE, and the reason is a measurement rather than a preference:**
  over 1,342,728 axis values in 63 fleet runs the maximum is EXACTLY 450 with zero
  exceptions, so the fleet is uniform today and a profile pin would refuse nobody --
  which is also why nobody can say what a refusal would cost.  Patch 493's marker
  is the instrument that answers it: if `moveoor` counts stay 0 while `worst` starts
  appearing above 450 in `cmd timer` readings or in the header cross-check's
  `worst` column, that is an honest population the constant is wrong about, and the
  pin is what fixes it.
  **ONE ROUTE IS UNBOUNDED AND NO CENSUS HAS SEEN IT.** A gamepad with `+speed`
  held reaches `450 * 360 * cl_movespeedkey` before the wire bound stops it at
  32767, because `in_generic.c`'s IN_MoveJoystick scales jstrafe by
  `360 * cl_movespeedkey` and then multiplies by `cl_forwardspeed` without
  re-normalising.  No joystick player appears in the fleet corpus, and "none in 63
  files from four identities" is not "none" -- it is the specific case a profile
  pin would settle, since a pin turns that route into a stated config rather than an
  accusation.  Falsifier: a player on a gamepad with `+speed` whose run reads
  `over > 0` and `moveoor 1` while being entirely honest.

## Ranking integrity

- **momwatch's import holds surfd's write lock past its 5 s timeout every 7
  minutes, so a run submitted then is lost** (2026-10-04, from the re-import's
  deploy review; measured in surfd.log). `database is locked` lands on every
  `*/7` tick (04:21, 04:28, 04:35 ...), 2-4 a tick: 229 heartbeats and one
  assignment lookup in the retained logs, no submission yet only because nobody
  plays. Each tick `momboards --go --link` sets ~1200 board rows in one
  transaction. A `/api/run` in that window gets a 500, and the lobby does not
  retry -- it tells the player the run is saved on this machine (sv_lobby.qc
  2680-2701) -- so it never reaches the board. Fix: commit momboards' rows in
  small batches (and the link pass incrementally), and let the lobby retry a
  submission surfd refused with a 5xx.
  THE LINK PASS HALF IS DONE (808756b, live 4 Oct 09:31 UTC): its UPDATE scanned
  2.35M rows inside the write transaction (6.2 s); it now reads first and
  writes only the rows it links. STILL OPEN: `flush()` (momboards.py:112-134)
  sets a tick's board rows in one transaction. The link pass's final review
  measured, on the PC, 20,000 rows (16,000 landing) holding the lock 1.83 s
  with a heartbeat beside it waiting 1.49 s, and unchanged rows cheap (20,000 in
  0.37 s); the Pi ran the old link UPDATE ~4.6x slower than the PC, so a tick
  that lands ~10k rows could pass 5 s there. Ticks set 1100-1800 rows today.
  MEASURED ON THE PI, surfd.log: 9 `database is locked` on 4 of the 6 ticks
  08:56-09:28 UTC with the old link pass; 0 on the 8 ticks 09:35-10:21 after
  it (1095-1212 rows each). Eight ticks is not many -- recount after a day.
  THE BIG TICKS ARE A BACKFILL'S: momwatch.log holds 200 ticks of 4,000+ rows
  (max 13,078), all 28-30 Sep, none since 1 Oct. A new batch of boards would
  bring them back -- batch flush() before widening --want or --backfill.
- **`noclip` is open to every player on the lobbies** (pre-existing; Patch 478
  round-8 integrity review, traced in the engine). The engine's `noclip`
  (Cmd_Noclip_f) refuses unless SV_MayCheat -- `sv_cheats`, or a one-slot
  server -- but the mod's SV_ParseClientCommand takes every client command
  first (PR_KrimzonParseCommand) and its own `noclip` branch toggles with no
  gate and never hands the command back; its comment calls the branch dead
  code. Noclip marks the attempt (SV_NoclipWatch), but every arm re-reads only
  the movetype: noclip to 1000-2000 u/s, off just short of a START or STAGE
  box, coast through, and the start is CLEAN at that speed. Since 478 r8 the
  stage handover carries the taint; a box entered from outside still clears
  it. Fix (Patch 479): hand `noclip` to the engine's gate (clientcommand), and
  tag noclip let go of faster than a walk as a fast idle load is; AGENTS.md's
  harness note ("each noclip is processed twice") changes with it.
  THE PIN HALF IS CLOSED (Patch 499): SV_WatchHoldMove re-imposes MOVETYPE_NONE
  from both thinks, so a pinned body cannot be left in noclip and SV_NoclipWatch
  cannot mark a frozen, recording run cheated (measured both ways,
  cfg/test/p477rewind.cfg R28A/R28B: `noclip 1` and `class: cheated` on the
  control build, `noclip 0` on the fixed one).
  WHAT THE 477 REVIEW FEARED BESIDE IT DID NOT REPRODUCE: "a body can creep
  through a stage with the clock frozen" -- measured 0.0 u over 900 ms of
  `+forward` with noclip ON, because the client sends an EMPTY usercmd while
  browsing (cl_main.qc's `rw_on && !rw_cd` branch) and SV_WatchFrame zeroes the
  velocity every packet. The exposure was the taint, not the distance. What is
  left here is the gate itself.
- **A ghost skips cancel zones on a running run** (pre-existing; Patch 478 round-2
  integrity review, code-read). SV_TimerFrame's ghost branch returns before the
  zone scan, so a body coasting unattended through a cancel zone keeps its run;
  the run is TF_GHOST-marked, and TF_GHOST is not in TF_UNCERT. 478 stops a
  ghost STARTING a clock; a cancel the ghost crosses should still void (a
  swept test of the ghosted ticks' own segments, which SV_TimerWarped already
  keeps one tick long). The same holds for a START the ghost crosses whole:
  since 478 r7 an unghost inside a START ends the run, but a window that spans
  the crossing skips its cancel as before.
- **The server trusts the client to empty a ghost's moves** (pre-existing; Patch
  478 round-6 integrity review, code-read). The mod defines no
  SV_RunClientCommand, so only `cl_ghost.qc`'s Ghost_InputFrame sends empty
  moves; a modified client steers its ghost with the camera detached. Off the
  clock nothing is judged or recorded -- since 478 r6 the unghost arms no box, so
  what that buys is the "cheapest prespeed route" below; on the clock pm_verify
  HOLDs a ghost window whose rows carry input (Patch 373), and the cancel entry
  above is the gap. Fix: the engine zeroes a ghost's usercmd while
  STAT_FS_GHOST is set.
- **A finished stage run's next box is policed only for a body whose point
  arrives after the finish -- a decision for Lex** (pre-existing; Patch 478
  rounds 7-11, code-read). SV_TimerJumpWatch judges a hop only while ARMED or
  RUNNING. A point that reaches the next box a packet after the hull fired the
  finish (a slow side entry, a rise from below) is armed there by
  SV_TimerTryArm and hop-checked, as before 478; a point that arrives in the
  finish packet -- a drop from above, a teleport, or any entry fast enough for
  the packet: ~1070 u/s at one move a packet, ~360 at three (`cl_c2spps`), or a
  ghost held across the boundary -- leaves the body FINISHED until the hull
  exits, and the handover sets `startok` (Build 20: a stage run begins in
  flight), so a chain bhopped in that box starts the stage clean at its speed.
  Both ways cost: hop-checking every handover (say, a body that stands on the
  ground in the box) closes it, and also tags an honest land-and-hop on
  teleport-staged maps and every chained stage on a bhop map played off-lobby
  (the bhop lobby runs `run_starthop 0`) -- with a tag that is sticky to `!r`.
  The point's arm already does that to slow entries, as it did before 478.
  Both arms carry what reached the entry one boundary (SV_TimerHandArm) --
  but only while the handover stands: a retry of a FINISHED body, a ghost that
  leaves the box or enters it, each drops it with the speed kept, and the next
  entry is a plain arm (round-12 integrity review; no gain beyond the entry
  below). Fix: arm a stage run's next box (its track, startseg + 1) through
  SV_TimerHandArm whether or not the handover survived, and let a fast
  FINISHED load set the segment bit.
- **pm_verify's start latch is not refreshed at a `ghost 0`** (engine; Patch 478
  round 8). The live unghost takes the START latch of where the body stands
  (SV_TimerGhostEnd) and keeps the event latches, as the verifier does (round 7
  took both and the verifier HELD a finish at re-attach); a ghosted run that
  ends in START prints "re-enters this track's START" on its PASS (sv_ccmds.c).
  A note, not a verdict -- refresh `vf_azone` at the record.
- **A lobby flip inside a resume phase strands the claim file** (pre-existing;
  Patch 478 round-6 integrity review, PLAUSIBLE -- needs an operator flip
  mid-countdown). SV_MsClaimLeaf and SV_MsKey change with Lobby_Active(), so
  after a flip SV_MsApply's read of the claim fails and SV_MsAbort renames a path
  that does not exist; the real claim stays, and the next park (`ms_posts 0`)
  wipes its `run.rec` -- posted-stage evidence lost. The body is safe
  (SV_MsAbortHere). Fix: latch the claim's path at the accept.
- **A second connection on one guid can wipe a claimed resume slot** (pre-existing;
  Patch 478 round-4 integrity review, PLAUSIBLE -- whether a lobby admits two
  clients on one guid is unchecked). While A1 holds the claim, A2's `!discard`
  (SV_MsDiscardOffer) or A2's park on a drop (SV_MsPark) finds no `ms.txt`,
  leaves ms_posts 0 and SV_MsWipeDir deletes `run.rec` without Patch 360's move
  to data/evidence -- posted-stage evidence lost, across lobbies (data/resume is
  shared); A2's park also leaves its state.txt under A1's claim. Fix: any
  `ms.*.txt` claim file means the slot is busy, in both.
- **`retry` never reopens the stage in progress** (pre-existing; Patch 478
  round-2 review, code-read). PutClientInServer runs SV_TimerSpawn, whose
  SV_TimerIdle sets `run_st_seg = -1`, before SV_RetryApply, and
  SV_SaveApplyState reopens a stage only `if (e.run_st_seg >= 0)`
  (sv_saveloc.qc) -- dead on a retry, and on a save-lock load from IDLE or
  ARMED. No stage is open, and the fail rule is off, until the next boundary.
- **A map's player gravity can follow a run out of the area that set it**
  (pre-existing; Patch 477 round-11 integrity review, PLAUSIBLE, map-dependent,
  not driven). `.gravity` written by map I/O (sv_entities.qc) is reset only in
  PutClientInServer, and nothing at a run's start reads it, so `!r`, a load or a
  rewind resume out of a low-gravity area can start a run that ranks at that
  gravity -- on maps that restore gravity with a separate exit trigger rather
  than the same trigger's OnEndTouch (which still fires after a teleport). Fix:
  reset `.gravity` (and `run_speedmod`) in SV_ZoneMoveAt and SV_SaveLocPlace, or
  make any start with a gravity multiplier other than 1 practice.
- **A RUNNING, ARMED or FINISHED load's speed is policed only by its file's
  `hopped`, and a start box re-entered from it can arm clean** (Patch 436's "load,
  step out, run"; predates 477, and 477 makes no such save). Patch 477 round 3
  tagged any load faster than a walk, running ones included; round 5 took the
  running half back, because on bhop-mode maps a start box entered from RUNNING
  or FINISHED arms only through the jump commit (sv_timer.qc SV_TimerTryArm's
  deferral), so `startok` stays set, Patch 454's rest test never runs, and
  honest save-state practice came out practice until `!r`. The real fix needs
  that deferral to run the rest test -- which is Patch 455 round 1's fix 5, on
  the unmerged `p455fix` branch (below). Idle loads (every rewind resume
  included) are still tagged above a walk or a jump.
- **Speed the map still owes lands in an armed start box after `!r`, a load or a
  `setpos`** (predates 477; Patch 477 round-5 integrity review, traced, not
  driven). A pad's OnEndTouch fires ~0.06 s after the body leaves even when it
  was teleported away, and delayed outputs keep the player as activator;
  `!activator AddOutput basevelocity` then pays into `.velocity` inside the box
  after `!r` zeroed it, `run_startcap` is 0 on the lobbies, and `run_pushed`
  excuses the hop. Fix: at those warps, drop the player's pending
  `vbsp_iodelay` and their touch bits, or clear the carrier for a window as
  SV_SaveLocHoldFrame does. Patch 477's load-at-rest forgiveness is skipped
  while SV_TrigPending is non-zero; `!r` has no such check. A load's hold does
  not cover it either (477 round-16 integrity review): delayed outputs fire in
  SV_Physics, after PostThink's SV_SaveLocHoldFrame, so one fired the frame
  before `sl_holdoff` -- a rewind countdown's release included, which a
  modified client times -- is cashed out on top of the handed-back speed. That
  path's fix is one SV_ClearCarrier in SV_SaveLocRelease, as SV_WatchRelease has.
- **PATCH 455 IS NOT MERGED, AND AGENTS.md TALKS AS IF IT WERE.** Rebased onto
  e7b6562 on 5 Oct as one commit, branch `p455rebase` (50affaa) on origin; the
  ten rounds are tag `archive/p455fix-r10`. AGENTS.md's "LATENCY BOUND"
  paragraph and the gate fixes it describes are not in the shipped Patch 454
  block: the carrier term, the vertical carrier and the `.maxspeed` cap are all
  still 454's, and 454's check sits inside `if (!e.run_t_startok)`, so it never
  fires on bhop maps. NOT READY TO MERGE: 44b313b's own message ends "the dwell
  does not close the bank it was built for, which is round 11", and no round 11
  exists; the rebase's reading (not driven) is that a write made inside the
  packet that grants the forgiveness has no wait at all. Lex's call: finish
  round 11, or cut the patch to round 1's fixes (right field, the mover's cap,
  the check out of the start block, refuse held or rising bodies) and review
  that.
- **Patch 454's carrier term reads `run_basevelocity`, which is always zero there.**
  The finish forgiveness adds `e.run_basevelocity` to `.velocity` to judge "no
  prespeed to launder", but the engine zeroes that field at the top of every move
  (sv_user.c:8577-8581) -- the latched carrier is `run_basevel`. So a body riding
  a push carrier at a low `.velocity` reads as walking. Found by Patch 477's
  round-1 integrity review; not changed there (it needs its own arm on a push map).
- **A thaw past an unrecorded freeze is still reachable**, and convicts a practice
  run's angles (the held-run fault): closing the replay viewer mid-run, `retry`
  or a Multi-Session park under it, and letting go of a save-lock hold. Patch
  477's rewind no longer takes it (ESC resumes at the head, a refused resume, a
  retry, a park or a lobby flip ends the run). The systemic fix is a `pause`
  record at the thaw, so reccheck abstains.
- **`!r` keeps the replay pin** (sv_zones.qc releases only the save-lock hold), so
  a run started after it is frozen at its first tick and practice (Patch 477's
  start taint) until the replay closes. Costs the player, never ranks.
- **A rewind whose pin the server refuses leaves up to a round trip of dead
  input** (Patch 477 rounds 12-13). The client zeroes moves and swallows the mouse
  from the open; when the server refuses the pin (a run that started since the
  ask), the mode closes only once the client's state or line check sees it, so
  a fresh clean run can begin with ~1 RTT of no input -- a hop chain's start
  breaks. Gating input on the pin's serial being seen trades it for an RTT of
  free movement under the cursor camera in the normal case. The run identity the
  server checks is the client's TIMERTICKS: a run cancelled within its first
  round trip and replaced by one that out-ticks it before the pin lands would
  still be taken -- a run serial stat would close that.
- **A `setpos` on a run that posted a stage makes its kept file unverifiable**
  (pre-existing; Patch 477 round-19 evidence review, traced). SV_TimerCheat
  taints the run but the recorder runs on, `setpos` writes no `warp`, and a run
  that posted a stage is kept as evidence (SV_RecKeepEvidence); surfd indexes it
  whatever its class and pm_verify HOLDs at the teleport ("packet(s) differ"),
  which abandoned_pass does not convert -- so the honest stages it backs never
  show Verified. `setpos` should write a `warp`, or end the recording.
- **The avatar name field swallows every key-up while it has focus**
  (pre-existing; Patch 477 round-24 review, code-read). Av_InputEvent
  (cl_avatar.qc) returns TRUE for any release, so a `+sl_hold` or movement
  key held into the field keeps its hold or motion -- the chat draft's
  round-24 rule (swallow only the releases of presses it took) applies.
- **Whether a client can claim another player's guid is unchecked** (Patch
  477 round-24 integrity review). The engine takes the guid from the connect
  packet (sv_main.c), and save folders, resume slots and rings key on it;
  whether the lobbies' certificate binds it was not traced.
- **A press the engine console or a menu took acts on its first auto-repeat in
  the rewind** (engine; Patch 477 rounds 18, 26, 27, CONFIRMED by trace). CSQC
  gets no KEYDOWN while key_dest is not game (keys.c), so neither Rewind_Track
  nor Chat_Track marks the key down: ESC held past the repeat delay after
  closing the console with it reaches the rewind as a leave (a go at the head
  on a running run), and a first repeat can be an unasked S save or scrub. The
  engine already drops the UP of a key CSQC never saw go down (pr_csqc.c
  csqckeysdown); it should drop its repeats too. Both tables keep one state per
  key, not per device: with `in_rawinput_keyboard 1` and a second keyboard, a
  key held through an alt-tab loses its release (the focus-loss release covers
  device 0) -- its next press in the rewind is swallowed once, and a chat
  bind's reads as a repeat and opens the engine's prompt (PLAUSIBLE, not tried
  on hardware).
- **A demoted save no longer restores its HUD Segments column** (Patch 477 round
  9's trade-off): a demoted row's load reads no snapshot or seq.txt, because a
  rewind row's reused id made either another save's. A keep-window demote's file
  really is its own; telling the two apart needs a `rewound` bit on the client.
- **A frozen park's `pause` and a frozen finish's `inend` still write the live
  mover counter** (Patch 477 round-11 evidence review). Round 10 made a frozen
  KEPT abandon's `inend` the counter at the freeze; SV_RecParkLine (a replay-pinned
  run parked by a drop, rotation or shutdown) and SV_RecClose (a pinned body moved
  into END by a map warp or noclip) do not, so the grammar's "the closing horizon,
  as `inend`" now disagrees between writers for the same state. Practice runs
  only.
- **pm_verify flies a pinned row as PM_NORMAL** (Patch 477 round-16 evidence
  review; traced, not driven). A pin's stringcmd runs before its packet's moves
  (sv_user.c:9719), so the server moves them PM_NONE, but the freeze latches
  after them, and pm_verify replays them PM_NORMAL from the `warp ... pin` state.
  A pinned body still touches triggers: a continuous push re-arms the carrier on
  the first move and `ride arm` hands it to the next, so a pin packet of two or
  more moves (43-65 packets/s against 66.67 Hz) flies 15-45 u a carried move in
  the replay for a 1000-3000 u/s booster, plus input and gravity (~1 u a move). In a rewind-frozen
  kept abandon that packet is the file's last, so the final zone scan and the
  physents checks are taken where the body never was: a HOLD on honest stage
  evidence (sweep.py passes only `no finish` and a last-row cancel). Fix, engine:
  fly a row with <fl> bit 4 inside a freeze (from a pin or hold to `inend`) as
  PM_NONE, in pm_verify and pm_recsim -- not keyed on the `pin` warp, which a
  body at rest does not write (round 16).
- **A warp writer imposes before SV_RecWarp, so a pending Multi-Session seed is
  the imposed state** (pre-existing; Patch 477 round-17 evidence review, traced,
  not driven). SV_RecWarp's SV_RecSession writes the `session` and its seed from
  the body as the writer left it, but the grammar imposes a floor-window warp ON
  the seed: a `!r` (`zone`) or a map teleport in the first packet after
  SV_MsApply makes pm_verify HOLD "session N resumes ...". Round 17 seeds before
  the pin's zero; the other writers are as they were.
- **A freeze's release packet counts as frozen whatever its ticks** (pre-existing;
  Patch 477 round-17 integrity review, PLAUSIBLE, not traced to a posted time).
  SV_TimerFreezeFrame's zero-drift proof assumes the pin's packet and the
  release's carry equal ticks, and a modified client picks both; a stage opened
  inside the release packet re-reads its taint from the live state
  (SV_StageOpen). A replay pin or save-lock hold taken in a ~0-tick packet before
  a boundary and released in a full one across it might open a clean stage short
  by part of that packet. Unread: crossing-tick interpolation, the engine's msec
  caps, pm_verify's stage-slice checks. Round 19 found a trigger that fix would
  miss: a replay pin (`rec_watch 1`, no `rw`) on a staged run, then `!r` --
  SV_TimerRestartSeg's SV_StageOpen recomputes run_st_dirty from the movetype,
  and MOVETYPE_NONE reads clean, the pinned body held in the stage box -- then
  `rec_watch 0` in a packet carrying the usercmd budget (500 ms, sv_user.c:8179)
  with moves that walk out: the stage starts on a frozen tick, short by the
  packet, and SV_StageQualifies has no pin refusal as it has run_st_sp. The
  rewind's pin voids at a `!r` that moves the body (one that lands where it
  stood leaves the frozen run, which every way out of the rewind still ends,
  and a frozen clock posts no stage). Fix: latch the thaw at the release
  command rather than at PostThink, or a run_st_pin refusal beside run_st_sp.
- **A `retry` or a second keep under one runid overwrites
  `data/evidence/<runid>.rec`** (pre-existing; round-11 evidence review).
- **The ghost and the replay pin refuse each other one way only**
  (pre-existing): SV_GhostSet refuses under the pin, SV_WatchHold never refused
  under the ghost. With 477 a modified client's `sl_saveat ... go` under the
  ghost loads with no countdown (the hold refuses the ghost); no ranking effect --
  the idle load is still tagged on speed. A server refusal needs the client's
  Watch_Open to refuse too, or the replay opens over an unpinned body.
- **`rec_watch` is not charged by the sl_ rate limiter** (pre-existing). Each `1`
  spawns the PVS eye (SV_ViewEyeAt) and each `0` frees it, and FTE keeps a freed
  edict for 0.5 s (qclib/pr_edict.c), so a stringcmd flood ratchets `num_edicts`
  up for the rest of the map and every `nextent` walk pays for it. Patch 477
  round-10 integrity review. Since round 14 a pin on a running run also writes a
  `warp ... pin` line, only when it zeroes some speed or carrier (round 16) --
  which no move bounds: `sl_load`, then `sl_hold; sl_holdoff; rec_watch 1;
  rec_watch 0` repeated in one frame hands the save's speed back and zeroes it
  again each cycle, ~30 to a packet, uncharged (round-17 integrity review).
  Practice runs only, under the line cap, the order `rec_ghost` pairs already
  write; one hold per load (`rec_sl_loadt = 0` once taken) would bound it.
- **A spectator's client acts on its tracked player's save events** (QC stats come
  from the tracked player, and Rec_ViewSaveEvents/Seq_SaveEvents run every frame):
  that player's prefixes and segment columns are written into the SPECTATOR's own
  save tree, over its own saves at those ids -- and a remote non-lobby server's
  ids land on the client's offline tree the same way. Save events should be
  ignored unless the stats are this client's own. Patch 477 round 8 review.
- **`setpos` can arm a start box clean, at rest, in mid-air** (predates 477;
  Patch 477 round-8 integrity review, traced, not driven). It has no cheat gate and
  no ground snap; the next packet's occupancy edge arms the attempt, and
  SV_TimerArm re-derives `run_t_cheat`/`run_t_dirty` from the live state, so the
  cheat latch does not survive the arm it caused. Worth speed only where a fall
  can leave the box. Fix: ground-snap a setpos that lands in a start or stage
  zone, as SV_SaveLocPickInZone does, or keep its cheat latch across that arm.
- **A HOST-SIDE INABILITY TO VERIFY IS RECORDED PERMANENTLY AGAINST THE PLAYER'S
  RUN.** `pm_verify` answers PASS / HOLD / REFUSE, and REFUSE is documented as
  "cannot say, never a judgement on the run" -- but `surfd/sweep.py:236-238` sets
  `checked = 1` on any non-ERROR verdict while `pending()` (`:86-96`) selects
  `checked = 0`, so **a REFUSE is terminal**. The only retryable outcome is
  ERROR, which the engine cannot emit: it is produced solely by `sweep.py:270`'s
  "no VERIFY line" fallback. So verdicts that are genuinely about THIS HOST --
  Patch 463's `this server cannot state its own zone pin` and `this server's zone
  pin is too long to read`, and anything else describing the verifier rather than
  the run -- stick to the run for good, one admin click each to undo
  (`admin.py:1577`). Two things are needed: a verdict class `sweep` will retry,
  and a bulk re-check (there is none in this tree, which is also what makes
  Patch 463's fix prospective-only). This is the Patch 421/422 third-verdict
  shape one level out: the word is right and the plumbing collapses it.
  Found by Patch 463's evidence reviewer.
  **MEASURED 2026-09-28 AFTER THE DEPLOY: THERE IS NOTHING TO REPAIR, and the
  claim that there was is withdrawn.** The live board has 72 verdicts -- 49 PASS,
  21 REFUSE, 1 HOLD, 1 ERROR -- and **0 of the REFUSEs mention zones**. All 21 are
  unrelated and correct: 10 `a stage restart`, 9 `not exact: no seed or no full
  pin`, 1 `no input trace`, 1 `a ghost window`. So Patch 463 rescues no historical
  run, because none was ever refused for the reason it fixes; the deploy notes
  saying it "helps runs from now on and not the ones it would have rescued"
  overstated a backlog that does not exist. The DEFECT is still real and still
  worth fixing -- a host-side verdict sticking permanently to a player's run is
  wrong whether or not it has happened yet -- but it is not urgent, and a bulk
  re-check built today would have nothing to chew on. Measured against
  `/srv/nvme/surfd/data/surfd.db` on the Pi, not inferred.
- **FIXED IN CODE, STILL GATED ON A DEPLOY, AND THE ALREADY-REFUSED ROWS DO NOT
  REPAIR THEMSELVES.** Engine Patch 463 (`0022cd190`) compares the fields instead
  of the path, so the 543 zone mirrors are unblocked as soon as the fleet runs it.
  Two things that are NOT done and do not happen by themselves:
  (1) `build.ps1 -Pi` restarts all 12 lobbies, so the deploy is the user's call;
  (2) deploying repairs nothing retroactively. `surfd/sweep.py:236-238` sets
  `checked = 1` on any non-ERROR verdict and `pending()` (`:86-96`) selects
  `checked = 0`, so a REFUSE is terminal. Every run already refused for this
  reason keeps its REFUSE until somebody issues the per-run `recheck`
  (`surfd/admin.py:1577-1579`), one at a time through the admin UI. **There is no
  bulk re-check in this tree**, and writing one is the missing half of this fix.
  Found by Patch 463's evidence reviewer.
- ~~**`pm_verify`'s zone pin includes the SOURCE DIRECTORY, so moving a byte-identical
  zone table from `online/` to `local/` refuses every existing recording for that
  map.**~~ Fixed by Patch 463; kept for the measurement, which is the reason the
  mirror was held. `sv_ccmds.c:5264` built `zbuf = "<zonesrc> <zonecrc> <zonerule>"` and
  `strcmp`s it against `SV_VerifyZonePin`'s answer; a mismatch sets
  `refuse = "a different zone table or rule"` and returns before replaying a tick
  (`:5267-5271`). But `zonecrc` is already a hash of the BUILT table -- type,
  track, seg, cp, z-band and every point at `%.3f` (`Zone_Hash`, sh_zones.qc:264)
  -- so the table is pinned twice and the second pin is a PATH. Two directories
  holding the same bytes are the same table, and saying otherwise is a false
  refusal on an honest run: the maximum-severity verdict for a file that is
  correct. Same shape as Patch 421's two-verdict angle check.
  THIS IS LOAD-BEARING FOR THE ZONE WORK. `tools/zoneinstall.py` can donate a
  zone file to the 66 builds that have none (done -- none of them could be timed
  before, so no recording exists to invalidate; measured, 0 of 66 carry BSP timer
  triggers), but it CANNOT mirror the other 543 maps into the editable folder
  until this is fixed, because every one of them currently records
  `zonesrc online` and 265 local recordings plus the fleet's corpus would stop
  verifying. Fix: compare `zonecrc` and `zonerule`, report `zonesrc` alongside as
  information. Touches the verifier, so it needs the independent review AGENTS.md
  requires before deploy. Note `local` already occurs in the wild -- Momentum's
  own install ships 14 files in its `zones/local`, which FTE's VFS resolves on
  that same path.
- **CONFIRMED BY MEASUREMENT: a pre-446 map could have made the server broadcast
  `rcon_password`. THE FLEET'S RCON KEY SHOULD BE ROTATED — an operator action, not a
  code one.** `Cmd_ExpandCvar` interpolates `$cvar` into the text AFTER the Cbuf split,
  so it can never start a second command (Patch 446 closed that class separately); what
  it does is expand a cvar INTO an allow-listed `say`. Round 7 read this in the engine
  and could not close it. `tools/p447dollar.py` + `cfg/test/p447dollar.cfg` now do, with
  two canaries so the real secret is never involved: a no-flags cvar and
  `rcon_password` holding `CANARY447RCON`. **On the pre-446 control BOTH EXPANDED** —
  so expansion happens at that exec level and the `CVAR_NOUNSAFEEXPAND` guard does NOT
  bite, because it tests `Cmd_IsInsecure()` against an exec level that is still 0 when
  the expansion runs. On a 446 build the command is refused and the question cannot be
  asked. qwprogs AB1F10EBDD196A3E fixed / 1F000116DB26CD5A control.
  **IMPACT:** the fleet has a real 48-character `rcon_password` in
  `game/ftesurf/cfg/lobby_local.cfg` (checked as a length, never printed), mtime
  2026-09-12, so there was a live secret behind the door. The door closed on the fleet
  at 2026-09-27 00:29:40 UTC when 446 deployed.
  **MEASURED MITIGATION:** 0 of 1438 shipped `Command` rows contain `$` or `%`
  (`tools/census/iocmd.py`), so nothing in the installed corpus exploited it — a crafted
  map would have had to be installed on the server first, which is not something a player
  can do. So this is "a live secret was reachable by a map for an unknown window" and not
  "the password leaked".
  **WHAT IS STILL OPEN HERE IS NOT CODE.** Rotating the key is the operator's call and no
  tool in this repo touches credentials. Worth doing on the reasoning that the window
  cannot be bounded from below: `lobby_local.cfg` predates every build in this series.
- **`tools/census/bsplib.py`'s `parse_ents` returns a dict, so every census that counts
  entity OUTPUTS has been under-counting.** A dict keeps only the LAST value of a
  repeated key and Source entities repeat output keys routinely. Round 7 measured the
  damage on two tools: `iocmd.py` saw 737 `Command` rows where the sound parse sees 1438,
  and `togglesolid.py` saw 184 maps with an Enable/Disable/Toggle output where the sound
  parse sees 226 — and that second one **overturned its own published conclusion** (grade
  3 went from 0 to 1). `parse_ents_pairs`/`read_pairs` now exist beside it and both tools
  use them. A second, independent bug travels with it: those tools split the I/O record
  on `,`, and VBSP >= v25 uses 0x1B ESC — `sv_entities.qc` picks the separator per value,
  the tools did not, and 144 of 1438 rows on 34 maps were invisible. Round 7, lens B.
  **THE REST OF THE DIRECTORY WAS THEN CHECKED AND IS CLEAN, so what remains is one
  file.** `onjumpstart.py` has neither bug — it builds its own pair list
  (`[v for k, v in kv if k == 'OnJump']`) and regex-searches the value for
  `basevelocity` instead of splitting it, so a separator it never uses cannot mislead
  it. `pushcensus.py`, `pushtilt.py`, `sscensus.py`, `sscount.py`, `ssd1.py` and
  `startdest.py` read only single-valued keys (classname, model, origin, spawnflags),
  for which a dict is the correct shape. `onjumpstart.py`'s remaining fragility was
  measured rather than left as a suspicion: it matches `k == 'OnJump'` case-SENSITIVELY
  and without a trim, where VBSP guarantees neither, so a differently-cased key would
  have been skipped and under-counted its "ZERO overlapping a start zone" result in the
  reassuring direction. **Scanned the raw entity lumps of all 1316 bsps: 1381 `OnJump`
  keys and EVERY ONE is spelled exactly `OnJump`** — no case variants, no leading space.
  So the match is sound on this corpus and the whole directory is now accounted for.
  Nothing is open here; the entry stays as the record of what was checked and how,
  because the next census written in this directory needs to know both bugs existed.
- **And on a LISTEN server, map I/O can reach `ClientCommand` after all — and it can
  destroy data, not just grief.** The server's own `say` is registered only
  `if (isDedicated)` (engine `server/sv_ccmds.c`), so on a listen server
  `localcmd("say !r\n")` runs the CLIENT's `CL_Say_f`, which forwards as that player's
  chat and reaches `SV_ZoneChatCommand`. **This falsifies the absolute claim** that map
  data cannot press `!r`, which AGENTS.md and Patch 445's own essays stated; all are
  corrected to the narrower true fact (`localcmd` cannot reach `ClientCommand` on a
  DEDICATED server, which is what the lobbies are). PATCH 446 DOES NOT NARROW THIS: a
  bare `say !…` needs no separator, so it still passes. `!r` itself buys a cheater
  nothing (the forced reset zeroes velocity and voids the run, and a listen server cannot
  submit to the board), but the bang table in `sv_player.qc` also holds **`!discard`,
  which destroys the player's parked Multi-Session run**, and `!rtv`/`!extend`, which
  cast the local player's vote. That is data loss on a server the victim operates.
  Round 6 lens B; extended in round 7.
- **THE CHEAPEST PRESPEED ROUTE IS UNTOUCHED BY THE HOPPED-START RULE, and the entry
  below over-claimed what Patch 445 narrowed.** The taint block is gated on
  `!run_t_startok`, and `run_t_startok` latches ~1 s after leaving the box or on the
  first ramp contact while RUNNING. After that no hop is judged at all, and a hop taken
  while RUNNING goes to `SV_TimerPractice`, whose three writes are ALL cleared by
  `SV_TimerArm`. So: leave the box cleanly, touch a ramp, bhop to any speed **outside**
  the box, re-enter the box (on a surf map `run_t_bhopjump` is FALSE so the arm is
  immediate and has no velocity gate), leave. `run_t_hopped` is never set, the arm
  launders the rest, and the run is clean, ranked and at full prespeed. Patch 445 raises
  the price of the in-box jump route to "`!r` and lose all your speed", which makes this
  one comparatively cheaper. Round 6, lens B; CONFIRMED in code, not measured. **Test:**
  drive it and read `cmd timer`'s `hopped 0` + `class: clean` after the second start.
- **Scope, stated because it bounds every entry in this family: the whole hopped-start
  rule is INERT on bhop-mode maps.** `cfg/lobby/mode_bhop.cfg` sets `run_starthop 0` —
  hopping out of the start is the sport there — and `SV_TimerMapInit` applies it from the
  map's own metadata, including on a listen server. That is roughly half the roster, and
  it means Patch 445 changes nothing for those maps. Round 6, lens B.
- **FOUR SHIPPED TRACKS HAVE AN END REGION THAT OVERLAPS THEIR OWN START, so a finish
  there should read as a CANCEL and the track cannot be completed at all.** MEASURED by
  `tools/census/endnearstart.py` over all 537 zone files: `agtricks` main,
  `surf_flyin_fortress` main, `surf_ethereal` b1 and `surf_quirky` b9 have an END whose
  prism is identical to or nested inside their segment-0 START, both polygons
  axis-aligned so the figure is exact (flyin_fortress' END is the same rectangle 0.011 u
  shorter; agtricks' is a 128x128 END inside an 1856x704 START). A fifth,
  `surf_pools` b2, is an AABB artefact — its rotated polygons do not actually overlap.
  MECHANISM, read but NOT run: in `SV_TimerFrame` the occupancy step runs BEFORE the
  event dispatch, so re-entering the START while `TS_RUNNING` reaches `SV_TimerTryArm`,
  and `run_rearmstops 1` (the shipped default) re-arms and prints "run cancelled (back in
  the start)". The dispatch then finds the state is no longer `TS_RUNNING` and
  `SV_TimerEvent` returns. FTESurf also ignores an END's `filtername` — nothing in `src/`
  reads that key — so the region loads unfiltered even where the mapper meant it not to.
  A map-caused denial: on those tracks no time can ever be set. Found by Patch 448's
  round 8 while checking whether the finish clear was reachable there; it is not, which is
  incidentally good for 448 and bad for the player. **Next step is to drive one of the
  four and read whether the cancel line appears** — the geometry and the control flow are
  established, the live behaviour is not. **DRIVEN 4 Oct on surf_ethereal b1: the
  cancel.** Patch 478's round-7 integrity review traced a few-tick finish instead (the END
  tests the hull, the arm the point); two out-and-backs -- one walked from the bonus
  spawn, one from a setpos 20 u inside the +x edge -- both read "run cancelled (back in
  the start)" and re-armed, no finish. So the denial stands where the rings are identical.
  agtricks (bhop mode, a 128x128 END nested in the START, where re-entry defers) is not
  installed here and is untested.
- **A hopped-start tag survives a VOID, though no longer a finish.** Patch 448 fixed the
  finish half and **Patch 454 fixed 448's argument**: the finish no longer clears the tag
  outright — it ARMS a forgiveness that is taken once the player is grounded at or below
  `sv_maxspeed`, because `endnearstart.py` measured 12 shipped tracks whose END sits within
  64 u of their own START (4 overlapping, `surf_summer` main at 64) where 448's "the trip
  costs something" was false. So the clear cannot carry speed whatever the geometry.
  **The above-`sv_maxspeed` refusal is UNMEASURED** — every headless gesture walks at or
  below it, so the arm only ever exercises the YES branch. It needs a human finishing fast
  on one of those tracks, and `tools/p448fin.py` says so in block capitals.
  **WHAT REMAINS IS THE VOID PATH.** A cancel zone or a fall-off `trigger_teleport` goes
  through `SV_TimerVoid` → `SV_TimerIdle`, which deliberately does not clear (it is
  map-reachable, which is the whole reason 445 took the clear out of there) — so an
  attempt abandoned rather than finished still carries the tag into the next one. On the
  66 maps whose own reset teleport IS that path, that is the honest population.
  Unlike the finish, a void has no "you traversed the map" argument available: a cancel
  zone can sit next to a start box, so clearing there could carry a chain's speed. The
  shape that would work is a clear gated on the void having moved the player somewhere a
  chain's speed cannot survive, which is a harder predicate than 448 needed and wants its
  own patch. Round 6 lens C; finish half closed by 448.
- **Nothing on the client knows about the tag.** No `STAT_FS_*` carries `run_t_hopped`;
  the HUD's taint word comes from `STAT_FS_TIMERFLAGS` alone and `TF_PRACTICE` is not set
  until `SV_TimerStart`, so a player standing ARMED with the tag up reads `ready`. Round
  6 added a chat reminder on each later fluffed start, which is a mitigation and not a
  fix: the state is still invisible between attempts. A stat bit, or the `phase:` line's
  free varargs slots, is the shape. Round 6, lenses A and C.
- **The `.rec` records no trace of the hopped start, and the tag can now predate the
  recording by minutes.** There is no hopped/jumps/reason key anywhere in the grammar,
  the taint chain runs BEFORE `SV_RecOpen` by design, and the pre-start pad ring is 256
  samples ≈ 3.84 s. Under build 21 the tag could not outlive its arm, so residual
  `TF_PRACTICE` implied "the hop happened in this attempt"; it now means "at some point
  since the last `!r`, respawn or map change". **A reviewer at `/admin/runs` can see a
  practice-residual run whose recording contains no jump anywhere**, with nothing in the
  evidence supporting the class — which is CLAUDE.md's "a check that cannot measure must
  say so" and the file says nothing. An additive `.rec` record at the set costs no version
  bump. Round 6, lenses B and C. Also stale on the same account: `cl_timer.qc` and
  `sh_defs.qc` both claim bare practice has "exactly one live cause", and bare
  `TF_PRACTICE` is filed under the `stitched` chip, so the browser labels a hopped start
  "a save state was used".
- **A false hopped tag is no longer self-limiting, and there are more ways to earn one
  than the rule's comments admit.** The trigger is a `velocity_z` edge with a dwell test,
  and the dwell reads 0 whenever `run_t_groundsec` is 0 — which `pm_autobunny` guarantees
  for a held jump. Pre-445 a false tag healed at the next arm or after 0.25 s grounded;
  now it kills every subsequent run on the map until `!r`. **And `!r` itself does not
  reliably clear it: pressing it while still holding +jump re-tags within a tick**, so
  the one remedy fails for the gesture most likely to have caused the problem. Unmarked
  or under-marked upward-velocity writers found while checking this, all reachable while
  ARMED in a start box: `trigger_teleport` VelocityMode 3 (marks nothing and strips
  FL_ONGROUND without `run_pushlift`), `trigger_push` SF_PUSH_ONCE (the upward clip lands
  on the next command, after `run_pushed` is cleared), `trigger_setspeed` (marks only
  when `vel_z > 140`), Patch 409's stated residual, and a plain standable slope
  deflecting horizontal speed upward with no pad involved. Round 6, lens B. This is the
  blind-dwell entry below with teeth; fix it at the placement, and note that two earlier
  attempts at it failed review.
- **`SV_TimerMapInit`'s per-player loop is dead code.** `find(p, classname, "player")`
  matches nothing on a map change or `map_restart`: `SV_SpawnServer` runs `PR_Deinit` and
  re-allocates every client edict blank, and `classname = "player"` is assigned only
  inside `PutClientInServer`, which runs after the zone load the loop hangs off. So the
  `SV_TimerIdle(p)` and recorder resets in it never run. Harmless today (the edict is
  blank anyway) but the loop's comment asserts the opposite — "the player entity outlives
  a map change on a listen server" — and Patch 445 added a call into it on that premise
  before round 6 removed it. Pre-existing. The engine's `preserveplayers` path needs a
  `ClientReEnter` global this progs does not define. Round 6, lens A.

- **A prespeed start-box load still arms CLEAN on the 6 regions where `%.4f`
  rounding hides the zone** -- Patch 435 answered the velocity where Build 47's
  gate can fire (`tools/census/startdest.py`: 29 of 35 shipped regions with an
  authored teleDestPos), and on the other 6 -- 3 maps, bhop_eazy,
  kz_bkz_goldbhop_v2, surf_friday -- SV_ZoneStartAt answers -1, so neither the
  gate nor Patch 435's row-speed condition is reached. THERE THE HOP IS THE
  ROUTE, and only on a non-bhop mode: `cfg/test/p435mode.cfg`
  (`python tools/p435pre.py --arm mode`) measures a prespeed load + `+jump` with
  `sv_gamemode surf` arming at z 106.9 against a slab bottom of 64.03125 and
  reading `arm zone 0`, `practice 0`, `class: clean`. `cfg/test/p435hop.cfg`
  (`--arm shipped`) tried to measure the same gesture in bhop mode and DID NOT
  DEMONSTRATE it: its own control (H3, the at-rest save loaded and jumped) came
  back tainted, which is verbatim that cfg's `FALSIFIED IF`, because on
  bhop_eazy's shipped zones no start-box load arms clean at all -- the rounding
  above. So on a bhop-mode map the question is OPEN. The mechanism that would
  answer it is readable in the code (SV_TimerTryArm's `run_t_bhopjump` branch
  refuses to arm an attempt already RUNNING, so the jump starts the run from the
  restored ARMED state instead of arming it) but it is not measured, and the
  entry this replaces claimed the hop beat the rounding EVERYWHERE, which is
  false only for the surf-mode half. A SOUND ARM is p435hop's gestures in bhop
  mode with `cfg/test/p435.zones.json` staged so the control can arm clean -- the
  same fixture p435pre and p441void use -- or one of the 6 exposed regions'
  own maps. `tools/p435pre.py --arm shipped` now exits 1 with NOT DEMONSTRATED
  rather than grading H3 against the failed reading (Patch 441). The fix has to answer the
  velocity where the gate cannot see it: either zero the inherited speed at a
  start-box placement under a TOLERANT box test (body AND the hold's
  `rec_sl_holdvel`, or the release hands it straight back), or a load-scoped mark
  SV_TimerArm refuses to launder while it stands -- cleared by the body being
  slow, NOT while `rec_sl_hold`, and never at SV_TimerArm itself, because on a
  surf map flying into a start box arms you clean at speed by design (Patch 415's
  essay) and a speed test there would taint every honest re-entry.
  PATCH 442 CLOSED THE VERTICAL HALF of the gate's blindness, which is not the
  same as closing this: SL_RowSpeed measured horizontal speed only, so a save
  taken MID-JUMP inside a start box (vz +302, nothing horizontal) read as at rest
  and laundered -- measured both ways, `cfg/test/p442jump.cfg`. The gate can no
  longer be told a rising body is at rest, and `sl_list` no longer prints such a
  row as `0 u/s standing`. A load carrying speed still hands that speed back, as
  a segmented run, so the placement answer above is still the open item.
  AND PATCH 443 CLOSED THE GROUND HALF, also not the same as closing this: the gate
  now asks whether the row was standing on anything (SL_RowGrounded, the mover's own
  probe plus its quadrant retry), so a body hanging at rest inside the slab no longer
  arms clean. All three gate on the ROW; none of them answers the question this entry
  asks, which is what the PLACEMENT should do with a speed the gate has decided not to
  launder. sv_timer.qc SV_TimerTryArm / SV_TimerArm, sv_saveloc.qc SV_SaveLocLoad,
  SL_RowSpeed, SL_RowGrounded. Patch 435, part-closed by 442 and 443.
- **`SV_TimerFrame`'s no-zone-tests guard misses the replay pin too.** It guards
  `e.rec_sl_hold` (sv_timer.qc:12370) and `e.rec_gh_on` (:12377) and not
  `rec_wt_hold`, so the occupancy scan can produce an ARM EDGE on a body frozen by
  `rec_watch` -- SV_TimerArm, which zeroes run_t_flags. The Patch 428 round 6 comment
  at that site applies verbatim, one pin over: fall into a start box, pin on the entry
  packet, hang there with the clock frozen for as long as you like, unpin and fall from
  rest. Worth the hang rather than a speed only since Patch 477 round 7: before it, a
  repeating `OnTrigger` basevelocity booster (20 in the library) paid the pinned body
  once per firing with no friction, and the release kept it -- the pin now zeroes the
  velocity and the carrier every tick and at the release (SV_WatchFrame). Same review.
- **CROSSING THE SEAM BETWEEN TWO ADJACENT START REGIONS RE-ARMS SILENTLY, and 21
  shipped maps have such a seam.** `SV_ZoneOcc` is a POINT test at the shipped
  `run_zone_hull 1` while the start test `SV_ZoneIn` is the HULL, and the arm scan runs
  AFTER the start test in the same packet -- so on two abutting or overlapping arm-able
  regions, crossing the boundary flips `run_t_azone`, SV_TimerTryArm fires (its bhop
  guard needs TS_RUNNING/TS_FINISHED, so it does not stop this), SV_TimerArm zeroes
  `run_t_flags`, `run_t_hopped` and `run_t_jumps` and re-derives dirty from the current
  movetype -- and the clock CANNOT start, because the start test used the old armzone
  whose hull the body is still inside. Nothing is printed: SV_TimerClassSay needs
  TS_RUNNING. So a bhop chain that loops across a seam has its hopped-start taint
  cleared on every crossing. MEASURED over the 537 shipped zone files by simulating
  `az` and Zone_BoxInside: **21 maps** with a same-(track, segment) pair.
  **RE-MEASURED BY A COMMITTED TOOL IN ROUND 7** -- `tools/census/startrearm.py`, an
  independent census written because this number was quoted in deployed source and had
  no tool behind it. The 21 reproduces EXACTLY. The sub-count in this entry did not:
  it said 15 START/START and **it is 18** -- all fifteen named are real, and it missed
  df_cavernish, surf_gradient and surf_lt_omnific. Full split: 18 START/START, 5
  STAGE/STAGE, overlapping on the 2 maps that have both (21 = 18 + 5 - 2), plus 10
  further maps that touch only ACROSS legs (30 maps with any touching pair, 57 pairs).
  surf_gradient has all three kinds, which is why the old bucketing undercounted.
  surf_tequila's main start is four trapezoids tiling one frame, sharing three diagonal
  seams; a crossing keeps the hull straddling for 32 units, which is two packets below
  ~1000 u/s. The fix wants the arm scan to refuse a re-arm that changes nothing a
  player did -- an `az` flip between two regions of the same track and segment is not
  an arm -- or the hull test both sides. `sv_zones.qc`'s "SV_TimerArm is idempotent
  while armed" is the comment that stopped being true. sv_timer.qc SV_TimerArm,
  SV_TimerTryArm, the occupancy scan. Patch 443 review, round 4, cheater lens.
  **PATCH 445 TOOK THE HOPPED-START HALF OUT OF THIS**, which is the half that was worth
  anything to a cheater: the arm no longer clears `run_t_hopped`, so a chain looping
  across a seam stays tagged and only `!r` (velocity zeroed) forgives it. The silent
  re-arm itself is UNCHANGED and still zeroes `run_t_flags` and `run_t_jumps`, so this
  entry stays open on its own terms -- the seam is still a re-arm nobody asked for.
- **66 maps' own velocity-keeping teleports land inside a START region, which re-arms
  at whatever speed you arrive with.** `trigger_teleport_touch` with `VelocityMode`
  absent or 0 KEEPS velocity (a plain CS:S map has no such key), strips FL_ONGROUND,
  and calls SV_TimerWarped, which empties the 3.8 s pre-start padding ring -- the only
  trace of the approach that would have reached the `.rec`. Arriving from outside, the
  next scan is an `az` edge, so SV_TimerArm launders as in the entry above. MEASURED
  over 535 zoned BSPs (52,879 trigger_teleport entities): 66 maps have at least one
  velocity-keeping non-landmark teleport whose destination lies inside a START region.
  **RE-MEASURED BY `tools/census/startrearm.py` IN ROUND 7 and reproduces exactly**,
  including the 52,879: of those, 455 are landmark, 46,229 have a VelocityMode set, 6,195
  are velocity-keeping candidates, 148 have an unresolvable destination, and 1,616 land
  inside a START region across those 66 maps. The 46,229 exclusions are why the answer is
  66 and not 500 -- most shipped teleports DO set a mode, so this number tracks a mapper
  convention and wants re-running when the corpus changes
  -- surf_pantheon 197, bhop_4tele 257, surf_suburbia 204, surf_valpect 90,
  surf_tibet 69, surf_dynasty 60, surf_ambient 34, surf_ecosystem 17, surf_gradient 19,
  surf_wahey 6. Gesture: chain to speed anywhere, take the map's own reset teleport,
  arrive in the start box at full speed ARMED and laundered, leave. No cvars, no
  restriction on other players. Same review.
  **PATCH 445 NARROWED THIS THE SAME WAY** and it matters more here, because a teleport
  is the one path that carries the speed AND used to carry the forgiveness: the arm no
  longer clears `run_t_hopped`, so a chain built before the teleport is still tagged on
  arrival. What survives untouched is everything else -- the velocity, the stripped
  FL_ONGROUND, the emptied padding ring and the `run_t_flags` zeroing -- so a player who
  builds speed WITHOUT hopping (a ramp clip, a push) still arrives clean and fast. The
  entry stands; only the hop-chain variant of it is closed.
- **A ramp-clipped hop is neither counted nor judged.** `run_rampcontact` suppresses
  `jumped` in SV_TimerJumpWatch, so a hop whose rise came from a ramp clip never
  reaches the hopped-start test AND never increments `run_t_jumps`. On a start box with
  a ramp in it -- which is the shape of a surf start -- a player can build speed with
  clips the rule cannot see. Pre-existing and independent of saves; found while
  checking whether a count-based rule could replace the dwell, which it cannot for this
  reason among others. sv_timer.qc SV_TimerJumpWatch, the `jumped` edge. Same review.
- **A box re-entry still launders `run_t_flags`, though no longer the hopped start.**
  FIXED IN PART BY PATCH 445, and what remains is narrower than the entry it replaces.
  Leaving the start box and re-entering it calls SV_TimerArm (SV_TimerTryArm ->
  SV_TimerArm), which touches `.velocity` not at all -- so "chain to speed, step out,
  step back in, walk out fast" still works. What it no longer does is come out CLEAN:
  445 took `run_t_hopped` out of the arm's clear list, so the hop taint survives a
  re-entry and only `!r` (which zeroes velocity) takes it back. `run_t_flags` is still
  zeroed, so any TF_PRACTICE from another source is still laundered by the same edge --
  that is the 46-field overreach entry below rather than a hopped-start bug.
  SV_SaveLocPickInZone's own essay names the re-entry arm ("on a surf map re-entering
  one while running ARMS you outright"). Patch 443 round-4 review; narrowed by 445.
  **ROUND 6 CORRECTED THE NARROWING CLAIM IN THIS ENTRY, WHICH WAS OVER-STATED.** It is
  true only when the chain happens INSIDE the box while ARMED. Done outside the box --
  which is where anyone builds real speed, and which `run_t_startok` makes unjudgeable
  after about a second -- `run_t_hopped` is never set at all, and the re-entry still
  launders everything. See the "cheapest prespeed route" entry at the top of this
  section: that is the gesture people actually use, and 445 does not touch it.
- **The retry placement is a second copy of the start-box velocity restore, with no
  gate on it at all.** `SV_SaveApplyState`'s retry branch places the body from the
  file's `origin`/`velocity` (sv_saveloc.qc:1194-1210) and restores the flags
  verbatim (:1395) -- no SV_TimerStitched, no SL_RowSpeed test, no SV_ZoneStartAt
  test, no `sl_voided` check, no demoted re-scan. Patch 442 hardened SL_RowSpeed,
  which has exactly one caller: the SV_SaveLocLoad gate. So: re-enter your own start
  box while RUNNING (with `run_rearmstops 1` SV_TimerTryArm re-arms without zeroing
  velocity), `retry` there, and the restart hands back ARMED + clean + that velocity,
  up to `sv_maxvelocity`. Prespeed injection into a clean armed attempt, repeatable.
  Its only brake is that `retry` refuses with more than one player on the lobby.
  Patch 441 review. **STILL OPEN, AND IT IS NOW THE FIRST THING TO CLOSE IN THIS
  FAMILY.** The previous version of this line said Patch 443 "turned the hopped-start
  rule back on for the restored ARM, so the chain the entry above describes is judged
  now" -- FALSE, round 4 withdrew that half and `SV_SaveApplyState` still sets
  `run_t_startok = TRUE` for every restore. Patch 445 then closed the OTHER two
  prerequisites the withdrawal named (the save format carries `hopped`, and an arm no
  longer forgives), which leaves this entry as the single remaining reason judging a
  restored arm is pointless: the velocity the placement hands back is read by no gate
  on the retry path at all, and the rule does not speak to a player who never jumps.
- **SL_RowGrounded's three residuals, and one of them is that a refusal leaves no
  artifact.** Patch 443 closed the airborne-row hole (the gate asked about SPEED and
  never about SUPPORT); what it does NOT do is the mover's last two steps. The probe
  grants a `func_slide` plane, which CategorizePosition demotes (engine
  pm_source.c:2119), and it grants a landing Patch 176 can refuse outright (:2131) --
  both fail-open, so they are a cheater's lens rather than a player's. Against that, an
  honest save wedged at rest on a ramp too steep to stand on keeps its taint, and the
  refusal is recorded ONLY in a dprint: nothing in `run_t_flags`, nothing in the save
  event stream, so a player who loses a rank to it leaves nothing a reviewer can read
  and the HUD shows `segmented` with no reason. A one-line `sprint` when the gate
  refuses on support alone would close the last one. sv_saveloc.qc SL_RowGrounded.
  (Both engine citations above had drifted and are corrected in the source: the
  func_slide demotion is `pm_source.c:2102`, not :2119.)
- **AND IN PRODUCTION THAT dprint DOES NOT EXIST, so neither a refusal nor a GRANT is
  observable on the fleet.** `dprint` prints only when `developer` is set and
  `default.cfg` never sets it, so SL_RowGrounded's one and only record of what it
  decided is absent on all twelve lobbies. The same two-valued return also GRANTS the
  laundering, so every "cannot see" that resolves TRUE is an unlogged grant of a clean
  rankable attempt. This is the worst of the probe's residuals because it defeats the
  remedy for all the others -- you cannot audit a check whose output is compiled out by
  configuration. A `SV_CensusAdd`-style counter, or the `sprint` the entry above wants,
  would make it readable; the third verdict below is the real fix. Patch 443 round 5,
  lens B. sv_saveloc.qc SL_RowGrounded's dprint.
- **SL_RowGrounded has TWO verdicts where CLAUDE.md requires THREE, and this is the
  entry the rest of its family reduces to.** Embedded, a NaN row origin, a
  `SOLID_BSPTRIGGER` support, a floor deleted by `World_PortalCSG`, a brush disabled
  since the save was taken, and every moved movevar all collapse to the same `FALSE`.
  The repo's own lesson (Patch 421's angle check, 422's absent receipt, 424 twice) is
  that the fix is never a better threshold, it is the third answer -- here "the row
  cannot be judged", which must neither grant nor refuse. Note the polarity differs
  from 421's: this check's two-valued failure GRANTS rather than accuses, so the cost
  is a laundered run instead of a false fault. Patch 443 round 5, lens B.
- **`MOVE_NOMONSTERS` includes `SOLID_PORTAL`, and `World_PortalCSG` can delete the
  world's floor hit.** A row standing on real floor inside a portal's CSG volume reads
  `frac 1.000` and is refused -- a false refuse, conservative, but a distinct fourth
  way for the probe to mean "could not see" while saying "no". Also: the trace's content
  mask is selected from the passed entity's own solidity, so the call is correct only
  because a player is `SOLID_SLIDEBOX`; nothing in the signature says so, and a future
  caller handing it a non-player entity gets a different mask with no diagnostic. Both
  named in the source now. Patch 443 round 5, lens B. sv_saveloc.qc SL_RowGrounded.
  Patch 443 review.
  THE func_slide ONE IS CONFIRMED FROM THE ENGINE SIDE, and it is worth knowing that
  someone already thought about it: engine world.c's forced-contents path deliberately
  excludes slide skins so that "every server-side trace (QC traceline/tracebox, THE
  SAVE-LOC FLOOR PROBE, run_eyeinfo)" does not fall through a slide brush -- so the
  probe is MEANT to hit it. The mover then declines a slide plane as ground
  (pm_source.c:2119), which this does not, so a flat slide (nz 1.0, no acceleration
  along it) or any `disablegravity` slide is a genuine at-rest airborne position the
  probe certifies. `func_slide` is `func_brush` -> SOLID_BSP and `pm_slide 1` ships.
  The height is normally reachable anyway, so the payoff is small; it is the one case
  where "at rest, probe says standing, mover says airborne" is constructible today.
  ALSO INVISIBLE THE OTHER WAY, from round 3: the first-jump forgiveness prints only
  under `developer`, so a rank KEPT because the rule declined to judge leaves no
  artifact either -- the mirror image of the refusal above. The `phase:` line in
  `cmd timer` has three free varargs slots and is where both belong.
- **The Build 47 gate's forced edge is a LATCH OF UNBOUNDED LIFETIME, not an edge, and
  the arm it authorises happens to a DIFFERENT BODY.** `run_t_azone = -1` is written
  after five conditions evaluated at load time against a body at rest. On a bare
  `sl_load` the arm lands next tick, which is what four paragraphs of the gate's essay
  describe. THE SHIPPING CLIENT DOES NOT SEND A BARE `sl_load`: `cl_saveloc.qc` sends
  `sl_load` and `sl_hold` together on one keypress, the hold re-places the origin every
  tick under `MOVETYPE_NONE`, so the latch sits there for as long as the key is held and
  the arm fires on the tick after the RELEASE -- after `SV_SaveLocRelease` has handed the
  saved velocity back. So the gate certifies "at rest, in a start box, standing" and
  then launders an attempt belonging to a moving body an arbitrary time later. Patch 435
  is where this wants fixing, not 443: the gate should re-ask at the moment it acts, or
  refuse to survive a hold. Patch 443 round 5, lens C. sv_saveloc.qc SV_SaveLocLoad.
- **The gate's `!= TS_RUNNING` admits `TS_FINISHED`, so loading a finished save in a
  start box ARMS OVER THE RESULT.** `SV_SaveApplyState` treats FINISHED deliberately and
  says so -- "there is nothing left to continue, only a result to look at" -- and the
  Build 47 gate one function later does not: its state test excludes only TS_RUNNING, so
  a restored FINISHED state passes, the edge is forced, and SV_TimerArm re-arms, taking
  `run_t_startseg`, `run_t_state` and the rest with it. The finishing time the save was
  taken to keep is replaced by a fresh armed attempt. The `run_t_bhopjump` branch in
  SV_TimerTryArm guards `TS_RUNNING || TS_FINISHED` together, which is what the gate's
  test should have matched. TRACED IN CODE, NOT MEASURED -- no arm loads a FINISHED save
  at a start box today, and that is the first thing to build. Patch 443 round 5.
- **The gate borrows 46 fields to clear five.** Its essay said "all six fields" and
  argued that reusing SV_TimerArm beats a parallel clear because the part is small.
  SV_TimerArm writes **46 distinct fields** (counted over its body: 25 `run_t_*`, 12
  `run_st_*`, the rest), so a load at rest in a start box runs all of them and only
  about five are what the gate is for. The conclusion still holds -- a parallel clear
  would drift -- but for the opposite reason, and the overreach is real: the arm also
  resets the stage machine, the checkpoint high-water mark, the PB lookup and the tick
  counters for a gesture whose whole claim is that you have not started yet. A narrow
  `SV_TimerLaunderStartLoad` that names its five is the shape; it needs the drift risk
  answered, which is why this is an entry and not a patch. Patch 443 round 5, lens C.
- **`SV_RecDiscard` has already thrown the recording away before the deferred arm clears
  `TF_RECORDING` for it.** Both run on the load path, in that order, so the arm clears a
  flag describing a buffer that no longer exists. Consistent today only by accident of
  ordering -- and `SV_SaveApplyState` already reads `wasrec` one function up precisely
  because this hazard bites there. An invariant that holds by ordering is a landmine:
  anything that moves the arm earlier, or the discard later, leaves the HUD claiming a
  recording with no buffer. Named at the gate now. Patch 443 round 5, lens C.
- **A togglable `SOLID_BSP` brush whose box reaches a start zone is a FAIL-OPEN, and
  ONE SHIPPED MAP IS A CANDIDATE.** `SL_RowGrounded` traces the world as it is at LOAD
  time and the save records nothing about the world at WRITE time, so: hover one unit
  above where a disabled brush's top face will be, inside a start slab, save at the
  apex, let the map's own button fire the `Enable`, load. The probe finds `nz 1.000` at
  `frac ~0`, grants, and the forced arm launders.
  **THE "NO SHIPPED MAP HAS ONE" CLAIM THIS ENTRY CARRIED IS WITHDRAWN.** It came from
  `tools/census/togglesolid.py`, and round 7 found that tool had the same two parser
  bugs as `iocmd.py`: it took a dict from `bsplib.parse_ents` (which keeps only the LAST
  value of a repeated key, and Source entities repeat output keys routinely) and assumed
  a comma separator where VBSP >= v25 uses 0x1B ESC. Both under-count, i.e. both made
  the census read more reassuring than the corpus warranted. Sound re-run, same 1316
  bsps / 535 zoned: **grade 3 (contained) is 1** -- `surf_legends`, `func_brush` named
  `health_small3`, reached by an Enable/Disable/Toggle output, contained in a start zone,
  overlap volume 4608. The self-check moved with it: 226 maps carry such an output (was
  184) and 276 brush entities are named by one (was 88).
  IT IS A CANDIDATE, NOT A FINDING: containment survives the AABB problem but does not
  show the brush's top face sits at a standable height inside the slab, that the Enable
  is reachable without the map's cooperation, or that a save can be taken at rest above
  it. **The next step is a live check on surf_legends** and it has not been done.
  The other grade-2 row is still the AABB trap in person -- `surf_hourglass`'s skybox
  shell, box spanning the whole map with its faces ~16000 u away. Patch 443 round 5,
  lens B; census corrected in round 7.
- **The save still carries no MOVER STATE and no MOVEVAR SNAPSHOT, though it now proves
  its BSP.** Patch 450 added `mapcrc` from `infokey(world, "*mapcrc")` and made the Build
  47 arm gate require a positive match, with three verdicts (no crc / wrong crc / proved)
  and a different message for each — measured both sides, `cfg/test/p450map.cfg`: the
  control laundered a save from a different bsp, the fixed build refuses it and still
  accepts a save taken on this install. **`map` stays write-only on purpose now**: the crc
  subsumes it, and one rule spelled twice is how they drift.
  **WHAT IS STILL MISSING FROM THE FORMAT:** the state of every mover at write time (a
  door or platform the row was standing on may be elsewhere now — the same family as the
  togglable-brush entry above), and the five movevars `SL_RowGrounded` judges a row with,
  which are pinned within an install but not across the write→read boundary a save is
  designed to cross. The crc closes the "different bytes under the same name" case; it
  says nothing about the same bytes in a different STATE.
- **The probe's five movevars are pinned within an install but NOT across the save's
  write -> read boundary.** All five are in `pms_lockedmovevars` under
  `pm_lockmovement 1`, so they are genuinely locked live -- but the canonical value is
  whatever `default.cfg` said at boot, and a save is explicitly designed to outlive
  installs. A `state.txt` written under the 72/54 hull FTESurf shipped up to build 40 is
  probed today with 62/45, and the row is judged by a rule the mover that wrote it never
  ran. The save would have to carry the five, which is the same "the format is missing a
  field" shape as the two entries above. Patch 443 round 5, lens B.
- **The dwell the hopped-start rule grades is BLIND after any placement into a fresh
  edict, and this is a LIVE defect rather than one the withdrawal avoided.**
  `run_t_groundsec` is 0 after a `retry` (the progs are re-initialised) and after an arm
  (SV_TimerArm deliberately does not reset it), and under `pm_autobunny` with the button
  held QC never observes `FL_ONGROUND` at all -- so the dwell reads 0, which means "a
  jump already taken". It was recorded as a reason Patch 443's withdrawn half was
  unsafe; round 5 showed it is reachable through the KEPT half too. Today it decides
  nothing only because the rule is off for a restored arm, so it sits one `startok` away
  from accusing an honest player of the one gesture the rule exists to permit. Fix it
  where it is caused -- at the placement -- not by widening the rule. Patch 443 round 5.
- **`sl_replay`'s taint does not survive the next arm, and it has no resume guard.**
  Patch 441 round 2 added SV_TimerPractice at the gesture so the command's safety is
  local rather than inherited from the cheatwatch blocks. It covers the attempt in
  progress only: SV_TimerArm re-derives the class from the level (sv_timer.qc:10566)
  and the retry/Multi-Session restores put back the saved flags, so `sl_replay` then
  `!r` clears it -- the same scope every other taint has, but the comment claims
  more. `SV_SaveLocReplay` also lacks the `run_ms_phase` refusal SV_SaveLocLoad has
  (sv_saveloc.qc:2299), so it can taint a run mid-resume. Patch 441 review.
- **`SV_RetryPoint` ignores `SV_RecDestream`'s return, so a failed destream writes a
  retry point that claims nothing was being recorded.** SV_RecDestream reads a
  streamed run's part file back into a buffer and returns FALSE -- after calling
  SV_RecDiscard -- when it cannot. SV_RetryPoint discards that answer and writes
  `state.txt` anyway, with TF_RECORDING clear and `reclines 0`, so none of Patch
  441's three clauses can see that this run WAS recording: with `rec_enable 0` the
  retry then carries a clean, rankable, RUNNING attempt across the restart with no
  recording. The fix is at the call (refuse the retry, or void the run) or by carrying
  "was recording" in the `rec_retry_armed` cvar the arming flag already travels in.
  Needs a stream -- a lobby, or `rec_stream 1` on a listen server, which is what
  would make it measurable. sv_saveloc.qc SV_RetryPoint, sv_timer.qc:5573.
  Patch 441 review, round 4.
- **`reclines` IS NOT EVIDENCE THE PREFIX FILE EXISTS, and nothing that reads it
  knows.** SV_RecWritePrefix returns its line count after `fopen`+`buf_writefile`+
  `fclose`, and QC cannot see any of those fail: the engine's PF_fopen allocates a
  MEMORY BUFFER for the write modes and the bytes leave at fclose, unchecked. Proved
  by staging a DIRECTORY on the retry slot's `run.rec` path -- the log shows the
  `fopen` succeeding, no `timer: cannot write` line, the directory still a directory
  at exit, and `reclines` positive in the state file with no prefix anywhere
  (`cfg/test/p441retryw.cfg`). So `SV_RecWritePrefix`'s `if (fh < 0)` branch is
  effectively unreachable for a filesystem fault, and every reader that treats
  `reclines > 0` as "there is a file" is trusting a count written before the bytes
  left the process -- Patch 426's reasoning about mark-0 saves, a verifier pairing a
  state file with a recording, and any future predicate tempted by `mark`. The fix
  wants the writer to confirm the file (a `fsize` of the path after fclose, or a
  `recbytes` it checks) before it reports a count. sv_timer.qc SV_RecWritePrefix,
  engine PF_fopen. Patch 441 round 6.
  **Patch 444 tried the `fsize` shape and is held back** (rebased as `p444rebase`,
  990a6cc, on origin; review of 5 Oct, two reviewers). It returns 0 when a
  FILE_READ re-open fails or reads empty, and: (1) SV_RecRewind refuses mark 0
  before its in-memory restore, so a same-attempt load whose prefix did not land
  now CANCELS a run it used to restore (buffered recorders: listen server,
  offline); (2) a stale or short file passes -- COM_WriteFile's failed "wb" open
  leaves the old file, reproduced with a read-only run.rec; (3) sv_saveloc.qc's
  "the two spellings agree on every reachable retry path" becomes false and
  round 5's `flg & TF_RECORDING` load-bearing. Its one ranked gain: an EMPTY
  prefix plus `retry` was a clean, rankable run with no header, and 444 voids it.
  Shape the reviewers suggest: keep `reclines` as the mark and write a separate
  key with the byte size the writer meant, compared as SV_RecRewindStream already
  does, which only the cold rewind refuses on.
- **TF_RECORDING can be left set with no recorder behind it.**
  SV_RecRewindStream's two cold-failure exits destroy the old recorder and return
  FALSE without clearing the bit, and SV_RecClose early-returns on `!SV_RecLive`
  without clearing it either. Inside SV_SaveApplyState both arms discard, so it is
  always reconciled there -- but SV_MsRecAttach's buffer branch returns without a
  discard, leaving a RUNNING run with the bit set and no recorder, and a later
  `retry` then writes that stale bit into its state file where Patch 441's third
  clause reads it. The void is still right in substance there (evidence really was
  lost, a session earlier), so this is "right for the wrong reason" rather than a
  false accusation -- but the bit is being trusted as a fact about now.
  sv_timer.qc SV_RecRewindStream, SV_RecClose; sv_resume.qc SV_MsRecAttach.
  Patch 441 review, round 5.
- **The cancel message names the wrong reason for a run that never had a recording.**
  Patch 441's clause 1 cancels a RUNNING attempt with no recorder on a server that
  records -- deliberately, and even when the run never had one (armed while
  rec_enable was 0, the operator turns it on, the player loads). The player then
  reads `run cancelled (the save's recording could not be restored)`, which asserts
  something false: there was none to restore. One string, two causes. The fix is a
  second reason word at the SV_TimerVoid call, and it touches what seven arms grade,
  which is why it is here rather than done. sv_saveloc.qc, the failed-rewind branch.
  Patch 441 review, round 5.
  THE SPLIT IS THE PREDICATE'S OWN CLAUSES, and the ARM ALREADY EXISTS -- both traced
  2026-09-26 so the work is a rewrite and not an investigation. `hadrec` or
  `retry && (flg & TF_RECORDING)` means a recorder really was there, so "could not be
  restored" is true; `SV_RecEnabled()` ALONE means the server records and this attempt
  never held one, which is the false case. Compute it once into a local and the void
  picks its word from that -- and the predicate becomes readable, which it is not now.
  cfg/test/p441twice.cfg's S2 is exactly the false case and already grades the string:
  measured, it prints `run cancelled (the save's recording could not be restored)`
  beside `recording 0` on an attempt restored a moment earlier that never held a
  recorder in this session. Nine cfgs and three drivers quote the string
  (p434rew.py, p439smoke.py, p441void.py's CANCEL), so the mechanical half is updating
  them to match either word and grading WHICH one at S2.
- **The void's "leave the box and enter it" is satisfiable by the velocity the
  same load restores.** Patch 441 re-scans the occupancy latches after a failed
  rewind so a cancelled run does not come back armed; the remedy assumes the
  player has to travel. A save taken just OUTSIDE a start box with its velocity
  pointed in gives `zs_az = -1` at the re-scan and an arm edge on the next tick as
  the body coasts in -- a clean arm, then the clock starts on the way out at the
  saved speed. Reachable without any void at all (load a non-RUNNING save outside
  the box), so it is not new, but the patch's stated remedy is weaker than "you
  must walk". sv_saveloc.qc SV_SaveApplyState's void branch. Patch 441 review.
- **The Multi-Session resume continues a RUNNING run with no recorder, under a
  flag that is not a taint.** `SV_SaveApplyState` returns at `if (retry == 2)`
  BEFORE the failed-rewind branch Patch 434/441 guard, and `run_ms_norec` leaves
  the attempt running while marking it only TF_MULTISESSION -- which sh_defs.qc
  and surfd both state is not a class, not in FS_RunClass or TF_UNCERT, and not
  read by surfd's `style_of`/`certifiable`. So a clean run whose `.rec` stops at
  the pause can rank. The size trigger (`run_resume_recmb` 512 MB) is out of
  reach; the live route is the copy-failure branch. Same absence decision as
  Patch 441's, resolved the other way, in code 441's own reasoning covers.
  AND THE BUFFER PATH HAS ITS OWN: `SV_MsRecAttach`'s `if (!ok) return;` after
  SV_RecRewind leaves a restored TS_RUNNING run with no recorder and no void, since
  SV_SaveApplyState returns at `retry == 2` before the branch Patches 434 and 441
  guard. `run_ms_norec` is the only thing standing there. Named by the fourth
  review round. sv_resume.qc:531-537, 573, 678. Patch 441 review.
- **At `run_zone_hull 2` + `run_zone_hull_live 1`, Patch 441's latch re-scan uses
  the PRE-load hull.** It passes `SV_RunHullMaxs(e)`, i.e. `e.maxs`, but
  SV_SaveLocPlace only sets `run_forceduck` -- the engine applies it in the next
  pmove -- so the re-scanned latch and the next tick's scan can disagree by the
  17-unit stand/duck difference, which is an arm edge, which is the laundering
  back. Inert at the shipped defaults (occupancy is a point test there and the
  hull arguments are ignored), so this is a note against those two cvars being
  turned on, not a live hole. sv_saveloc.qc SV_SaveApplyState. Patch 441 review.
- **Map triggers still touch a held (save-lock) body.** The engine skips touches
  only for `run_pmhold`; push-once triggers are spent for everyone, and every
  other trigger that writes velocity does so into a body nobody is steering. The
  timer ignores it since Patch 428 round 6, the side effects remain.
  PARTLY CLOSED BY READING, NOT BY A MEASUREMENT ON DISK: the func_bhop dwell
  the entry named should not fire on a held body (a save-lock hold is
  MOVETYPE_NONE, the mover runs PM_NONE for it, PM_NONE clears FL_ONGROUND and
  nothing writes .groundentity again, so SV_BhopFrame reads `ground 0` on every
  held frame and the dwell never arms). That chain is checkable in the sources
  cited below. THE MEASUREMENT IS NOT REPRODUCIBLE, though, and the entry said it
  was: the one-shot print it quotes (`bhop frame first: ground 0 isbhop 0
  movetype 0 slheld 1`) exists nowhere in `src/` -- it was instrumentation that
  did not survive the patch -- and the only instance of that print anywhere in
  ftesurf/logs reads `movetype 3 slheld 0` (p439svAO.log:143), i.e. an unheld
  walking body, not a held one. To close it for real: put the dprint back in
  SV_BhopFrame behind `developer`, drive p439cl.cfg's route, and grade the line. The half that is
  still open is the triggers a HELD body is already touching, and the
  push-once spend: those need the engine's `run_pmhold`-style skip to cover a
  save-lock hold too, which is an engine change.
  sv_entities.qc SV_BhopFrame, engine sv_user.c:8097 (MOVETYPE_NONE -> PM_NONE),
  sv_user.c:8887 (.groundentity written only when pmove.onground).
  Patch 428 review.

- **`SV_TrigPending`'s touch-bitfield clause goes blind above edict 32, and the fleet is
  configured at exactly 32.** `bit` is built only for `n < 32` and left 0 otherwise, so
  `(vbsp_touch_in | vbsp_touch_seen | vbsp_touch_out) & bit` tests `x & 0` and silently
  never fires (sv_entities.qc, `SV_TrigPending`). The `vbsp_touch_who` and `vbsp_iodelay`
  clauses still work, so the predicate DEGRADES rather than dying -- and the iodelay clause
  is the one covering the 0.06-0.09 s OnEndTouch window. `cfg/lobby/lobby.cfg` sets
  `sv_playerslots 32`: client edicts are 1..32, so `n` is 0..31 and every player is inside
  the mask today with EXACTLY zero headroom. Raise that for one event and player 33 loses
  the touch half of the test. It became a ranking concern in Patch 455, which made a
  forgiveness depend on the predicate; before that it only gated spectate entry. Fix is
  either a second word for 32..63 or a per-entity scan instead of a mask; the cheap
  mitigation is a refusal to raise `sv_playerslots` past 32 without doing the first.
  Found by a reviewer on 455 round 3, verified against the source and the cfg.

- **`run_t_hopsaid` IS ONE LATCH FOR TWO REMINDERS, and every site that clears it has to
  choose which one it is wrong about.** It suppresses both the hopped-start reminder and the
  `run_t_dirty` reminder. The ZONE_END arm deliberately leaves it alone, because clearing it
  re-opened a message about a taint the finish does not forgive (see the field's own
  comment); `SV_TimerForgiveHop` clears it, because that IS a forgiveness; and Patch 455's
  take clears it for the same reason as ForgiveHop. So the tree is self-consistent only
  because each site reasoned separately, and the next site will have to as well. The real
  fix is two latches -- the two reminders are about different taints and should not share a
  bit. Small, and it wants its own patch rather than being folded into a gate change. Cited
  by 455's take-site comment, which is why this entry exists.
- **A plugin's cvar flags are still masked down to CVAR_ARCHIVE for everything except
  CVAR_CHEAT and CVAR_SEMICHEAT.** Patch 460 widened `Plug_Cvar_GetNVFDG`'s `flags&1` to
  the restrictive flags only, because those can nothing but refuse a change. Still
  discarded, in the hl2 plugin alone: **`CVAR_SHADERSYSTEM` 25 times, `CVAR_MAPLATCH` 14,
  `CVAR_NOSAVE` 6, `CVAR_RENDERERLATCH` once.** So 14 cvars that say they latch to a map
  load do not, and 25 that say a change flushes shaders do not. `mod_hl2.c:1480` reasons
  at length about `hl2_propcollision` being MAPLATCH and it never was; `cl_gfx.qc`'s `*`
  "needs a reload" convention is the mod compensating for that on its own side.
  **Why it was not done in 460:** a MAPLATCH set stops updating the cvar's value until a
  reload, so every menu row over one would redraw the number the user did not choose --
  the exact confusion `Gfx_Inert` exists to prevent. It needs its own patch and its own
  pass over those 39 rows, not a line in a collision fix. `engine/common/plugin.c`,
  `PLUG_CVAR_FLAGS`.
- **`sv_prop_collision` is still a client-side desync vector, and it cannot be fixed the
  way the hl2 cvars were.** It picks the collision SHAPE at trace time -- mesh, convex
  hull or box -- and `pmovetst.c:402` reads it with `Cvar_Get("sv_prop_collision", "2",
  CVAR_SERVERINFO, ...)` on BOTH sides, so the client traces against its own local value.
  The comment there says "cvar is synced to the client, so both sides pick the same mode"
  and **that is not true**: there is no generic serverinfo-to-cvar path in this engine.
  `CL_CheckServerInfo` reads named keys one at a time into `movevars` (`cl_main.c:3310+`),
  and `sv_prop_collision` is not one of them. Today both sides agree only because
  `default.cfg` and `defaultuser.cfg` both say 1.
  `CVAR_CHEAT` is NOT the fix here: it force-sets to the REGISTRATION default, which is 2,
  and FTESurf wants 1 (mode 2 has no Source hulls and falls back to a box). A `set` in a
  config does not change a default -- `CVAR_CONFIGDEFAULT` is defined and nothing ever
  assigns it -- and the engine is shared with nettest, which wants the 2.
  **The fix is `movevars`**, the mechanism this engine already uses for every other
  "the client must use the server's value" case (`pm_slide`, `pm_maxvelocity`, and the
  note at `cl_main.c:3327` about `sv_maxvelocity` desyncing by construction until it
  became serverinfo). Add the mode to `movevars`, set it server-side from the cvar and
  client-side from serverinfo, and read `movevars` in `pmovetst.c` -- then the client's own
  cvar cannot affect its prediction at all, which is stronger than a cheat latch.
  Not measured live: no run has yet been made with the two sides deliberately disagreeing.

## Engine client-security audit (the `p482` batch) — 2026-10-05

Five holes in the engine's server-to-client command surface were **driven** on
2026-10-05 — measured, not just read — against a build of engine `798fda84b`.
The audit, the arms, the logs and the reasoning live in the private repo
(`C:/FTESurf-private/ENGINE_SECURITY.md`, `poc/p482/`); AGENTS.md's rule is that
live bypasses stay out of this one, so each entry here names the code site, the
impact class and a falsifier, and no recipe.

The arms are deliberately **not** in `ftesurf/cfg/test/`. They are working
exploits for holes that are still open and this repo is published; the convention
is that an arm ships publicly with its fix, not before it. Copy them in from
`poc/p482/cfg/`, run, delete.

FIXED AND DRIVEN since that paragraph was written: items **4, 7, 8** (Patch 483),
**5, 6, 9** (Patch 485), **1** (Patch 487, `poc/p487/`), **2** (Patch 488,
`poc/p488/`), **3** (Patch 489, `poc/p489/`) and **10** (Patch 491, `poc/p491/`).
Item 1 was the one that defeated all the others -- a server-planted `f_newmap` alias
ran its body at `RESTRICT_LOCAL`, so every `Cmd_IsInsecure()` gate read 29 for it;
item 2 was the last route to arbitrary native code execution, a server naming the DLL
the renderer loads; item 3 was the last unbounded copy of a server-supplied string,
and its canary build measured the write reaching 172 bytes past a 128-byte global;
item 10 was the last unarmed one, and arming it DISPROVED the audit's own note that
the route "needs a local/listen server first" -- a plain connected client was enough.
**EVERY DRIVEN ITEM IN THAT AUDIT IS NOW FIXED.** What is left is the lower-value list
that was never armed (see the bullet below it), and item 10's own residual.

- **`TP_ExecTrigger`'s multi-command branch is fixed but never DRIVEN, and the reason
  is a server-side filter that a real attacker does not have to obey.** Patch 487 sets
  the level for both of `TP_ExecTrigger`'s branches (`Cmd_ExecuteString` for a
  single-command body, `Cbuf_AddText` for one containing `;`) and for
  `TP_SearchForMsgTriggers`, but the arm could only plant a single-command body:
  `stuffcmd` refuses any string containing `;` or `\n` ("You're not allowed to
  stuffcmd that", `server/sv_ccmds.c` `SV_Stuffcmd_f`). That filter is in the CONSOLE
  COMMAND, not in the wire path, so a server sending `svc_stufftext` itself -- or its
  own QC's `stuffcmd` trap -- still reaches the `Cbuf_AddText` branch. The fix covers
  it by construction and the local-alias regression control exercises that branch at
  `RESTRICT_LOCAL`, but no arm has watched a SERVER alias take it.
  `client/zqtp.c` `TP_ExecTrigger`; `common/cmd.c` `Cmd_AliasExecLevel`.
  Falsifier: plant a multi-command body by a route that is not the `stuffcmd` console
  command (a test-only QC `stuffcmd`, or a raw `svc_stufftext` from a stub server),
  change map, and grade by string -- the payload must print
  `Blocking insecure command`, and the same body created locally must still run.
  Note when writing it: a multi-command body's execution is DEFERRED (~94 s measured,
  draining during the client's own quit) and the client's `quit` re-fires `f_newmap`
  twice more, so neither position nor count is a verdict -- only presence/absence of a
  string one cause alone can produce. Patch 487 review.
- **A server-named renderer DLL is refused now, but the ARCHIVED route is not gated
  and the reason is a measurement, not an oversight.** Patch 488 refuses an explicit
  subrenderer token from an insecure caller, which closes
  `stuffcmd * setrenderer "gl <path>"` -- the route a canary DLL proved, its `DllMain`
  running in the client's pid. What it does NOT gate is `vid_renderer` itself: the
  cvar is `CVAR_ARCHIVE`, `ftesurf.cfg` really carries a `vid_renderer` line, and
  `+set vid_renderer "gl <path>"` loads the DLL at BOOT, before any map. That is a
  LOCAL actor's own setting at `RESTRICT_LOCAL`, so gating it would take a user's
  renderer choice away from them, and the only way a SERVER could plant that value was
  `saveconfig` writing `cfg/` -- which Patch 483 closed. So the chain is broken at its
  first link and the remaining link was never demonstrated end to end.
  `client/renderer.c` `R_BuildRenderstate`; `common/cvar.c` `Cvar_LockFromServer`
  (`CVAR_SERVEROVERRIDE`). Two falsifiers, either of which reopens this:
  (a) drive `poc/p482/cfg/p482e.cfg` (item 8's arm) against a current build and show
  that a server can still get a `vid_renderer` line into `cfg/` or `data/cfg/`;
  (b) show a stuffed `set vid_renderer "gl <path>"` surviving to a later
  `vid_restart` -- Patch 482 measured the opposite (`GLInitialise` printed `Reusing
  renderer dll`, the canary did not run, the cvar read "" afterwards), which is the
  only reason the obvious extra gate is not in the patch. THAT GATE WOULD BE
  `vid_renderer.flags & CVAR_SERVEROVERRIDE`, and it is deliberately absent: it would
  refuse a local user's explicit `setrenderer gl <path>` for as long as a server held
  that cvar, i.e. a local false positive defending a route measured dead. If (b) ever
  fires, add it at the `vid_restart` caller rather than in `R_BuildRenderstate`, so a
  token the user typed themselves is never refused. Patch 488 review.
- **`Cmd_Alias_f` concatenates every argument into a fixed 65536-byte stack buffer
  with `strcat`, and the tokenizer that supplies them is not bounded to match.**
  `common/cmd.c`, the `for (i=2 ; i<c ; i++) { strcat (cmd, Cmd_Argv(i)); ... }` loop
  over `char cmd[65536]`.  `MAX_ARGS` is 80, so the ARGUMENT COUNT is capped, but each
  argument's LENGTH is not: `Cmd_TokenizeString` allocates its store with
  `Z_Malloc(len+1)` sized to the input, so a single long argument is copied whole.
  `alias` is server-reachable through stufftext -- which is what Patches 481/485/487
  all exercised -- and a server-supplied value longer than the buffer would run past a
  stack array.  FOUND BY A SWEEP, NOT BY A CRASH: Patch 489 audited the same class
  (`strcpy`/`strcat`/`sprintf` fed directly by `Cmd_Argv`, across `client/*.c` and
  `common/*.c`) after fixing `allskins`, and this was the one hit whose bound did not
  obviously match its input.  **NOT MEASURED, and the missing measurement is the whole
  question:** whether a >64 KB stufftext is deliverable at all.  `svc_stufftext` rides
  the reliable channel, which is chunked across packets, so length is not obviously
  capped by one datagram -- but nothing here proves it, and the cbuf may impose its own
  limit first.  Do not quote an impact class until that is settled either way.
  Falsifier: stuff an `alias` whose value exceeds 65535 characters and look for a crash
  or a corrupted neighbour; if the transport refuses it first, the finding closes as
  unreachable and THIS ENTRY should say so rather than be deleted, because the next
  reader will sweep the same class.  A fix, if it is needed, is a bound on the
  concatenation (refuse or truncate with a printed warning) -- not a gate, since a
  user's own long alias is legitimate.  Patch 489 review.
- **`CL_SetInfoBlob_f` reads an arbitrary game-VFS file into the player's userinfo,
  which is sent to the server.** `client/cl_main.c`; `FS_MallocFile(..., FS_GAME,
  ...)` with no insecure check. Measured: a planted canary file's exact bytes went
  out on the wire as a `setinfo` blob. **The transmission is conditional** — the
  blob key is dropped unless the server negotiates `PEXT2_INFOBLOBS`, which is the
  server's own `_pext_infoblobs` cvar to advertise — so whether the bytes leave is
  the remote host's choice, not a limit the client imposes. The arm read a planted
  canary and the mod's own 53-byte consent record, and deliberately not
  `ftesurf.cfg` or `conhistory.txt`, which are in the same reach and can hold an
  rcon password and a command history; their reachability is a code fact, not a
  measurement. Fix: refuse insecure callers, the pattern `Cmd_Condump_f` already
  uses. Falsifier: the arm's wire line must disappear while its "file does not
  exist" control still prints, and the engine's own blob keys (vwep) must be
  unaffected.
- **The config writer's `data/` and `cfg/` exemption sits before its
  `Cmd_IsInsecure()` refusal, so a remote host can write a config into either.**
  `common/cmd.c`, the `saveconfig` path. Measured: the unprefixed form printed
  `not allowed` and both prefixed forms wrote a 64 KB real config to disk. The
  exemption is keyed on the path, not on who asked, though its own comment gives a
  mod-facing reason. `data/` is where this mod reads `mapdl.txt`, `mapmeta.txt`,
  `mapwr.txt` and `saves/**`. Fix: move the exemption after the insecure check, or
  apply it only to non-insecure callers — the same lesson as Patch 446, hang the
  rule on where the command ENTERS. Falsifier: the arm's two prefixed forms must
  print `not allowed` while a locally typed `saveconfig cfg/x.cfg` still writes.
- **Chained, the last two are a persistence path**: a written config carries
  `vid_renderer`, and `vid_renderer` at boot names a DLL to load. Plausible, and
  **not demonstrated end to end** — no arm here chains them. Worth deciding whether
  the renderer fix or the config fix closes it, rather than assuming one does.
- **`MSV_MapCluster_Setup`'s subserver FORK is refused now but never demonstrated, and
  the refusal is the only thing standing between a remote server and `CreateProcessW`.**
  Patch 491 gates the top of the function, so both command legs (`mapcluster`, and
  `SV_Map_f`'s auto-offload reached via a server-set `sv_autooffload` plus a stuffed
  two-argument `map`) are refused before `CL_Disconnect`. What the arm measured is that
  the victim was no longer dropped and no longer re-purposed into a cluster master --
  NOT that it can no longer spawn a child process, because the fork is several
  statements past the gate and no arm reaches it. `server/sv_cluster.c`
  `MSV_MapCluster_Setup`; `server/sys_win_threads.c` `Sys_ForkData` -> `CreateProcessW`.
  Falsifier: get past the gate by a route that is not a stuffed command -- a local
  console `mapcluster` with `sv_autooffload 1` set locally, which is `RESTRICT_LOCAL`
  and must still work -- and confirm a subserver process really appears; then confirm
  the same route stuffed from a server is refused. If a future patch ever needs the
  fork reachable from a server, the gate has to move to the fork itself rather than to
  Setup's entry, because Setup is also the legitimate single-player offload path.
  Also worth knowing for any future arm here: a server-set cvar's readback prints
  THREE lines and the first one is the LATCHED pre-override string
  (`"sv_autooffload" is "0"` / `Effective value is "1"` / `Default: "0"`), so a
  precondition control that matches the first line reports a held precondition as an
  unheld one. Patch 491 review.
- Items 4, 5, 6, 9 and 10 of the audit (`fs_changegame`'s early returns, `gamedir`,
  `fs_restart`, `mapfrom`'s prefer-hint leg, `ssv`/`mapcluster`'s `CreateProcessW`)
  were **traced in the source but not driven** when that line was written. All five
  have since been driven and fixed (483, 485, 491); what remains unarmed is the
  audit's LOWER-VALUE list -- `fs_cache_clear`, `fs_loadlist`, `fs_whereis`,
  `fs_filenamelist`, `fs_whichpack`, `fs_dumppathconfig`, `fs_paksettings`,
  `fs_loadpaks`, `fs_dumpcfg`, `fs_filedigest`, `fs_manifests` -- which is a census
  of read-only `fs_*` commands rather than a set of findings. None has an arm, so none
  has a verdict, and Patch 485's sweep is the reason not to assume that list is
  harmless: `fs_indexmaps` looked read-only and was writing and mounting.

## Performance

- **A 999-save rescan is synchronous: 157 ms on the Pi** (profile_ssqc,
  p428cl). Once per player per map, plus once per reconnect with another
  certificate -- alternating two certificates with 999 saves each is a
  player-ordered stall. Half is the directory walk (one search_begin), so the
  fix is an index file or an incremental scan, not a tweak. sv_saveloc.qc
  SV_SaveLocScanBlk.
- **A 999-row delete-all takes ~5 s** (~3.5 ms per row on the Pi: FS_Remove
  re-walks every search path to update the name hash). It sweeps 2 rows a frame
  and is harmless, just slow. Engine fs.c FS_RebuildFSHash_Update.

## Features / releases

- **Rewind v2 -- what Patch 477 left (2026-10-03).** (1) The continuation after a
  resume is untimed and unrecorded: the server's ring and the client's line take
  samples only while a run is on the clock, so what you do after a resume cannot
  be rewound until the next run starts (the mode reopens at the last resume point
  instead). A TIMED continuation needs the recorder to rewind to a tick it never
  saved a prefix for -- the ring would have to carry the stage machine, splits and
  zone latches per sample, or the .rec be cut at a line index found by tick. (2)
  Rewind inside a replay or a Momentum demo ("continue from any point" of someone
  else's run): a save built from a client-supplied state, which must be practice
  by construction and raise the hopped tag whatever its speed. (3) `rec_watch` is
  the one WRITE command in this family that is not behind `SV_SaveLocRate` (the
  dispatcher charges every `sl_` stringcmd, 20/s, and this one does not start with
  `sl_`), so a client can pin and void at packet rate. Low harm as it stands --
  a void ends the run, so the cost is self-inflicted, and `SV_ViewEyeAt` reuses
  the eye entity rather than spawning one -- but it is an uncharged write and the
  rate exists for a reason. Falsifier: a client sending `cmd rec_watch 1 rw <n>
  <t>` / `cmd rec_watch 0 void` in a loop keeps a run ending and re-pinning with
  no "too many" refusal, where the same loop of `cmd sl_save` is refused.
- **A MAP THAT DISAGREES WITH THE SERVER AT THE SAME SIZE IS STILL A KICK, AND
  NOTHING CLIENT-SIDE CAN SEE IT.** `ui_prejoin` (build 89) fetches the server's
  build before connecting when the map is missing or its size differs, which is
  every case the browser can judge. It cannot judge equality: measured, the Pi's
  `surf_rookie` and this workstation's are byte-identical -- 8,377,611 bytes,
  sha1 `1dd30123a38fded6bedad1915390fd01850cee03` -- so a third install that
  disagrees with both may match on size and sail through.
  The authoritative answer exists and we throw it away. The server compares BSP
  model checksums (`sv_user.c:2298-2320`), and on a mismatch it sends
  `//kickfile "maps/<name>.bsp"` NAMING THE FILE before dropping the client.
  `cl_parse.c:7660-7670` handles that stufftext by PRINTING it and nothing else.
  The fix is an engine patch: hand the name to QC (a cvar set in that handler is
  enough), and the menu can force-download exactly that file and reconnect -- it
  already has `downloadmap(name, 1)` from Patch 466 and the address it just
  connected to. Not started: it needs an engine rebuild and a shipped exe, and
  it should not begin until Lex says whether `surf_rookie` reads "Wrong build"
  on the laptop, because if it does, the size check already covers that case and
  this buys nothing for it. lextest 2l (r).
  Note that the client cannot PREVENT the kick this way, only repair it: the
  checksum is computed from the loaded BSP, so nothing short of loading the map
  can answer the question before connecting.


- **A segment's air percentage still reads over 100% when the energy came in
  HORIZONTALLY (Patch 464).** `Seq_Push` divides the row's energy change by
  `seg_emax`, and build 89 made that bound the total: a running high-water mark
  adds any rise the flat-air ceiling cannot explain to the ceiling itself, so a
  booster or an unseen hop is neutral rather than a 400% row. What it bounds is
  the row's OWN energy, which is the right quantity, and the simulator at
  `<scratchpad>/hopsim3.py` shows 0 rows over 100% across perfect, sloppy,
  autobunny and boosted flights with the sloppy rows byte-identical to build 89.
  The gap left: the rule fires on the frame the energy arrives, so a push whose
  gain is spread thin enough to stay under one tick of ceiling per frame is
  invisible to it -- measured at 10175 of 17021 impossible ticks under a single
  unit of height across 300 .rec files. Those are individually noise and could
  sum on a long conveyor. The fix wants the excess attributed per TICK rather
  than per rendered frame, which means the server, which is where
  `run_basevelocity` already lives.
- **Ramp rows are not graded at all, which on a surf map is most of the column.**
  `seq_pct` is `-1` for `SEG_RAMP` by design -- the flat-air ceiling does not
  describe a plane, and `Strafe_PlaneBest`/`Strafe_CScale` (which do) are not
  wired into the segment ceiling. Worth doing, and it is a SEPARATE job from the
  over-100% work above: walking 300 .rec files tick by tick, the recorder's ramp
  bit appears on NONE of the 17021 impossible ticks, so a plane-aware ceiling
  would not have moved a single over-100% row. It would give surf players a
  number where they currently get a dash. Same blocker as the trainer entry
  below: the normal and the pre-clip velocity at the right cadence.
- **The strafe trainer grades flat air only, so on a surf map it is blind
  exactly where the map is (Patch 462).** `hud_trainer` scores each strafe with
  `Strafe_Quality(rate, Strafe_IdealTurn(...))`, which is the FREE-AIR ideal. On
  a ramp the ideal is `Strafe_IdealTurnPlane` instead -- a different function of
  the plane normal, measured in `sh_strafe.qc` at 55.2% of the flat ideal at
  `wn +0.8` and 16.8% at `-0.8`, so reusing the flat number overstates the target
  by between 1.8x and 6x. Rather than grade a ramp against the wrong target,
  `Trn_InputFrame` counts a ramp tick into the strafe's DURATION and not into its
  grade (`trn_s_gdur` is the divisor) and the coach line says "on a ramp -- the
  bar grades that". Correct, and it means a surf player's rows are mostly
  ungraded. The blocker is cadence, not maths: the trainer samples per usercmd in
  `CSQC_Input_Frame`, and the plane normal there is `STAT_FS_RAMPCONTACT`/
  `STAT_FS_RAMPNORM`, a snapshot behind, while `HUD_DrawStrafe` also needs the
  PRE-CLIP velocity to go with it. Either establish that those are good enough at
  input cadence (measure it -- do not assume, the whole reason speed comes from
  the stat is that prediction jitters by a tick), or move the per-tick grade to
  the server where the normal is exact and send the finished per-strafe record.
  Bhop maps, which is what it was asked for, are unaffected.
- **`tools/mapmeta.py`'s `MAPDIRS` omits the Momentum install -- the FIRST and
  largest mount -- so the tier alias pass has never considered most of the
  library.** `ftesurf/fs_addons.txt` mounts `Momentum Mod Playtest/momentum`,
  then cstrike, then hl2, earlier winning. `MAPDIRS` (`mapmeta.py:159-163`) lists
  only `ftesurf/maps` (4 BSPs), cstrike (1084) and hl2 (79), so
  `installed_maps()` returns **1165 of the 1419 names the engine can load** and
  every one of Momentum's 1316 is invisible to `alias_rows()`. Harmless for the
  case it was written for (Momentum's own maps carry real leaderboard rows and
  need no alias) and wrong for anything asking "which builds of this map can be
  loaded". Patch 463's variant work needed the real set and added
  `mounted_maps(momentum)` beside it rather than widening `MAPDIRS`, because
  widening it changes which tiers get aliased and that deserves its own
  measurement. Do that measurement, then collapse the two.
- **Re-running `tools/mapmeta.py` LOSES DATA, measured 2026-09-28.** A
  regeneration over an existing `ftesurf/data/mapmeta.txt` dropped the
  `surf_strike` row entirely -- tier 5, `sugg`, thumbnail
  `b0a5f058-ca96-4f9c-a75a-543efaf3c326`, and the map is installed in BOTH the
  Momentum and cstrike mounts -- and blanked page/cell on 8 rows that still
  exist: `bhop_aperture_kinetic_lab`, `bhop_arcturus`, `bhop_cooksassistant`,
  `bhop_greenbox`, `bhop_greybox`, `bhop_peribox`, `bhop_tealbox`,
  `df_maroonbox`. So `keep_atlas` does not carry forward everything it should,
  and something in `build()` is not stable across runs. 2271 meta rows before,
  2294 after, 1 lost. The run that found this was reverted from its backup rather
  than shipped, so the table on disk is the pre-run one -- which means the
  `variant` rows `write()` now emits are NOT in it yet, and generating them needs
  this fixed first. The module docstring already warns that `--report` used to
  mutate its input; this is the same class one level down.
- **Patch 427's client half is not in a release.** Clients quote `download`;
  until players update, the lobbies' server half is what lets them join maps
  with spaced sound names. Ships with the next `release.ps1 -Bump patch`.
- **Only `2` is drawn early (Patch 430).** 3/4/5/6 move the cursor and load in
  one server step and their target row is not published; the release after a
  hold still waits a round trip for the server's unfreeze (the second `prederr`
  line on each load).
- **IN-GAME MAP DOWNLOAD, A "NEW" BADGE, AND A 6-HOURLY UPSTREAM SCAN -- asked
  for 2026-09-28, surveyed and NOT started.** Three decisions were taken with the
  operator at survey time: the button fetches **from the Pi, which fetches through
  to Momentum's CDN and keeps its copy** (so the Pi stays the authority on which
  build is canonical); the scan **polls the Momentum API every 6 hours**; and the
  KSF Google Drive is **a map source beyond what is on disk** (its share link is
  still needed -- nothing in this repo or in `wrlines` knows the Drive exists).
  What follows is the survey, because most of the pipeline is already built and
  the parts that are missing are not the parts the request names.

  **THE REQUEST'S KSF PREMISE IS INVERTED: EVERY KSF MAP IS ALREADY HERE.** 55
  `_ksf` BSPs across the Momentum and CS:S mounts, **0 missing**. 26 already run
  on DONATED zones -- `tools/census/zonefit.py` graded a donor build FIT on frame
  and destinations, `tools/zoneinstall.py` installed it, and
  `ftesurf/maps/zones/manifest.txt` records all 26 as `donation` (25 FIT, 1
  NO-DESTS). Of the 29 unzoned, exactly **2 are recoverable by that same path
  today** (`surf_derpis_ksf`, `surf_lullaby_ksf` -- their base builds are zoned
  and installed); the other 27 have no zoned base anywhere on disk. And
  `ksf.surf`'s API is players and records only (`wr_ksf.h:65,70,74` -- search,
  bestrecords), with **no map list and no zone data**. So the KSF gap is ZONES,
  and KSF cannot supply them; a downloader answers a question nobody asked.

  **THE MAP LIST CANNOT SHOW A MAP YOU DO NOT HAVE, AND THAT IS ONE LINE.** The
  library IS the filesystem: `m_main.qc:1668` is
  `search_begin("maps/*.bsp", SB_FULLPACKAGEPATH|SB_ALLOWDUPES|SB_NAMESORT)`, and
  `m_main.qc:1257-1259` throws metadata away for anything unmounted
  (`continue; // metadata for a map that is not mounted`). That `continue` is what
  hides **1551 of `data/mapmeta.txt`'s 2271 rows** -- the download button's entire
  audience. The 639 listed maps with no metadata (`m_main.qc:280`, of 1334 listed)
  are a DIFFERENT gap: they are visible and untiered, not invisible.

  **THE ROW'S RIGHT EDGE IS FULL -- the button needs space taken, not found.** The
  PB time is right-aligned at `rp_x + rs_x - 8 - mtw` (`m_main.qc:4402-4414`),
  reserves its width even when blank (`"--:--.---"`, `:4413`, deliberately so the
  headcount does not jump while scrolling, `:4394-4400`), widens by a
  `"^9lobby  ^7"` prefix (`:4409`), and vertically straddles both text bands, which
  `m_main.qc:4435-4439` says outright: a second right-aligned item "would draw
  through the time". The two centralised places to buy room are the `mtw`/`mpopw`
  anchors (`:4414`, `:4448`) plus the `ui_fit_text` budget (`:4464`), or the 36 px
  tier gutter (`rp_x+90` to `rp_x+126`).

  **THE DOWNLOAD ALREADY FAILS TODAY, WITH A LOGGED LINE** -- see the existing
  entry on `Server permissions deny downloading file "package/maps/<map>.bsp"`.
  The fleet sets no `allow_download*` at all and runs engine defaults, which are
  permissive (`allow_download 1`, `allow_download_maps 1`, `sv_main.c:89,95`), so
  the refusal is not a policy knob: the server advertises the BSP as a PACKAGE and
  `SV_AllowDownload` refuses non-pk3 packages. Under that sits the real veto --
  `SV_LocateDownload` (`sv_user.c:4215-4249`) denies any file in an
  `SPF_COPYPROTECTED` searchpath, which is what a Steam-mounted `momentum/` is.
  The engine already carries the opt-out, `sv_allow_download_anything` (nettest
  Patch 37, `sv_main.c:108`, `sv_user.c:3967-3977`, `:4219-4221`), default 0 and
  set nowhere here -- and it is a `sv-rel` patch, so it is DEAD in a stale server
  binary. `sv_dlURL` is `CVAR_SERVERINFO` (`fs.c:330`) and empty everywhere.

  **ZONES ARE NEVER SENT TO A CLIENT, so a downloaded map arrives untimeable** --
  no `precache_file` anywhere in `src/server/*.qc`. The good news is that
  `SV_AllowDownload`'s `maps/` gate is a PREFIX, so `maps/zones/online/<map>.json`
  is already permitted BY NAME under `allow_download_maps 1`, and Patch 463 made
  the zone pin compare fields rather than the path, so a downloader may write to
  either `local/` or `online/` without refusing recordings. BSP and zone must
  travel as an atomic pair for the same reason `mapsync.py:15-21` gives.

  **WHAT IS ALREADY ON THE PI, read from the host 2026-09-28 and not in this
  repo.** `sites-enabled/` holds `fastdl`, `mom.conf`, `momcdn.conf`,
  `nettest-dl.conf`, `filebrowsers.conf`, `play.proto.bar.conf`. `fastdl` is real
  but is SVEN CO-OP's (`:8082`, root `/srv/nvme/Archives/SvenBackup/...`, serving
  `.bsp` out of `.bsp.gz` with `Content-Encoding: gzip` -- a working recipe worth
  copying). **`momcdn.proto.bar` terminates TLS and proxies `127.0.0.1:9000`,
  which is a live MinIO** (`Server: MinIO`, region `us-west-1`). **`mom.proto.bar`
  serves a clone of the Momentum monorepo at `/root/mom`** with `/api/` proxied to
  `127.0.0.1:1245`. Do not overstate this: the API on 1245 is **DOWN**, socket.io
  on 9132 is down, `STORAGE_BUCKET_NAME=momtest` is still the template default and
  every bucket answers 403 -- it is an unfinished local-dev deployment, not a
  running CDN. But the hard part (public hostname, cert, object store) exists.
  Disk: 458 G, **77 G free** (83% used); `mapsync.py`'s `HEADROOM_GB` is 5.
  Consequence for the chosen design: a self-hosted Momentum API would make the
  6-hourly poll hit the operator's OWN server, which is a materially different
  proposition from polling `api.momentum-mod.org`, and is worth settling first.

  **WHAT A DOWNLOAD COSTS, measured on the 1316-BSP install:** 45.0 GB total,
  median **23.1 MB**, mean 35.0, p90 76.9, max 494.6; 78% exceed 10 MB and 5.9%
  exceed 100 MB. The Pi serves 12 live lobbies off one home uplink, so
  concurrency and rate need a ceiling before this is switched on -- `ftesurf.nginx:37-72`
  already has the shape (`limit_rate_after 512k; limit_rate 2m`).

  **THE "NEW" SIGNAL: DO NOT USE `dataTimestamp`, OR NORMALISE IT FIRST.** Zone
  files carry one, and it is read by NOTHING today, so this is a prospective trap
  rather than a live bug. Measured: Momentum's own `zones/online/` is 537 files,
  524 in milliseconds and **13 in SECONDS** (2.4%); this library's 609 hold 15 such.
  Read as ms they date to **1970-01**, i.e. a badge or sort keyed on that field
  ranks them permanently oldest and a "newer than last scan" scanner never fires
  on them -- the silent direction. A guess that these were the hand-authored files
  was FALSIFIED: Momentum's own `zones/local/` is 14 files and all 14 are
  milliseconds, so the inconsistency is UPSTREAM in API-sourced data and will keep
  arriving. The robust answer needs no upstream date at all: record first-seen
  ourselves, append-only, on each scan.

  **AND THE TIMER IS BLOCKED ON A KNOWN DEFECT** -- see the entry above on
  `tools/mapmeta.py` losing rows across a regeneration. A 6-hourly job that
  regenerates `data/mapmeta.txt` would run a generator already measured to drop a
  row and blank 8 rows' page/cell, unattended, four times a day. Fix idempotency
  first; the falsifier is free (run it twice, diff must be empty).

  **STAGING, cheapest and most-blocked first.** (1) make `mapmeta.py`
  regeneration lossless -- gates everything on a timer. (2) the two recoverable
  KSF zones, via the existing `zoneinstall.py` path, no new code. (3) emit rows for
  catalogued-but-absent maps and relax the `m_main.qc:1257` `continue`, so the
  1551 become visible as unavailable -- the lobby cell's `"^1not installed"`
  treatment (`m_main.qc:4211-4227`, and the cell is deliberately unclickable in
  that state, `:4245-4247`) is the precedent. (4) first-seen roster and the New
  badge; `data/mapmeta.txt` takes both with NO reader change, because the reader
  skips any line whose first token is not `meta` and guards trailing columns with
  `n >= 11` (`m_main.qc:1250-1275`). (5) trace and fix the `package/maps/` denial,
  then serve BSP+zone from the Pi. (6) the button itself -- and note the menu has
  exactly ONE `URI_Get_Callback` per VM (`m_lobby.qc:885-931`, `responsecode == 0`
  is success, not 200), so anything new branches inside it; a per-row button
  registered after the row STEALS the row's hover, because sui walks front to back
  (`sui_sys.qc:296,347,409`) -- use `sui_hover_index`/`sui_release_index`, and act
  after `sui_end` or the release fires twice (`cl_scores.qc:1273-1299` is the
  working precedent). (7) the Drive, once its link exists.

## Run-line/rewind reports — Lex, 2026-10-07

These are reported defects to reproduce, not confirmed root causes or fixes.
The full requested feature plan and delivery order are in ROADMAP.md section 12.

- **Input parity still open after P544's bare-bind demo scrolling.** P544 adds
  held demo navigation with physical ownership and opposing-key cancellation.
  Full-chain controls at 30/100/300 and native pinned-body checks pass. Imported/
  native long demos, compound/modifier binds and actual-device focus acceptance
  remain open. P550 closes live rewind opposing-key cancellation: both press
  orders stop; either release ACTS; same-side owners continue until the last
  release. P554 adds live focus-loss cancellation without forgetting physical
  ownership: chat/menu/console and synthetic keyboard-focus loss stop held
  navigation, return/repeats stay stopped, and a fresh press ACTS. Whole-chain
  controls and delivered releases pass at 30/100/300 FPS; actual-device/OS-event
  delivery, compound/modifier binds and broader demo acceptance remain open.
  Broader falsifier: remap/hold/release in native/imported demos, close/change
  focus while held; no dangling repeat or movement leak. Plan 12.2.
- **Repeated stitched rewind has zero-speed pauses/time creep followed by a
  jolt.** Lex reports several cut/resume attempts producing stationary stretches
  while the displayed timer updates. Failed-tail/hold-time capture is only a
  hypothesis. Sites: `cl_trailstate.qc` raw history/trim/restore,
  `cl_trailreplay.qc:Trail_RewindPrefix/Trail_ReplayPrefix`, and
  `cl_rewind.qc:Rewind_Cursor/Rewind_Frame/Rewind_Camera`. Falsifier: perform
  at least three cuts with a long failed-attempt wait, warm and cold prefixes;
  compare retained raw samples, stitch indices/times and fractional cursor pose
  both ways. No leaked idle tail, synthetic speed-zero plateau, clock creep at
  a fixed cursor or unexplained jolt. Real pause/teleport controls must remain
  explicit; P502 authoritative held clocks/save/go contracts still pass. Plan 12.3.
  P539 repairs the measured cold-stream attachment-lineage defect. All six
  warm/cold cuts pass in buffered and streamed dedicated controls, including
  native selected-snapshot body/clock, counted >4s failed waits and frozen holds.
  The local attachment key is not an evidence run ID/nonce; generation and
  stale/other-lineage guards remain strict. `tools/stitched_rewind_smoke.py`
  retains the full oracle and native probes, with grader counterfactuals in
  `tools/test_stitched_rewind_smoke.py`. Human path/camera feel and the broader
  wait-tail/presentation/event/compare cases above remain open. Never trust
  client history as server state or trim the picture to a requested clock when
  the authoritative body went elsewhere. P540 repairs two measured presentation
  boundaries: raw break/stitch columns now stop velocity/view interpolation,
  and chase tangents stay within the continuous span. Nine compiled controls
  and quarter-point scans of both camera modes pass at caps 30/100/300; this is
  not human moving-camera acceptance or complete teleport/event parity.
  Native-event tooling after P542 additionally passes engine-driven keep/zero
  velocity volumes on real map ground, counted six-second stops and fixed-cursor
  pinning at 30/100/300 FPS, with 44 counterfactual checks. Authored BSP teleports
  and human camera acceptance remain open. `tools/native_trail_events.py` reports
  native-instant/first-raw-break offsets rather than asserting pose simultaneity;
  snapshot angle/body arrival ordering needs a UX trace if the jolt persists.
  Camera capture follow-up is complete: frame barriers survive blocking PNG
  encoding, final-render probes match first/chase/return, world pixels change
  then restore at 30/100/300. Authored BSPs and human acceptance remain open.
- **Low-FPS requested cursor differs from the restored native snapshot.**
  Sites: `cl_rewind.qc:Rewind_Go`, `sv_saveloc.qc:SV_RewindFind` and visual
  prefix/trim acknowledgement. The dedicated 30-FPS buffered six-cut fixture
  retained 0.690 for a 0.735 request and 1.545 for a 1.500 request on both
  P539 and P540. These are visual endpoints, not necessarily native selections:
  the original native probes hold tick 49 (0.735) and tick 103 (1.545).
  P542 repairs the first case's demonstrated raw-clock roundtrip loss in
  `Trail_Trim/Trail_Save/Trail_Load`: the six-decimal 0.735 row decoded above
  the unrounded float32 cutoff. A complete ring/request/ack audit independently
  reproduces all six nearest-position choices and exact acknowledged prefixes
  at 30/100/300 FPS; strict requested-clock checks also pass in the new matrices.
  This is not universal requested/native equivalence. `SV_RewindFind` still
  chooses the closest position within `RW_NEAR`, and the original forward
  45 ms difference remains a separate selection/UX gate. Current P554-source
  audit passes thirty local selections at caps 30/100/300 and both clients,
  including exact requested/native/raw 0.735; offsets are -15..+30ms, not proof
  of universal equivalence. A configured/read-back 30ms packet-delay arm ACTS
  and fails the unchanged requested-clock check on warm +60/+60/+45ms choices.
  Full native-ring enumeration, correlated ack, native body/clock, exact retained
  prefix, hold/release/counting and camera checks pass all six delayed cuts;
  nearest-clock-only selection gives a worse position match in those captures.
  Do not change native selection solely to make a requested-clock oracle green.
  Falsifier: instrument requested sampled clock/pose, selected native snapshot
  clock/pose and acknowledged visual bound together at 30/100/300 FPS, with
  explicit latency and repeated-pose tie controls. P560 delivers the presentation
  distinction: sampled request, waiting, and correlated native/request/delta,
  with no invented clock for untimed/missing metadata. Four delayed six-cut
  matrices and five real repeated-position/window/tie units pass; strict clock
  equivalence remains red. General pose/clock alignment is NOT closed by that
  caption; keep the strict-red arm and independent native/body/prefix gates. Repair
  alignment without weakening body/prefix checks, inventing authoritative state
  or retiming the recording. Keep genuine stops and discontinuities explicit.
- **"Off ramp" labels appear well beyond the actual ramp exit.** Sites:
  `cl_lines.qc:Line_Contact/Line_Point/Line_Marks`, `Board_RampHeld` and the
  native per-tick raw contact/normal producers. The line classifier uses held
  contact; establish its contribution versus sampling/render delay before
  changing it. Initial diagnostic: `tools/OFFRAMP_CONTACT.md` separates native
  per-tick bit/normal, sampled held kind, event creation and actual rendered
  position; private acted 30/100/300 captures and counterfactual refusals measure
  the stages, not a classification fix. Packet/stat clock jumps must not be
  mistaken for a longer configured hold. Separate authored static-brush
  trajectories now bind actual hulls to full native/joint edge/input/jump/seam
  queries and real open/ceiling-blocked duck cycles with five-arm body parity.
  A real capsule ramp/departure actor also binds winning/tick/contact snapshots
  and native hit/miss/capsule-vs-box controls, retaining explicit capsule geometry
  ABSTAIN (no independent capsule oracle). A real translated/yaw world-brush
  actor binds native instance/hull snapshots and rotation-sensitive queries,
  with transformed geometry ABSTAIN (no independent transform oracle).
  Identity-solid results remain counterfactual, never body contact or misses.
  A matched non-world/removed-physent pair now ACTS a real physent-1 ramp winner,
  hit/miss/world-only removal queries and a different removed body trajectory.
  Actual entity/model/brush/hull binding and active-only joint AABB fixture
  queries pass; entity geometry/support remains ABSTAIN, never world support.
  A matched embedded BIH_MODEL/removed-parent pair now ACTS a depth-1 child-brush
  winner, native removal queries and physically different removed trajectory.
  Child/root/model/whole-brush/hull bind while embedded geometry/support ABSTAIN;
  actual-body nonembedded checks stay strict. Identity-fixture queries include
  only active child geometry. Original twelve cases stay unchanged. General
  entity/embedded/map wiring, nested transforms and geometry remain open.
  A matched actual BIH_TRIANGLE/removed-triangle pair now ACTS a kind-2 world
  winner, native hit/miss/same-pose removal queries and different removed movement.
  Origin/model/leaf/hull/identity instance bind with an empty brush payload;
  authored vertices/indices are wiring, not copied accepted geometry. Triangle
  support remains ABSTAIN; original fourteen full case/winner arrays stay exact.
  `tools/offramp_triangle.py` separately checks the retained standing-AABB native
  queries against an independent finite triangle/four-unit-slab SAT interval,
  including hit/miss/removal and native collision bias. This oracle uses authored
  wiring and does not promote support. A separate `offramp_tricopy` layer now
  copies actual winning triangle indexes/vertices at the native win, proves
  return-bound ownership against later probes/competition, and independently
  checks the fourteen bounded standing-world accepted sweeps. Original capture
  categories stay unresolved and general native/support semantics ABSTAIN;
  copying a winning triangle is not general support/physical-exit proof.
  `tools/offramp_trislab.py` separately ACTS setup-only full native back-slab
  queries: shaped native axial clipping enters four units later than ideal prism
  SAT, with native short-back/stationary misses despite ideal overlap. Explicit
  front/solid/removal controls and exact original motion/copy parity bind this
  NON-equivalence, not a marker/collision fix or unconditional support oracle.
  A separate `tools/offramp_tribev.py` setup-only full BIH fixture now ACTS a
  copied-winning front-edge bevel tag5 with independent SAT entry/bias, while
  bevel-OFF produces earlier tag2 contact and stationary false solid. Removal,
  face/occupied/outside/repeat controls and old twenty-case/copy/slab parity pass.
  This is NOT a new bevel-winning PM actor or support/physical-exit/marker fix;
  general native corner/bias/tie behavior, transforms and real-map triangle/
  displacement/prop geometry and identity remain open. An open-air
  crouch/release and matched no-duck falling pair now ACT native instant hull/origin/timer transitions,
  +8.5-unit shift/reversal and matching landing. Current-hull native/joint AABB
  queries and completed tick/hull binding pass; original sixteen full case/winner
  objects stay exact. These zero-ramp-contact actors do not cover airborne winning
  collisions, blocked-unduck/sliding or general posture. A grounded ascending-ramp
  approach and matched removed-ramp walker now ACT native cached-firsttrace reuse,
  winning whole brush/plane/actual hull and prior-grounded-body/requested-sweep
  binding. Actual/local/removed joint AABB queries ACT; original eighteen full
  case/winner objects stay exact. General cached variants/recovery/portal actors
  remain open. This is bounded fixture coverage, not a physical-exit or classifier fix.
  General geometry, uninstrumented cadence, LODs, unsupported mover paths and
  the recorded/live/render chain remain open.
  Falsifier: a known brush edge, raw contact-loss tick/hull/plane,
  held-kind transition and rendered event position logged together, at several
  tick/frame rates and LODs. Include ramp-to-ground, curved/prop/displacement
  ramps and teleport controls. Place labels at measured contact events rather
  than guessing from centre-to-surface distance. Plan 12.4.
- **Peak/trough speed and energy labels are not reliably visible.** Existing
  `cl_lines.qc:Line_Point` reversals are gated by `LN_EVZMIN` and `SEG_AIR`;
  contact changes take a separate branch. `Line_Marks`/`hud_lines_nums 1`
  defaults to contacts; 2 adds peaks. Audit missing display/defaults separately
  from classifier coverage. Falsifier: an airborne ascending->descending apex,
  descending->ascending ramp bottom, reversal at contact transition and a slow
  genuine reversal show the time/speed/energy AT the reversal, while zero-noise
  and teleport/stitch controls do not invent events. Repeat for a native run
  and a Momentum demo with honest missing/inferred-contact provenance. Plan 12.5–12.6.

## Modern UI theme and board layout (`ui_style 1`, Patch 606)

Published and on both Windows installs. In this patch `ui_style` still defaults
to 0 and the classic look is gated pixel-identical (`tools/test_ui_theme.py`).
What a human has to judge is in lextest.md. Left open, none of it a wrong action:

- **The old look is retired** (owner, 10 Oct: "we have it in the git"). Patch
  607 removes `ui_style`, every classic drawing branch and the classic board
  layout, gated the other way round: the modern pixels of this patch must not
  move. Until it lands the two looks coexist and the default is still classic.
- **The native table is themed but still looks foreign.** `ScoresTheme`
  (`plugins/ui_imgui/scores.inc`) changes colours only, because the p603 gates
  click at fixed pixel offsets inside the table; it still draws ProggyClean and
  its own column order (time before player), and it scrolls sideways inside the
  modern board, whose table area is narrower than the classic one's. The game's
  Roboto should be embedded in the plugin the way ProggyClean is, not read at run
  time: `plugfsfuncs_t`'s `LoadFile` cannot ask for a trusted-only lookup, and
  ImGui's stb_truetype is not written for untrusted fonts. Falsifier for the
  swap: `p603scores.py --font` (its glyph-height bounds are ProggyClean's) and
  the dense gate's rank-ink pair. The table wears the theme in EITHER style:
  the provider cannot see `ui_style`, and the classic board it would matter in
  is going.
- **Not restyled:** the terms and name screens (their `^1 ^2 ^3` escapes are
  still Quake's saturated colours on the pastel panel), the in-world main menu,
  the results card, replay chrome, vote box, chat, entity inspector and the
  avatar panel. `cl_linegraph.qc` follows the board's palette macros and so
  changed colour without being looked at.
- **The modern board on a small window.** It never draws under the room list.
  When its smallest form does not fit (under about 790 px wide at hud_scale 2,
  wider with the Imported tab or a larger hud_scale) the classic layout draws
  instead, in the new colours, with the room list docked over its edge as
  before; the fit depends on the tab count, so the Imported tab appearing can
  flip it. Patch 607 replaces that fallback with smaller type. `scores
  status`'s `cols` word still uses the classic budget's three names and cannot
  say that the run-class column was the one dropped.
- **Menu tooltips are witnessed by a synthetic hover only.** `ui_hover <x> <y>`
  (menu VM, harness) parks a mouse-mode cursor and `ui_hover` reports the tip;
  `test_ui_theme.py` P4 grades one chip in each style. No arm covers the other
  tips, the delay, or a real mouse.
- **`tools/compare_chip_smoke.py` was not rerun.** It patches `cl_scores.qc` at
  four text seams; all four still match exactly once (`Scores_Seg` takes `tab`,
  not `id`, for that reason), but the tool itself needs `surf_dune` and a full
  product build and was not run against this patch.
- **`p603scores.py`'s basic suite fails one native check in BOTH styles:**
  "actual native page controls did not act". It expects a 6-row page from 8 rows;
  the dense provider's page is 24. The dense suite is the one that grades native
  paging. Either seed 32 rows in the basic suite or retire its native arms.
- **The modern board's cost is reported, not budgeted** (tools/p603scores.md,
  Patch 606). It draws more than the classic board and builds two or three more
  temp strings a row (`Scores_Delta`), which feeds the collector section below.
- **Small:** the room list keeps its fixed 12 px type beside 16 px rows; the
  mono and UI faces snap to different size ladders, so at some window heights
  the names sit one rung under the times (12 against 14 at 720p); a podium
  plate follows the local list's position number, so with a cheated run sorted
  first the best clean run wears a silver 2; `test_ui_theme.py`'s regions are
  1920x1080 at hud_scale 2 only; `test_ui_modern.py` reads 21 changed pixels
  inside the speedometer between styles (bound 30), from another element's
  outline crossing it.

## Native scoreboard (opt-in, Patch 605)

Published and deployed as `ui_native_scores 1`; legacy stays the default. Evidence,
commands and limits: `tools/p603scores.md` (the p603 file names are a historical
harness number, not Patch 603). Human-only acceptance is in lextest.md. Everything
below came from the two review rounds or the gates of 2026-10-09/10 and fails safe:
a click is lost or the table falls back to legacy, never a wrong row.

- **The default switch is still held.** Needs the lextest.md items (font face and
  size, mouse feel, DPI, a second machine), a font with more than Latin glyphs
  (ProggyClean draws CJK names as `?`; legacy draws boxes), and an agreed CPU
  budget: open cost measured 0.78-0.79x legacy on one laptop, GL only, in a
  number the temp-string collector moves by a third (section below).
- **A held click is dropped when any cell changes.** `Scores_NativePublish`
  republishes on any label change and every `SetModel2` resets plugin input, so a
  press on row 2 while row 1 goes "queued" -> "on" does nothing on release. Same
  for an age label ticking over. Check: hold a line box down across another row's
  transition. Wants per-cell revision or a press that survives an unrelated change.
- **Parity gaps against legacy.** Line box is inert (`--`) on a filtered Local row
  where legacy still registers `Scores_LineCell`; only the first row with matching
  ticks is highlighted where legacy marks every one; only the player cell is a
  click target where legacy takes the whole row; Next fetches the following online
  page only when clicked where legacy fetches near the end of the scroll.
- **Labels can trail the data by a tenth of a second.** The page is rebuilt on a
  signature (page, count, highlight, pin, font, reply epoch or local rescan,
  layout), after any action, and otherwise at 10 Hz. `Online_MomBindRow`
  (cl_online.qc) rewrites `ob_rep` in place with no epoch bump, so a row can read
  "queued" for up to 0.1 s while a click on it already takes the replay branch:
  same row, same intent. Anything that must show on the next frame belongs in
  `scn_sig1`/`scn_sig2`.
- **A click after typing in chat lands on the pre-chat row.** `Chat_InputEvent`
  (cl_chat.qc) swallows mouse motion while a draft is open, so `_cursor_position`
  is stale when the pinned table gets the next press. Legacy's hover is equally
  stale. `tools/p603dense.py`'s `dense_cursor` step covers only the
  `ui_native_scores 0` window. Fix shape: `ev_mouse_seen` in cl_entview.qc.
- **A second `ui_native_draw` in one host frame costs the table for that gesture.**
  `cl_plugin_ui.inc` returns 0 for it and `Scores_NativeDraw` latches `scn_failed`.
  Not traced: whether loading-plaque or stereo redraws reach it.
- **Replay ids of 1,000,000 or more collide.** `Scores_LineKey` and the fetch URL
  in cl_online.qc both print `%g` (six significant digits). The native click is
  resolved by slot and then checked against this key, so a collision cannot pick
  another row, but line state is shared between the colliding rows. Not
  determined: whether surfd's autoincrement ids reach that size.
- **Vendor ImGui asserts are live.** `plugins/Makefile` builds the vendor objects
  without `NDEBUG` and `IM_ASSERT` is libc `assert`, so one would abort the client
  instead of falling back. No reachable assert was found by reading.
- **`ScoresGallery` bounds the clip's extent but not its origin.** A finite origin
  of 2^31 or more with a legal extent reaches ImGui's float-to-int truncation
  (undefined). Only a CSQC passing an absurd `drawsetcliparea` gets there.
- **Vulkan deferred destroys only drain on a presented frame.** While minimized
  (`cl_main.c` skips `SCR_UpdateScreen`) map-change purges accumulate until
  restore; on device loss `VK_FencedCheck` drops jobs attached to an in-flight
  frame (a leak, not a double free). Same shape as the existing
  `VKBE_SafeClearVBO` deferral.
- **`tools/p603names.py` grades the table staying up, not the label bytes.** A
  sanitizer that returned `?` for every name would pass; the text was read by eye
  in the screenshots. Wants a probe that prints the sanitized bytes.
- **Legacy does not clip a long owner name.** A 200-byte name overruns the date,
  run and line columns (seen in the names control screenshot). Pre-existing.
- **The soak's leak-control arm was not rerun on the shipped QC.** The third run
  (`runtime/soak3`) had its native and legacy arms complete (floor rise 21.0
  against 1.9 MiB over 800 open/close cycles) when the host's memory reaper
  killed the leak arm, so that rig fails `planned/acting arm set differs` and
  `tools/test_p603soak_unit.py` has no complete passing rig to run on. On the
  complete second rig 17 of its 18 controls act; the 18th, `test_acting`,
  reports that rig's real 59.3 MiB miss. The leak arm separated there (294
  against 54 MiB). Rerun all three arms when the laptop has memory to spare.
- **Page floor still creeps with churn.** 21 MiB over 800 opens at 32 rows, flat
  at 6 rows (`runtime/soak-rows6`): it follows per-row QC string work, not the
  open itself. See the temp-string section.

## QC temp-string garbage balloons the client while a board is open

Found by Patch 605's soak (2026-10-10), which failed its memory bounds in every
arm, legacy included. The legacy scoreboard makes about 1 MiB/s of temp strings
held open (every `bufstr_get`, `sprintf` and `strcat` allocates one) and the
engine reclaims them with a threshold collector: `PR_RunGC` (qclib/initlib.c)
runs once half the table is live, and `PR_AllocTempStringLen` doubles the table
whenever it fills while a threaded collection is in flight. The threshold only
grows, so the saw-tooth gets taller over a session: legacy peaked 126 MiB over
its floor in a 3-minute hold; the native table, before it stopped rebuilding
every label each frame, 650 MiB. Private bytes come back at each collection,
so it is not a leak. With `pr_gc_threaded 0` (not the default) that pre-fix
native table grew 6 MiB/s for two minutes and never came back
(`runtime/soak-gc0`); not investigated. Check: `tools/p603soak.py --arms
legacy native`, per-sample private bytes in report.json. Wants either less
garbage in the per-frame board code or a collector whose threshold can come
back down.

It costs CPU as well, and it moves cost measurements. The same held-open native
table, same pixels and same plugin counters, read 822 us of QC UpdateView with
the collector disabled (`pr_gc_threaded 2`) and 1159 us with it on
(`runtime/regime-gc2`, `regime-gc1`): about a third of a millisecond a frame
while it cycles. Fresh sessions that make little garbage read the low figure
(828-852 us in the cost runs), long-churned ones the high (1174 us in two soak
holds), and the legacy board, which always makes enough garbage, reads
1050-1110 us. A cost comparison that does not say which regime each arm was in
is comparing collectors. One earlier cost run stepped 80-100 us mid-arm
(`runtime/perf20/p603-perf-u69mhxdt`) and one no-plugin arm read 85 us high for
a whole process with identical pixels (`runtime/lean/perf32`); neither was tied
to the collector.

## Screenshots on D3D9/D3D8 are probably upside down

`D3D9_VID_GetRGBInfo` and `D3D8_VID_GetRGBInfo` (engine/d3d/vid_d3d.c, vid_d3d8.c)
have the bottom-up copy loop Patch 604 fixed in `D3D11_VID_GetRGBInfo`, with the
same positive stride. Neither renderer starts on the test laptop, so this is read,
not measured. Check: `screenshot` under `vid_renderer d3d9`; the HUD should be the
right way up.

## Imported runs (Momentum, KSF)

- **An immediate stage restart can reuse/trim the live trail** (run-line review,
  2026-10-07): `Trail_Frame` keys a new run primarily on TS_RUNNING's rising edge.
  A stage reset which re-arms and launches inside one transmitted snapshot keeps
  TS_RUNNING and a backwards clock reaches `Trail_Trim`, discarding the failed
  attempt rather than retaining/fading it. Control: surf_dune stage-2 zone_goto
  in a private dedicated overlay can land outside its boundary and launch at
  once. Falsifier: distinguish an authoritative new attempt from a save/rewind
  clock-back, preserve failed attempt/head, then start/fade only after departure;
  P502 same-frame go/save, warm-history and cold-load arms must still pass.
- **Re-imported Momentum runs read every ramp as free air** (2026-10-04, the
  re-import's review; true of the .wrpath imports too). A .mtv records no ramp
  contact, so fl bit 16 is never set and the plane is 0 0 0 -- and readers take
  a clear bit 16 in a 17-column file as "measured, not riding": the strafe bar
  grades ramp ticks against the flat-air target, the segment column has no ramp
  rows, and line marks/colour treat rides as air (cl_watch.qc:1261, 2549;
  cl_lines.qc:573; cl_hud.qc:3725). Real ground/jump bits now make it look
  measured: 24-43% of airborne ticks in four surf files are not free fall. FIX
  BY INFERENCE, validated first: the per-tick wishVel and post-move velocity
  give the expected air step (half gravity, AirAccelerate at aircap 30), and
  the residual of a clipped tick is along the plane normal. Score it against
  FTESurf's own recordings, which carry the engine's true bit 16 and plane, and
  declare it in the header. Until then the alternative is a reader guard.
- **The web run page reads 8 MiB of a recording** (recplot.py MAX_BYTES), and
  three re-imported surf_666 main runs are 17-24 MB: their page plots and
  times the first third. The cap keeps one request from holding the Pi's single
  worker; the fix is a summary computed at index time, not a bigger cap.
- **Two Momentum-demo quirks the re-import keeps** (pre-existing): 26 main
  files claim a tick the body never reaches (the demo's time is X.5 ticks and
  was rounded up), so the replay clamps short of the finish; and 797 of 2486
  main files have stage splits in the demo but no `stage` records, so the
  replay's timer panel shows the starting stage throughout. The split events
  (type 2, major/minor) could be written as `stage` records.
- **Two cases the re-import's keys still get wrong** (2026-10-04, its review
  round 4). (1) A zero wish frozen on a ladder: Momentum stops updating wishVel
  off the air/walk mover. A frozen non-zero wish is caught by its yaw; a zero one
  cannot be, so 210 in-run ticks in 2 files (surf_leidenfrost main 0005452,
  surf_simpsons_source stage_8 0000455) read "no key" while W or W+A climbs.
  Only the velocity tells (airborne, no gravity), and a rule on it must not
  sweep in (2): A+D overlaps record a zero wish, but on surf_fiellu bonus_4
  0001753 (run ticks 59-60) the velocity turns along the later key, while on
  others it is plain gravity. 531 zero-wish keyed airborne ticks are neither
  gravity nor a ramp clip: 210 are the two ladders, and every stretch looked at
  among the other 321 (3 files) was an overlap. Find out which overlaps move
  before choosing a rule.
- **The Momentum demo scan's first pass found nothing; its next signal is not
  built** (4 Oct). `momscan.py` and its report live in the private repo (ROADMAP
  11: the method stays private). The plan's "Momentum demo scan" section names
  the next signal, and why it needs a recorded sample before it can be trusted.
- **A rejected Momentum recording stays linked, and the link pass would link it
  again** (2026-10-04, the link pass's final review). `restand` (surfd.py:2278)
  re-derives a row only for kind 'run', so a reject on an imported replay
  leaves its row's `replay_id` on it and `/api/replay` still serves it; and
  `link_demos` reads no reviews. Fix: skip `_REJECTED_SQL` replays when linking,
  and clear a momentum row's link when its replay is rejected.
- **A header key `recplot.parse` does not list is DROPPED SILENTLY** (found 5 Oct
  while closing the run page's "derived" wording). `recplot.HEAD_KEYS` filters the
  header before `surfd.py`'s `WEB_HEAD_KEYS` ever sees it, and an unlisted key
  produces no note and no counter -- the `unknown records` note counts BODY records
  only. So adding a key to `WEB_HEAD_KEYS` alone publishes nothing, and the failure
  is a missing field, not an error: exactly the shape AGENTS.md warns about for the
  `.rec` grammar's `r.info` tuple. Both lists move together, and `test_web.py` 6b now
  pins each side (the demo hash reaches the browser; a ranked run grows no empty
  one).
- **momreplay.py has no memory or time bound per demo** (PC-only; every current
  demo decodes or refuses cleanly): zstd's max_output_size is ignored when the
  frame states a size, LZMA trusts the file's own 32-bit size, a zero-width prop
  index loops on a count up to 2^32, and momreimport's pool has no per-job
  timeout. Bound all four before decoding demos from strangers.
- **A client keeps a replay it fetched forever, so a rewritten import never
  reaches it** (2026-10-04). `Online_ReplayFind` (cl_online.qc) serves any
  `data/online/**/*_r<id>.rec` before asking, and that was safe while a row's
  file never changed; `tools/momreimport.py` rewrites them under the same ids.
  None of Lex's 20 cached replays was an import at the re-import. Fix before a
  second rewrite: put the file's size or a version in the board row and
  refetch on a mismatch.
- **THE COMBINED BOARD IS UNUSABLE ON A BUSY MAP.** It merges every tier by
  time and the client fetches one page of `OB_MAXROW` 64 with NO offset
  (`Online_Fetch` sends `limit` and never `skip`). On `surf_utopia` main, 221
  imported rows are faster than this server's best, so a local row lands at
  rank 222 and is simply not in the page. The merge is correct; the paging is
  the hole, and it will bite the ranked board too once any map has 65 rows.
  Found only by testing against the LIVE board -- the local fixture had 2
  ranked against 1 imported and interleaved perfectly. `lextest.md` 2h(f)
  puts the three fixes to the operator.

- **The import is being deployed now** (2026-09-28); until this entry says
  otherwise, check the host rather than this file. What ships: the `.rec`
  corpus under the game's `data/momentum`, the surfd code carrying the tier and
  the pseudo-tiers, the board cache and track table for `momwatch`, and the
  progs carrying the tab and the tint. `lextest.md` §2h holds the five
  judgement calls that are still the operator's.
- **877 imported runs are on a build that is NOWHERE ON THIS MACHINE, and are
  SKIPPED.** The demo's own map SHA1 says so (see AGENTS.md). Searched across
  all three map roots -- Momentum's 1,316, Counter-Strike: Source's 1,084 and
  ftesurf's own -- and **0 of the 877 match any build here**, so they are older
  Momentum cuts since replaced rather than a map we merely mounted from the
  wrong place. Nothing recovers them but the original BSPs.
  (The first search of this missed the CS:S install entirely and reported the
  same answer, which was luck rather than method: a root that is not searched
  cannot contribute a match. The figure above is from the complete sweep.)
  It also confirms from the other direction that no Momentum demo was recorded
  on a CS:S build -- not one hash matched one.
  Their times are real and their paths are not ours to draw. `momimport
  --other-build` imports them if anyone ever wants the times without the lines,
  which would want the line suppressed per run, and nothing does that yet.

- **SIX MAPS CONTRIBUTE NOTHING BECAUSE EVERY ONE OF THEIR RUNS WAS SKIPPED**:
  `surf_anubis` (9), `ts_rookie` (23), `surf_intbonus` (2), `surf_simple_v5`
  (2), `surf_corruption` (1), `surf_shade` (1) -- 38 runs. We hold a build of
  each that nobody in this demo library ever played. They are not errors and
  nothing is lost that could be recovered here, but a map that appears in the
  corpus and yields no rows looks identical to a map that was never imported,
  and the importer does not say which it is.
- **A CORPUS-WIDE BUILD COUNT IS A FLOOR, NOT A TOTAL.** 103 of 478 corpus maps
  have runs on more than one build, and `surf_4am` has **three** attested here
  (62 runs kept, 20 dropped) against the two a 40-map demo sample found. So a
  roster column saying `builds=2` means "two seen", and a second corpus can
  raise it. Anything that resolves a contested map by picking the most-played
  build should say how many it saw as well as which it chose.
- **80 demos failed extraction outright** (of 735 in the last batch): mostly
  `gave up after 30 s in the chain search`. `wrpath_extract --timeout 0` or a
  larger value would take another pass at them; the extractor records failures
  so a re-run skips them by default.
- **The corpus was extracted on CPython 3.10, not the 3.13.9 the extractor is
  bit-pinned to.** Its own oracle still gates every chain, so the output is
  valid, but a chain here may differ from the one the wrlines DLL would pick on
  the same demo. Nothing measured says it does; nothing says it does not. If
  parity with the DLL ever matters, re-extract on 3.13.9 and compare.
- **`surf_antichamber` has 5 demos and no zone file** -- the only one of 500
  demo maps without one. Its runs import and draw, but nothing times that map.
- **An imported run's air-control and energy colouring is graded against THIS
  server's movement settings**, like every other foreign recording -- see the
  `Line_Movevars` entry under Cosmetic. The import makes it concrete: the engine
  prints Momentum's own constants (`accel 5, airaccel 150, aircap 30, gravity
  800`) on every one of those maps, so the file's numbers are KNOWN and still
  not read. `momimport` writes no `pmpin`, deliberately -- it did not run that
  physics either -- so the "no answer" branch is the PERMANENT state for a whole
  tier rather than a legacy case that shrinks.
- **A KSF row's `ticks` is derived, not counted.** KSF reports seconds; the
  schema wants a tick count, so `ksfimport` divides by the CS:S 0.015 and says
  so. Anything reading `ticks` off a ksf row is reading a number nobody
  measured. `millis` is the fact.
- **`momquality` is surfaced at the replay, not on the board.** Opening an
  import whose velocity exceeds the demo's own ceiling prints a `^3` line
  naming the factor, and `replay status` carries it either way (momline A6
  grades both halves on one map). What is still missing is the BOARD side: a
  row that will draw a bad-speed line looks identical to one that will not
  until you open it. 354 of 5,281 rows were affected; since the re-import
  (4 Oct) none is -- every rewritten file reads 1.0000, and the 21 left as they
  were are under 1.01.
- **The two imported tiers make different claims and the board shows one word
  each.** A `momentum` row is build-verified exactly; a `ksf` row cannot be,
  because nothing on the CS:S side publishes a per-map digest and the 322
  divergent map names are all plain-named. `why` says `momentum` or `ksf`, so
  the information is there for anyone who knows -- but nothing says that one of
  those words carries a check and the other cannot.
- **The blue tint is a hue blend, not a glow**, and against a warm map it reads
  as lavender. `hud_watch_path_foreign` tunes it, but the real answer for
  "someone else's line" is probably a wider or additive draw pass, which is a
  rendering change wanting its own patch and a `replay bench` measurement.
  `lextest.md` §2h(a) asks the operator whether it is enough as it stands.

  **AND A MATCHING NAME IS NOT A MATCHING BUILD, FOR 30% OF THE SHARED LIBRARY --
  which makes the `_ksf` counts above a floor, not a bound.** The import session
  fetched a real `ksf.surf` bestrecords response and found KSF returns records
  under PLAIN map names (`{"map_id":580,"mapName":"surf_whiteout"}`), with
  suffixed and unsuffixed names in the SAME response -- so a KSF record on a plain
  name was still set on KSF's build under KSF's zones, and counting `_ksf`-named
  files understates the exposure. Their API reading is theirs and is not verified
  here (no request was made to ksf.surf from this session). The LOCAL half is, and
  it generalises the point past KSF: of the **1062 map names present in both the
  Momentum and CS:S installs, 322 (30.3%) differ in size, i.e. are a different
  build under the same name** -- and **all 322 are plain-named, zero are
  `_ksf`**. The suffix convention is exactly where the collision does NOT happen.
  Divergence is not marginal: `surf_fantasy` is 155 MB against 351 MB,
  `surf_dune` 21 MB against 156 MB. Method check: `surf_kitsune` reads
  3,952,402 / 4,418,529, the same pair `mapsync.py:47-63` recorded independently
  when it found 323 of 1312 Pi BSPs were the wrong build.

  **CONSEQUENCE FOR THE DOWNLOAD BUTTON, and it is a design constraint rather than
  a caveat: the transfer must be content-addressed, not name-addressed.** "Send me
  `surf_kitsune`" is ambiguous across a third of the library, and getting it wrong
  is SILENT -- the client loads, plays, and `TF_NOMAP` demotes the run because
  mapcrc disagrees. So the button must ask for the build the SERVER holds (its
  mapcrc or a hash), the Pi must answer with that exact file, and the client must
  verify what arrived before the run counts. This is also the strongest argument
  for the Pi-sourced design over Momentum's CDN: the CDN can only ever answer by
  name, and the name is the thing that is not unique.

  **THE KSF DRIVE, SURVEYED 2026-09-28 -- AND IT IS ALL PUBLIC, SO NO OAUTH AND NO
  CREDENTIAL IS NEEDED.** Three links from the operator: maps A-K
  (`17QJ-Wzk9eMHKZqX227HkPCg9_Vmrf9h-`), maps L-Z
  (`1f3Oe65BngrSxTPKHAt6MEwK0FTsDbUsO`), and a roster spreadsheet
  (`1oXU6UXGPdgdqRiAjjD_5c1WfI6PY6ML4`). All three answer an anonymous GET.

  **ENUMERATION: use `embeddedfolderview`, NOT the folder page.**
  `https://drive.google.com/drive/folders/<id>` returns 798 KB of HTML whose
  `window['_DRIVE_ivd']` blob holds **only the first 50 entries** -- the rest
  paginate by XHR, so a scraper built on it silently sees 50 of 466 and looks like
  it worked. `https://drive.google.com/embeddedfolderview?id=<id>#list` returns the
  COMPLETE listing in one unauthenticated request: 466 + 468 titles, **934
  distinct names, 927 of them `.rar`**. The roster exports as CSV with
  `https://docs.google.com/spreadsheets/d/<id>/export?format=csv&gid=1729788986`
  (23 KB, `Map name,Tier,Type`, workbook tabs `Surf Maps - KSF CSS` / `Sorted by
  map type` / `Feuille 3`).

  **THE MEASUREMENT: 929 maps on the roster, 929 archives in the Drive, and we
  already hold 894 of them (96.2%).** Genuinely absent after name reconciliation:
  **31**, and every one of the 31 is present in the Drive, so the mirror is a
  bounded one-off rather than an open-ended sync. Roster tiers run 1-8
  (76/170/262/217/108/56/31/9); types are Staged 496, Linear 404, Staged-Linear
  28, plus one row whose Type is the literal `c`.

  **THE REAL KSF GAP IS ZONES, AT EVERY SCALE THAT WAS MEASURED.** Of the 929
  roster maps, **390 have a zone file (42.0%)** and 389 are both playable and
  timeable; 539 are not. That is the same finding the `_ksf`-suffix census gave
  and the same one the whole-library census gave -- maps are nearly solved, zones
  are not, and no KSF endpoint or Drive artifact supplies zone data.

  **A SCANNER NEEDS A THIRD VERDICT FOR NAMES, because the spreadsheet and the
  Drive disagree on five of them.** `surf_disappointed_fix`/`surf_disappointed`,
  `surf_junglepics_ksf`/`surf_junglespic_ksf` (a transposition), `surf_not_so_zen`/
  `surf_nsz_fix` (an abbreviation), `surf_race_final`/`surf_race`,
  `surf_vestige_fix`/`surf_vestige`. **Four of those five are already on disk under
  the DRIVE's spelling** -- so a scanner that trusts the roster reports 4 maps
  missing that are sitting in the library, and one that trusts the Drive reports 5
  roster entries absent. Neither is a fault; the honest answer is `unreconciled`,
  counted separately and never folded into `missing`. This is the Patch 421/422
  third-verdict shape arriving in a new place.

  **PRACTICAL TRAPS FOR THE FETCHER.** Maps are `.rar`, not `.zip` or loose BSP, so
  an extractor is on the path and a CS:S map archive carries materials and models
  beside the BSP. The Drive's mime types are INCONSISTENT for identical content --
  `application/rar`, `application/x-rar` and `application/x-compressed` all appear
  -- so filter on the name, never the mime. And the spreadsheet is the cheap change
  signal the 6-hourly scan should actually use: one 23 KB unauthenticated GET,
  hashed and diffed against the last copy, gives new-map detection without
  enumerating either folder and without touching anyone's API.

  **PART OF THIS IS NOW BUILT: `tools/maproster.py` (2026-09-28), the official
  surf/bhop list pinned by content hash.** Scope narrowed by the operator to surf
  and bhop, with zones explicitly off this thread (an in-game zone maker is being
  built instead). It writes `data/maproster.txt` -- **1748 maps, 1174 surf and 574
  bhop** -- unioning KSF's roster, Momentum's catalogue and what is on disk;
  1249 installed and hashed, 499 absent, **31 of them fetchable from the KSF
  Drive**. `pin` came out **ok 37, other 2, unknown 1709**.

  It hashes only the build the ENGINE WOULD LOAD, resolved through
  `fs_addons.txt`'s mount order rather than assumed -- 1249 files and 43.7 GB
  instead of the 90 GB both installs hold, and it is also the only build that can
  ever matter. Regeneration is byte-identical on a re-run (checked), which is the
  defect the `mapmeta.py` entry above records, avoided by deriving everything from
  sources and carrying no state forward but the hash cache -- and that cache is
  keyed on size AND mtime, because a stale one is silent.

  **Momentum's published SHA1 is real and was verified independently: a `.mtv`
  carries it as 40 UPPERCASE hex at FIXED byte offset 80**, and across the 2888
  demos in `wrlines_data/demos` 39 of the 40 maps carrying one hash to exactly a
  local build. 5 of those 40 have demos that DISAGREE with each other
  (`surf_4am`, `surf_antichamber`, `surf_blackheart`, `surf_pinkcubes`,
  `surf_tropic`) because Momentum re-released the map and both builds hold times --
  so "the latest version" is not a thing a hash can answer, and the tool reports
  the split rather than resolving it silently.

  **AND IT FOUND A LIVE ONE ON ITS FIRST RUN, which hand-checking the two Steam
  installs had missed: `ftesurf/maps/` WINS THE MOUNT, and two of the four loose
  BSPs in it shadow a different upstream build.** `surf_dune` (156,409,212 bytes)
  and `surf_fantasy` (351,547,373) in the gamedir are **byte-identical to the CS:S
  builds** and override Momentum's 21 MB and 155 MB cuts for everybody on this
  install. So any run on either map is recorded against geometry Momentum's
  leaderboards do not know, and `surf_dune` is exactly the `other` verdict the pin
  is for. Whether those two are deliberate fixtures or leftovers is not recorded
  anywhere and wants deciding; `poop` and `surf_raqbonus3ramp` are gamedir-only
  with no upstream build and are not affected.

  **THE KSF MIRROR RAN: 28 of the 31 are in, 3 are not.** `tools/ksffetch.py`
  fetches the archives the roster names and extracts the BSP into the Momentum
  install's `maps/` -- that dir and not another, because `mapsync.py` mirrors FROM
  there to the Pi and `fs_addons.txt` mounts it first, so anywhere else is a map
  you can play and cannot host. `surf_tycho2`, `surf_weirdcore` and `surf_yolo`
  are still absent: the run was stopped by the harness for host memory pressure
  partway through the 29th, not by any failure of its own. Re-running fetches only
  those three, because the roster recomputes `avail` from what is on disk.
  They are large -- surf_expel 335 MB, surf_crank 216 MB, surf_starvald 195 MB --
  and the first cut of the fetcher read each whole file into memory before writing
  it; it streams to disk now, which it should have done from the start.

  **THE PIN GOT 12x WIDER AND IT CHANGED A VERDICT, which is the argument for the
  `ev` column rather than a footnote to it.** Every one of the 5281 imported
  `.rec` files carries a `mapbuild` line, so attested builds now cover 472 maps
  where the `.mtv` demos reached 40: `pin ok` went 37 -> 467. **`surf_slobs` was
  reported here as a build nobody plays and that was WRONG** -- it rested on a
  single demo, and against 19 attestations our build is the most-played one. The
  count of evidence has to travel with the verdict or a thin sample reads exactly
  like a strong one.

  **THE `.rec` HASH IS 39 CHARACTERS, NOT 40, AND THE TRUNCATION IS UPSTREAM.** A
  `.wrpath` stores the map hash in a 40-BYTE field including its terminator, so it
  keeps 39 of the 40 hex digits -- agtricks reads ...4C17940 where the `.mtv` says
  ...4C17940F -- and `momimport.py` copies that into `mapbuild`. So the wide
  source is a prefix and the exact one is whole. `maproster.py` matches by prefix
  and folds the 39 into the 40 where both exist; without that fold every map
  carrying both sources reads as contested when it is not.

  **AND THE TWO `other` ROWS ARE NOW EXACTLY THE GAMEDIR PAIR**, which is the
  cleanest statement of the shadowing problem above: `surf_dune` has **45**
  attestations for a build this install does not load and `surf_fantasy` 5,
  because `ftesurf/maps/` wins the mount and holds the CS:S cut of both. Nothing
  else in 1748 maps contradicts the evidence. Deleting those two files resolves
  both; whether they are deliberate fixtures is still unrecorded and still wants
  deciding.

## Harness coverage

- **Admin metrics board-invariance control includes wall-clock `t`.**
  `surfd/test_admin_metrics.py:32,57` compares complete public-board JSON across
  multiple authenticated API calls; `/api/board` includes its current timestamp.
  One unchanged frozen run failed this comparison and one recorded rerun passed;
  its failure log prints only the later response, not the earlier timestamp.
  Falsifier: drive the two board responses across a deterministic clock second
  while leaving rows/tiers unchanged. A content-invariance control should still
  pass, while a real board-content change must fail. Keep clock checks separate;
  do not weaken public exposure assertions or repair product code for this flake.
  **2026-10-08 P595-597 installed proof:**
  `surfd/test_verifier_counts.py:Counts.test_migration_no_backfill_and_authenticated_api`
  has the same complete-JSON comparison. It failed only on a one-second `t`
  difference. Restored predecessor deterministically fails with an advancing
  fixture clock and passes with a frozen one. That one private installed fixture
  now freezes its clock; legacy test/product source remains unchanged. Future
  fix must compare invariant content independently of `t` and still falsify a
  genuine board-content change. See `tools/p595observers.md`.

- **surf_aquaflow CRASHES THIS PC HEADLESS, on every engine and csprogs tried.**
  2026-10-03, `cfg/test/p474page.cfg` (minimized, listen server): the log ends at
  `Loaded Certificate DN` right after the map loads, and `crashaddr.txt` gets an
  access violation (0xc0000005) at an address far outside the exe. Same with the
  engine from 2026-09-28 (`ftesurf64.exe.prev`, 315a35f1) and today's (e847d3ae),
  and with the csprogs live on the lobbies -- so not 467/468 and not Patch 474.
  The map is the one in the session that needs `steam:Counter-Strike Global
  Offensive/csgo` mounted; surf_utopia and surf_colin_blaster_69000 load fine.
  Unmeasured: a windowed launch, and whether a player on this PC hits it.
  Falsifier: `map surf_aquaflow` headless, then read `crashaddr.txt`'s mtime.
- **A failed rewind on a LOBBY is untested, AND BUILD 66 AND PATCH 434 DISAGREE
  ABOUT IT.** Patch 434's void and Patch 441's latch re-scan are measured only on
  a listen server (`p434rew.cfg`, `p441void.cfg`), where the recording is
  buffered in QC strings. A lobby STREAMS, and there SV_RecRewind refuses at
  `if (e.rec_rec_stream) return FALSE` (sv_timer.qc:5967) whenever the save
  carried no snapshot -- whose own BUILD 66 comment says "the run carries on
  recording from where it is; it just does not rejoin the saved prefix". Patch
  434's branch then discards that recording (fclose + fremove of the part file)
  and Patch 441 voids the run with it. One of the two is wrong and the difference
  is a cancelled lobby run.
  HOW LIVE, NARROWED BY READING (2026-09-26, while closing Patch 443; the entry
  said "live since the 434-438 deploy" and that is wider than the code allows).
  The BUILD 66 refusal is reached only when the save carried NO stream snapshot --
  `sb = rs_bytes` is 0, i.e. no `recbytes` key -- because a save WITH one goes to
  SV_RecRewindStream instead. SV_RecSnapshot returns 0 in five cases, and four are
  not live: no file handle, nothing recorded yet, `!checkbuiltin(fcopyrange)` (this
  fork HAS it, engine pr_cmds.c:12471), a part file over FS_RECCOPY_MAX (256 MB,
  out of reach like the Multi-Session 512 MB trigger), and a failed buf_create. So
  on a healthy lobby a mid-run save always carries a snapshot. What IS reachable is
  a save written by a PRE-375 build, which has no `recbytes` key at all, and a
  snapshot skipped for one of those five reasons. ALSO CHECKED AND SOUND: the
  queued-copy race the Patch 441 comment implies ("a positive count for a copy it
  has only QUEUED") cannot reach a load -- SV_RecRewindStream calls SV_RecCopyFlush
  before it reads anything (sv_timer.qc:5706). The arm is still worth building, for
  the pre-375 save and to settle which of the two behaviours is right.
  MEASURABLE LOCALLY:
  `rec_stream 1` forces streaming off a lobby (sv_timer.qc SV_RecStreams), so an
  arm can drive it on a listen server -- which is also what makes this a to-do
  rather than a guess. Both reviewers of Patch 441 named it independently.
  sv_saveloc.qc SV_SaveApplyState (the `SV_RecRewind` else branch),
  sv_timer.qc:5546 SV_RecWritePrefix / SV_RecSnapshot. Patch 441.
- **A load the server REFUSED still tells the client to reload its sidecar.**
  SV_SaveLocLoad prints `save: the state file could not be read` and falls
  through: the body has already been placed, no rewind was attempted, and
  `SV_SaveLocEvent(e, SLOP_LOADED, id)` is still sent. The client then truncates
  its live `.view` to that slot's remembered mark, so the sidecar gets a hole
  with no `resume` record in the `.rec` to explain the jump. Reachable through
  the TOCTOU Patch 428 r1 documents (the identity check reads the file, the apply
  re-opens it). The fix wants the refusal BEFORE the placement, which is what r1
  set out to do, and an arm that produces the race. sv_saveloc.qc SV_SaveLocLoad,
  cl_replay.qc Rec_ViewLoaded. Patch 441 review.
- **The run line's near-plane guard cannot be falsified by the harness, and it
  is kept anyway.** Removing the dot-product test before `project()` in
  `Line_ProjPt` changes nothing measurable -- 158 glyphs either way, no NaN --
  because `q_z < -1` already rejects everything behind the camera, so the dot
  test's unique contribution is the `w == 0` knife edge exactly, which a sampled
  run does not land on. A cut that parks the camera ON a mark (p449win W3,
  t=41.1440) did not produce it either. The guard stays because
  cl_entview.qc:1288-1294 documents the same hazard from a case that DID reach
  QC; what is missing is a way to make the condition. cl_lines.qc `Line_ProjPt`.
  Patch 449.
- **The one-frame angle rule in `reccheck.py` convicts honest low-frame-rate players, and
  `tools/p456solo.py` is the arm for it.** ANG_SOLO faults a pair when too many ticks that
  held exactly ONE rendered frame disagree with the recording by over a flat 0.05 deg. That
  population is selected for having no minimum to take: a tick is scored as the MINIMUM over
  its frames, so a 4-frame tick picks its best of four and a solo tick cannot. Deny the
  ordinary ticks the same advantage and they come out WORSE than the ticks the rule convicts
  on -- 67.7% past cut against 45.8%. And coverage is `solo/comparable`, so a LOW frame rate
  RAISES it, and coverage is what promotes the verdict to `tight`: decimating an honest
  sidecar to one frame per tick (49 fps, nothing rewritten) makes the shipped rule answer
  `angle_rule tight` and "the sidecar is not this recording's" at 67.6%. The candidate fix is
  physics rather than a threshold -- a frame is drawn INSIDE the tick, so it cannot differ
  from that tick's angle by more than the tick's own sweep, and `dev > k*max(sweep, ANG_SOLO)`
  at k=1 clears honest 196 fps (0.6%) and honest 49 fps (0.1%) while still faulting a
  substituted sidecar (99.7%). With the floor at ANG_SOLO a still camera reduces to exactly
  the shipped rule, so the still-camera teeth the sweep rule is blind to are kept. NOT
  APPLIED: it is a verifier change and wants its own review round. The 2026-09-21 surf_4am
  FAULT was adjudicated a false positive on this basis and its `pubkeys.decision` is
  deliberately unset, so the fixed rule re-derives the verdict instead of inheriting a
  hand-cleared row.
  **PATCH 476 TRIED THE `max(sweep, ANG_SOLO)` CUT AND WAS REVERTED, 2026-10-03.** Two
  reviewers, independently, each with a measurement:
  - the turn is the wrong window: a one-frame tick's frame sits in the turn OUT of the
    move (row i to i+1), not into it -- all 155 surf_4am solo ticks do. Cut at
    max(backward, forward) turn: 0/155 honest; keep the first frame of each tick
    instead of the last and the shipped-backward cut faults honest at 1.05%. Move 0
    (`py` None) is judged at the floor whatever the camera does.
  - yaw and pitch must be cut separately: `max(dy,dp)` against `max(sy,sp)` lets a yaw
    deviation hide under a pitch turn (0.3-0.69 deg drew no fault from any rule).
  - `score()` in the lag search still uses the flat cut, so with any ping (>= 1 tick)
    the true offset fails ANG_LAG_FLOOR/EDGE and the join falls to 0 -- the honest
    pair shifted 2-3 ticks faults at 65-66% under the patch. A turn-aware score alone
    lets the neighbours pass too; the gates need rethinking with it.
  - THE TRADE IS A DECISION, NOT A DETAIL: a cut of the tick's own turn also clears
    deviations that sit inside turning ticks (measured: windows of 2-10% of a run at
    0.5-1 deg caught 11-15 of 20 vs the flat rule's 20/20). Since a FAULT is admin-only,
    the likely right shape is a THIRD VERDICT for "deviation inside its own turn" --
    reported, neither convicted nor cleared -- rather than a wider cut.
  - fixtures: `view_for` writes every frame exactly on its move's angle, so no test can
    reproduce the bug. A fixture with frames placed inside the tick's turn is the
    first thing a retry needs. `p456solo.py` grades against HOLD 5.0; the rule's
    ANG_SOLO_HOLD has been 1.0 since 70a40ae.
  Also corrected: the 0.0104 baseline is NOT only from still cameras -- honest p421
  pairs that swept 1258-5925 deg have one-frame worst 0.0099-0.0101 at or below the
  mover rate, where the one frame IS the usercmd's.

## Cosmetic / low
- **Source unbaked large-model lighting is still a two-slot, single-sample
  approximation** (`plugins/hl2/mod_vbsp.c:VBSP_LightPointValues`,
  `VBSP_AddWorldLightCube`; `plugins/hl2/glsl/vmt/vertexlit.glsl`). Patches
  508–509 fix the minimum's directional amplification and world-wall light
  leaks, not full Source parity. Source's shader retains six ambient faces and
  evaluates selected local lights at vertex world positions; ours usually
  scatters direct light at one point and folds the combined cube to two slots.
  On surf_tensor2 prop 46, two within-bounds probes differ 3.85x in +Y direct
  luminance. Source's material-selected half-Lambert also squares its ramp;
  the FTE split fold uses an unsquared ramp even without that material flag.
  No prop/mover shadow meshes or sky tracing are supplied by the world-only
  occlusion tree. See engine HL2_MODEL_LIGHTING.md for source citations and
  measured limits. Falsifier for a closer pipeline: rotated-model six-face
  colours, opposite/perpendicular local lights, attenuation across a large
  mesh, correct material cosine/half-Lambert and matched Source cameras. Keep
  visible-light, blocked-light and unchanged-world controls. Neither disabling
  all direct light nor enabling hl2_cubelight alone proves Source parity.

- **`Online_CacheName` still spells its filename with the pre-496 float32
  chain**, so a cache name and the time the board draws beside it can differ by
  1-3 ms on a run past an hour (`src/client/cl_online.qc:Online_CacheName`;
  `tools/onlinecache.py` is its model and returns both spellings beside each
  other, which is how this was seen rather than inferred).  DELIBERATE and
  load-bearing: the name is a cache key and every cached `.rec` on disk is named
  by it, so it must not change under existing installs -- and
  `tools/onlinecache.py`'s PINNED_NAMES would all have to be renamed with it.
  Cost, stated: `Online_CachePath` finds a cache entry by NAME and
  `Online_CacheScan` re-derives it from the file's own header, so both agree
  with each other and neither agrees with the displayed ms on such a run -- a
  row whose label reads `1:08:16.275` sits in a file called
  `68m16.276s_..._r7.rec`.  Nothing parses the ms back out of the name, which is
  what makes this cosmetic.  Fix if ever wanted: put a generation in the
  directory (`data/online2/`) and let `Online_MigrateBegin` move the entries,
  renaming on the way.  Falsifier for "it is only cosmetic": find a reader of the
  name's ms field -- today the only parses of that filename are
  `Online_RecName`'s writer and `onlinecache.py`'s model of it.

- **ENTER in a focused menu text field does not adopt what was typed**
  (pre-existing, found driving Patch 500's arm, traced and measured).  char 13
  reaches `sui_handle_text_input`'s "commit and deselect" branch, so ENTER is not
  swallowed as text -- but nothing wires that to the screen's own take, so the
  field's contents are dropped and the committed `name` keeps its default.
  Measured: type "watwasd" into the name field, press ENTER, and `ui_name` reads
  `name "Proto" -- chosen`, not `name "watwasd"`.  The screen has a button for it
  (`nm_go` -> `ui_name_take(ui_name_field)`), so this is a missing wiring and not
  a missing feature, but a player who types a name and presses ENTER gets nothing
  and no message.  Fix: call `ui_name_take(ui_name_field)` from the name screen's
  char-13 path (`screen_name`'s button action is the model), and the create
  screen's search field wants the same for its query.  Falsifier:
  `cfg/test/p498keys.cfg`'s B6 currently asserts the name is NOT the field's;
  after the fix it should assert that it IS.
- **ENTER is sui's confirm, and it clicks wherever the keyboard cursor landed.**
  The half of the old w/a/s/d item that Patch 500 did not touch: with a field
  focused the cursor no longer moves (the focus gate is in `sui_input_dir` AND in
  `sui_menu_nav` now), so ENTER cannot be *moved* into a lobby cell by typing --
  but it still activates whatever element the cursor was already on, and on the
  create screen that is a map row.  Untested and unmeasured: no arm sends ENTER on
  the create screen with the cursor on a row.  `sui_input_is_confirm` is reached
  only through `sui_block_menu_navigation`, which is the UNUSED sibling of
  `sui_block_input_fn` (`var` initialised to `sui_block_listened`, never
  reassigned, no caller in `src/`), so `Menu_InputEvent` returns 0 for ENTER and
  the click comes from the screen's own handler instead.  Fix if wanted: suppress
  the confirm-click while a field is focused, the same shape as the two gates
  Patch 500 added.
- **The create screen's search field is unreachable by ANY key, focused or not**
  (found driving Patch 500, measured).  Its scroll view calls `sui_reread_input`
  and DRAINS the input buffer every frame, so a keystroke is consumed before
  `sui_text_input` can read it: TAB claimed the focus (`ui_tab: focus cs_search`,
  the claim recorded) and the TAB itself was eaten by the frame that claimed it.
  That screen has 58 elements -- one per visible map row -- against the name
  screen's 3, and the arm therefore grades only "the claim was recorded" there.
  A player cannot type in the map-search box without a mouse.  Fix: have
  `sui_scroll_view_begin` re-read only the wheel keys it consumed
  (`sui_reread_input` exists for exactly that and is the wrong tool for a text
  field sharing the frame), or drain after `sui_text_input` has run.
  Falsifier: an arm that claims `cs_search`, types "surf", and reads the query
  back -- `ui_maplist` prints the row count, which a query changes.
- **A uri_get reply from before `menu_restart` reaches the new menu VM**
  (pre-existing; ROADMAP 9 review, read in the engine, not driven).
  `PR_uri_get_callback2` (pr_bgcmd.c) drops a reply only when the VM's
  `spawncount` moved, and client/pr_menu.c never sets `menu_world.spawncount`.
  The new VM's `Lob_NextReq` starts again at 1, so a late reply can take a
  fresh id -- the lobby poll's, a join's or the leaderboard's -- and be parsed
  as its answer. Fix: bump the spawncount in MP_Init, or seed `lb_nextid` from
  the clock.
- **The run line's air-control grade is measured against THIS server's movement
  settings, not the recording's -- ALL BUT THE TICK, which Patch 470 fixed.**
  `Line_Movevars` reads `sv_airaccelerate`, `sv_accelerate`, `sv_maxspeed`,
  `pm_maxairspeed`, `sv_gravity`, `sv_friction`, `sv_stopspeed` and
  `pm_duckspeed` from the server the client is on, and so does the strafe bar for
  a replay -- so the two agree, and on a foreign recording they are wrong
  together. The v9 header carries a `pmpin` block of 70 movevars and NOTHING in
  `src/` reads it; that is where the file's own settings would come from. Until
  then a recording made on a differently-configured server is graded against
  local numbers, silently. `tools/p453q.py` says the same in its header.
  cl_lines.qc `Line_Movevars`, `Line_Grade`.
  A Momentum import makes this concrete: the engine prints `Momentum movement:
  ... accel 5, airaccel 150, aircap 30, gravity 800` on every one of those maps,
  so the file's own numbers are known and still not read. tools/momimport.py
  writes no `pmpin`, for the honesty reason in its header.
  **MEASURED OVER THE WHOLE LIBRARY 2026-09-28:** of 3733 `.rec` files `tickrate`
  is on all 3733 and `pmpin` on 268 (7.2%: v9 243, v10 25; the rest v5 3107, v4
  344, v7 13, v6 1). So "read `pmpin`" repairs 7% of the library and the other
  93% needs a third verdict. What is left is SMALL on this fleet: with the tick
  right, surf (`airaccel 150`) and bhop (`1000`) both clear the 30 u/s cap in
  every combination (`k = aa*ws*tick*fric`, smallest 146 at fric 0.25), so the
  air grade cannot move between them; the ground grade reads `sv_accelerate`.
  AND THE NO-ANSWER BRANCH IS PERMANENT, NOT LEGACY. An imported run will never
  carry `pmpin`: momimport omits it deliberately (`:21` -- the machine that ran
  that physics was Source). So the third verdict is the standing state of a whole
  tier, and it wants to read "not measurable here" rather than "old file".
  AND THE MISSING-KEY CASE IS INDISTINGUISHABLE FROM AN ANSWER. `ln_mv_airaccel`
  (cl_lines.qc `Line_Movevars`) and `airaccel` (cl_hud.qc `HUD_DrawStrafe`) are
  the only two movevar reads in either file with no `<= 0` fallback --
  cl_board.qc `Board_AirCeiling` falls back to 150. Absent key gives airaccel 0,
  so `Strafe_CapBinds` returns false and both the bar and the line go to "the cap
  does not bind" -- also the legitimate answer for a server genuinely running a
  low rate. A fallback of 150 is the WRONG repair (it invents the number the
  CapBinds comment exists to respect); the refusal should name which of the two
  it is. The trigger is unreproduced: `SV_UpdateMovementServerInfo` publishes on
  the first frame whenever `sv_airaccelerate` is non-zero. Found by ftesurf-a1
  reading cl_hud.qc for Patch 462.
- **The live trail draws a teleport as one long segment, not a break.**
  `cl_trail.qc` feeds `Line_Point` with `brk 0` because it watches a body rather
  than reading a file, and the grammar block's rule is that a discontinuity found
  by watching is not a warp record. A map teleport mid-run therefore draws a
  straight stroke across the map. A break needs a teleport the client is TOLD
  about (a stat or event from the server's warp site), not one it infers.
  Falsifier: a run through any `trigger_teleport` with `hud_trail 1`.
- **A hop whose ground contact falls between two packets has no mark**, and
  cannot have one. Samples are one per packet (43-65/s measured against a 66.67
  Hz tick) and a bhop's ground contact is one tick, so the touch is simply
  absent from the file. The Segments column misses the same hops from the same
  samples, which is why the containment invariant still holds exactly -- but a
  reader counting chevrons on a bhop line is undercounting, and the number is
  not small: `bhop_monster_jam` main has 438 landings marked for 330 jumps.
  Interpolating them would be inventing contacts the file does not record, so
  this is a documented limit rather than a defect. cl_lines.qc header. Patch 449.

- The replay line's alpha ramps from 1 to the `ahead` alpha across the one sample
  segment after the playhead instead of stepping (cl_lines.qc Line_Feed).

- **Console notify on screen tints unrelated HUD text to the console's ^7 white
  when that text is drawn in extra passes.** engine/gl/gl_font.c's font batch
  colour meeting engine/client/console.c's Con_DrawNotify.  Found by Patch 440's
  arm (cfg/test/p440font.cfg, tools/p440font.py): with notify up (con_notifytime's
  default 3) and hud_font_outline 1 or 2, the speedometer's 48 px Bebas zero drew
  at (224,226,234) -- consolecolours[15], engine/client/console.c:181 -- with
  identical glyph coverage, 410 changed pixels, while every other Bebas and
  Roboto block in the frame stayed put; the same arm with `con_notifytime 0`
  grades 0.  Needs all three at once: notify on screen, this patch's extra
  drawstring passes, and a busy HUD -- a speed-only and a speed+mapinfo cfg never
  showed it, the full arm (debug + timer + energy + mapinfo) always did.  The
  mod's own harness therefore sets con_notifytime 0.  FALSIFIER: delete that line
  from p440font.cfg and grade the SPEED region -- 410 changed pixels in states
  1/2, 0 with it.  First read as glyph-atlas corruption from a second baked font
  slot; withdrawn in sh_font.qc's Patch 440 essay and in the arm's RESULT block.
  Patch 440.

- `Server permissions deny downloading file "package/maps/<map>.bsp"` on joins:
  the server advertises the map's BSP as a package and SV_AllowDownload refuses
  non-pk3 packages. The advertising side was not traced.
- A QW (engine) spectator receives the tracked player's cursor-save stats
  (STAT_FS_SLORG/SLANG, Patch 430) -- no more than the live position it watches.
- The release packet's ticks count as frozen (SV_TimerFreezeFrame); held runs are
  practice, so no board is affected.

## Map downloads shipped (Patch 465) — 2026-09-28

The survey recorded earlier in this file said the download button, the "New"
badge and the 6-hourly scan were surveyed and not built. They are built now.

**Engine (Patch 465, client-side, three changes.)** `downloadmap` as a menu
builtin, because `localcmd` runs at `RESTRICT_INSECURE` and the console
`download` command therefore treats a menu request as a server's, refusing a bare
map under `cl_download_redirection 2` and dropping `DLLF_ALLOWWEB`.
`CL_RequestNextDownload` now starts a `DLLF_TRYWEB` entry while disconnected --
the queue was drained only while connecting or connected, which is right for the
netchan and wrong for the menu, and http needs no server because `HTTP_CL_Think`
runs from the top of `Host_Frame`. And `CL_WebDownloadFinished` re-pumps when
disconnected, because `CL_DownloadFinished` does not chain and a second queued
map would otherwise wait forever behind the first.

**The progress bar and the KB/s needed no engine change at all** --
`serverkey("dlstate")` was already VM-agnostic. Neither did the rate cap:
`sv_maxdrate` already existed at `500000`, which is the answer to "do we get
uncapped speeds" -- no, and it was half the figure anyone would ask for, on the
fallback path only.

**Serving is nginx, not the game and not ftp**, on the vhost that already exists.
`limit_rate 1m` for the 1 MB/s, `limit_conn` because `limit_rate` caps ONE
CONNECTION -- the multiplier the `nettest-dl.conf` essay already records from the
6.20 GB incident.

**The scan** is `tools/mapscan.py` on a PT6H Windows scheduled task. It writes
`data/mapdl.txt` (the intersection of the catalogue and the Pi's inventory) and
`data/mapseen.txt` (first-seen, with a `bootstrap` origin so the first sweep
badges nothing).

### Still open

- **The nginx snippet is not installed.** Sudo on the Pi is scoped to the lobby
  units, correctly, so this needs the operator. Command is in lextest §2j. Until
  then `https://play.proto.bar/maps/*.bsp` is a 404 and every download silently
  takes the netchan path instead -- slower, and working.
- **Nothing has been downloaded end to end yet.** Every component is measured
  (builtin present in both binary and `menu.dat` against known-good controls,
  `sv_dlURL` and `sv_maxdrate` confirmed live by rcon, the sweep runs green) but
  the first actual transfer has not happened.
- **509 catalogued maps are not on the Pi** (1748 catalogued, 1315 bsp present,
  1239 of them on the roster). The button cannot offer those. `tools/mapsync.py`
  is the fix and it has not been run since the KSF fetch -- the Pi currently has
  FEWER roster maps than this workstation.
- **The 76-map gap** between what the Pi serves (1315) and what the roster
  recognises (1239) is unexplained. Other gamemodes and name mismatches are the
  likely answer; nobody has checked.
- `mapmeta.py` regeneration losing rows is still the reason nothing ELSE is on a
  timer. `mapscan.py` deliberately does not depend on it.

### Two process failures worth keeping

**A patch number was taken and the ledger did not know.** `lextest.md` §2g calls
its change Patch 464 and that number never reached `ENGINE_PATCHES.md`, so the
ledger's maximum was 463 while the maximum in USE was 464. Scanning the ledger
for "the next number" -- the obvious method -- returned a taken one, and this
work shipped as 464 before being renumbered to 465. `ENGINE_PATCHES.md` now has a
bookkeeping entry at 464 and the grep that would have caught it.

**A pre-existing nginx drift nearly became a whole-box outage.**
`setup_public.sh` rewrites the entire rate-limit zone file whenever any zone it
lists is missing, and the live Pi has a fourth zone, `surfdjoin`, added by hand
and never brought back to the repo -- used by `snippets/surfd.conf:206`. Adding a
fifth zone without noticing would have written a file without `surfdjoin`, and
nginx refuses to start when a vhost names an undeclared zone. That is exactly the
failure the essay in that file describes, reached by drift rather than by a
missing check. Fixed in both the list and the guard.

## Map downloads: measured end to end, and three defects found doing it — 2026-09-28

The previous entry said "nothing has been downloaded end to end yet". That is no
longer true. `tools/p465dl.py` drives `cfg/test/p465dl.cfg`, which calls
`ui_dlmap` — the headless twin of the Download button, the way `ui_join` is the
start button's, and for the identical reason: no cfg in this tree drives a
cursor.

**SUBJECT** (a throttled local mirror serving a real bsp):

    state sequence: idle -> active x8 -> ok x3 -> idle x4
    rate samples: 16, non-zero: 15, max 250000 B/s   (exactly the throttle)
    maps/p465test.bsp afterwards: 4774571 bytes, sha1 matches the source
    maps/p465test.tmp left behind: False
    http: 1 served, 0 refused

**CONTROL** (the same mirror, same port, same config, answering 404):

    state sequence: idle -> failed x2 -> idle x13
    rate samples: 16, non-zero: 0
    no bsp, no tmp, 0 served, 1 refused

They differ in every graded dimension, which is the only thing that makes the
subject's pass worth anything.

### Defect 1 — an interrupted http download left a TRUNCATED .bsp under the real name

`httpclient.c:639-642` opens its localname directly with `"w+b"` and never
renames. The netchan path has always downloaded to `<name>.tmp` and renamed in
`DL_Abort`'s `QDL_COMPLETED` arm, but that arm is gated on `DLLF_BEGUN`, which a
web download never sets. So a quit or a dropped link mid-transfer left a short
`.bsp` at the real path — and that is the worst possible shape for a map: it
reads as installed, the Download button stops offering it, and a short bsp is a
mapcrc mismatch, i.e. a silent `TF_NOMAP` on every run played on it.

Found by the test, not by reading: the first throttled run was cut off by the
arm's own wait budget and left 3,531,250 of 4,774,571 bytes sitting there as
`p465test.bsp`.

Fixed in Patch 465: the web branch of `CL_SendDownloadStartRequest` fetches to a
`.tmp`, `CL_WebDownloadFinished` renames on success and removes on failure. The
rename is done there rather than by handing `DL_Abort` a tempname, because that
arm also calls `FS_Remove(dl->dclname)` and `dclname`/`prefixbytes` are set only
on the netchan path — a web qdownload carries `""`.

### Defect 2 — `mapdl.txt` named six maps the Pi could never serve

Both catalogues lowercase their names; the Pi does not. Six maps differ by case
alone: `Bhop_Mukiology`, `bhop_HaddocK`, `bhop_HeLL`, `bhop_addict_V2`,
`surf_prottos_NightMare`, `surf_Rebel_Resistance_Revamp`. An exact-case
intersection dropped all six, but the sharper half is the other direction — the
Pi runs Linux and nginx's `alias` uses the captured name verbatim, so a row
reading `bhop_haddock` would have sent every client to a path that does not
exist and 404'd forever. `mapscan.py` now folds case to MATCH and emits the PI's
spelling, because the name in that file IS the download path.

### Defect 3 — the grader read a log that accumulated across runs

FTE appends to its log. The control's first pass showed 12 state samples for 6
calls, opening with the *subject's* `ok`. The driver now deletes the log before
each run, the way `p438view.py` always did.

### Also settled by measurement rather than assertion

**The engine takes the `sv_dlURL` layout, not `cl_download_mapsrc`.** Both were
set and the mirror served both shapes; every request arrived at
`/ftesurf/maps/p465test.bsp`. The reason is in `cl_parse.c:1005` — the
`cl_download_mapsrc` branch is an `else if` on `dlURL` being EMPTY, and
`default.cfg` sets `sv_dlURL`, which is the same cvar (`fs_dlURL`) on a client.
So `cl_download_mapsrc` is currently dead configuration. It is kept because it
costs nothing and is the documented fallback if `sv_dlURL` is ever cleared, but
`default.cfg`'s comment claiming the menu uses it was wrong and is corrected.

**`DL_HOLD` is 6 seconds and a probe every 8 stepped over it**, reporting
`active -> idle` with the map on disk — which reads exactly like a download that
never finished. It had finished. The arm now polls every 2 s. Worth remembering
whenever a state is shown for a fixed time: the sample interval has to be
shorter than the window, or the arm measures the gaps.

### Still open

- **The Pi's nginx snippet is still not installed** — needs a sudo this tooling
  does not have. Command in lextest §2j. The local mirror proved the client half;
  the Pi half is unexercised.
- **477 catalogued maps are still not on the Pi** (down from 509: `mapsync.py`
  pushed 32 and the Pi is now 1347 bsp, 1277 of them on the roster). The rest are
  maps this workstation does not have either.
- The 76-map Pi-vs-roster gap is explained: other gamemodes (`df_`, `ahop_`,
  `conc_`, `fy_`, `de_`) which the roster excludes by design, plus the six case
  mismatches above, which are now matched.

## Map downloads are live on the Pi — 2026-09-28

The last open item is closed. nginx serves maps from play.proto.bar with
`limit_rate 1m`, both url layouts resolve, and the content is right:

```
/maps/surf_utopia.bsp          206   1,020,745 B/s
/ftesurf/maps/surf_utopia.bsp  206   1,036,246 B/s
/lobbies.json                  200   (unaffected)
/maps/                         404   (no listing)
/maps/../../etc/passwd         404   (traversal refused)

bhop_1n5an3  2,538,880 B at 1,041,175 B/s
served sha1  f33756d2f7840d6858132dbdc041b109a37da5a5
roster sha1  f33756d2f7840d6858132dbdc041b109a37da5a5   <- identical
```

The whole chain is now measured end to end: catalogue -> pinned hash -> Pi
inventory -> data/mapdl.txt -> nginx -> client download -> the exact build the
roster named. The rate sits 2-4% over 1 MB/s, which is nginx's burst at the
start of a connection, not a leak.

### The install command I handed over was wrong, and the guard is why it cost nothing

`sed` was given `\&` in the replacement. A bare `&` there means "the whole
matched line", which was the intent; `\&` means a LITERAL AMPERSAND. So it
replaced `include snippets/surfd-admin.conf;` with a single `&` character --
which is both a syntax error and, had it loaded, the silent removal of the admin
vhost.

`nginx -t` refused the config and nothing reloaded, so the live box kept serving
and the admin login was never lost. That check was in the command BEFORE the
reload for exactly this reason. It is the second time in two days that a
shell-quoting fault has eaten a load-bearing character in this tree (the
ENGINE_PATCHES entry that lost its backticked nouns was the first), and the
standing rule stands: compose escape-bearing text with a file write, not inside
a shell string. A command that must be pasted into someone else's terminal is
the one case where that is hard, so it needs the guard instead.

### And a column index, again, immediately after writing the rule about it

Picking a test map from data/mapdl.txt used `$5` where the kb column is `$6`.
The tell was instant -- an empty candidate list rather than a plausible wrong
one -- but it is the same fault as the `$10`/`$11` awk that earned the CLAUDE.md
bullet, three days later and in the same session that cited it. The rule is
right; what it needs is a habit, and the habit is reading the file's own header
line before writing the awk rather than after it fails.

## The library is complete, and 0.1.14 could never have shown it — 2026-09-28

Two separate pieces of work that turned out to be one problem.

### What was missing, measured rather than recalled

471 of the roster's 1748 maps were not offerable. The split is the whole story:

    surf   1146 of 1174   97.6%
    bhop    131 of  574   22.8%

By catalogue: 463 Momentum-only, 4 KSF-only, 1 both, 3 legacy. **KSF was already
finished** — 931 Drive archives indexed and NOT ONE of them for a map we lacked,
which is a real check rather than an empty one because the index loaded and every
entry resolved. The four KSF-only holes (`surf_disappointed_fix`,
`surf_junglepics_ksf`, `surf_race_final`, `surf_vestige_fix`) are on KSF's
spreadsheet with no archive behind them and no Momentum publisher either.

`avail` is `-` on all 1748 rows, which nearly got reported as "0 fetchable". It
is only a finding because `arch` is populated; on an empty index the column reads
identically. Checked before quoting it.

### Momentum publishes the rest, with a digest

Every `_cache/*.dat` record carries `currentVersion.downloadURL` and `bspHash`.
The hash is the sha1 of the served file — verified against bhop_landmark2 before
any of this was written, not assumed — so `tools/mapgrab.py` can fetch and check
every file against the publisher's own digest.

HEAD'd all 464 rather than sampling: a 14-map sample gave mean 15.0 MB against
median 6.3 MB, a 2.3x spread on the total, because one map in it was 110 MB. The
real figure is 7.66 GB, and 12 maps over 100 MB carry 1.5 GB of it.

Result: **463 OK, 1 CURLFAIL** — `surf_solipsism`, whose published URL 404s.
The HEAD sweep predicted exactly one dead URL and named the same map, so the
prediction and the outcome agree. Zero `.part` files survived 464 transfers.

    pi 1350 -> 1813 bsp        offerable 1277 -> 1743 of 1748
    bhop 131 -> 574 of 574     surf 1169 of 1174

Verified end to end on a map fetched an hour earlier: `bhop_pandora` over
https at 1,041,220 B/s, served sha1 identical to the Pi's on-disk copy.

### Why the user's download had no button at all

Reported as "I just downloaded and it had no map download option. It just
failed." Two independent faults, and the second is the one worth keeping.

**0.1.14 was cut at 13:33; every map-download commit landed 19:41-20:17.** No
release had ever contained the feature. "Is the source pushed" and "what did the
user download" are different questions and only the second one was being asked.

**A rebuild alone would not have fixed it.** `ftesurf/data/mapdl.txt` is ignored
by `/ftesurf/data/*` and `$ShipGameFiles` is a NAMED list of four data files.
Without that file `ui_dl_load` reads nothing, every row comes from `search_begin`
and is already installed, and no row draws a button — the feature compiled in,
working, and invisible. Proved from the shipped artifact rather than inferred:
`ui_dlmap`, `downloadmap`, `ui_dl_start` and `mapdl.txt` all absent from
0.1.14's `menu.dat`, with `checkbuiltin` PRESENT in the same file as the control
that says the search works.

0.1.15 ships it: 150 files, `mapdl.txt` at 1743 rows, and the published archive
re-downloaded from dl.proto.bar and checked — sha256 matches, rows present.

### Faults of this leg

- **`mapscan.py` folded case for `servable` and not for the `missing` count 20
  lines below**, so it printed 477 where the truth was 471 — it counted the same
  six case-mismatched maps the fold exists to serve. Found only because the
  number was derived a second way and the two disagreed.
- **`mapsync --only` reported success on an empty selection.** Three maps on the
  cstrike/ftesurf mounts were dropped by the intersection against `--momentum`
  and the run said "nothing to do -- the Pi already has everything selected".
- **A warning count read an empty pipeline.** `build.ps1` prints via the host
  stream, so `2>&1 | Select-String warning` returned 0 against a build printing
  `Done. 0 warnings` three times. Re-run with `*>&1`: 14 lines, 3 matches. Same
  CLAUDE.md rule, new mechanism — the stream never arrived rather than the
  spelling not matching.
- **`echo -n` stripped VERSION's trailing newline.** Caught with `cat -A` before
  committing. That file crosses into a remote shell in publish.sh.

## The public leaderboard grows a run viewer, profiles and the imports

`proto.bar/ftesurf/board/` was a table of rank/name/time/gap/date with nothing
clickable, over 172 ranked rows on 36 maps. It is now five views behind one
hash route, and the live numbers are **766 maps, 740 with times, 4,791 runs to
watch**.

- **The run viewer** (`/board/api/run/<rid>`) is `recplot.parse()` -- the same
  parser the admin page has always used -- rendered by `web/runview.js`: the
  path coloured by speed, a dot that scrubs and plays with a live u/s readout, a
  speed strip with split ticks, and `#r=<rid>&at=<seconds>` so a link shares a
  moment rather than a run. An imported run is tinted with LN_FGNCOL, the same
  blue the imported line wears in the game, and says in words that its path is
  reconstructed.
- **Player profiles and search** (`/board/api/players`, `/board/api/player/<h>`)
  over ~5,000 people: times, contested records, top tens, maps finished, and
  completion per Momentum difficulty tier. 380 of our 536 board maps are rated.
- **The board takes `tier=imported|combined`**, with per-source counts on the
  tabs and a blue edge on imported rows. THE WEB DOES NOT HAVE THE IN-GAME
  PAGING HOLE (lextest 2h(f)): it pages with a real offset, so our row at rank
  222 on surf_utopia is reachable with "Show more".

### Still open

- **FIXED, and the residue is 3,795 rows.** The imported Date was our ingest
  date; `momdates.py` backfilled 81,290 rows and 996 replays on the live DB
  from the cached `created`, momentum going from 2 distinct dates to 80,843
  over a year. Verified against the pre-backfill copy: **0 ranked, community
  or ksf rows moved**. What is left are rows below momfetch's cached top-25 on
  boards whose own total reaches 26,112 -- they keep the import date, and
  `momdates` counts them rather than guessing. `momindex` alone cannot date a
  row: `tools/momimport.py` reads `date_ms` from the .mtv but writes it only to
  the manifest, never into the `.rec` header.
- **surf_utopia's public #1 is 0.060 s faster than Momentum's own #1**
  (53.565 against 53.625, a demo-corpus row with no board entry). The
  impossible-time check reports **0** because 0.5% slack on a 53 s run is
  0.268 s and this is 0.11% -- so the row is inside a tolerance chosen when
  the disagreements being hunted were whole seconds. Now that the imported
  board is the first thing a visitor sees, the slack is worth revisiting: an
  absolute floor (say 0.02 s) alongside the ratio would catch this class
  without touching the rounding case the ratio exists for. Not changed
  unilaterally -- dropping somebody's row is the operator's call.
- **`momquality` is still not shown on the web run page.** The in-game viewer
  warns when the ratio exceeds 1.05; the web one does not, and it should.
- **The maps list is 65 KB** and grows with the archive. Cached 60 s, fine for
  now, wrong at 2,000 maps -- it wants server-side paging or a search endpoint.
- **A profile's rows cap at 100 with an offset the page never uses**, so a
  player with 1,629 times shows the first 100. The endpoint pages; the UI
  does not.
- **Name fragmentation is real and visible**: `boro` / `borobongo` /
  `BoroBongo` are three guids, and our `Proto` and the Momentum `Proto` are
  different people as far as this site can tell. Per-install identity is the
  honest answer and merging by name would be an impostor's gift, but a player
  who reinstalls does split. There is no fix here without real accounts.

### Faults of this leg

- **`400 bad tier` broke old shared links.** `/board/api/map` shipped ignoring
  that parameter, and test_web.py pinned that `tier=community` still opens the
  ranked board. My "a typo should not quietly show a different board" reasoning
  was right in general and wrong against a contract somebody had already
  written down. The suite caught it in the first run.
- **Two profile orderings, both plausible, both nonsense at the top.** By rank:
  #1 of 1. By board size: #501 of 501, dead last. Neither was found by
  reasoning -- both were found by rendering a real profile and reading the
  first row. The fixture now has three boards so it rejects both at once.
- **"35 records" counted 35 boards nobody else is on.** True and useless. The
  contested count on that same profile is 0.
- **A COMMENT failed two builds.** test_board.py greps public bodies for
  `reason`/`verdict`/`reject`, and test_web.py greps for `innerHTML`; my
  comments used both words to explain why the code does not. Reworded the
  prose rather than loosening either grep -- a bare substring is the stronger
  check and the whole point is that it cannot be talked around.
- **An unquoted heredoc ate a backtick pair** in a throwaway script, printing
  `have: command not found`. Sixth occurrence of the documented trap, first
  in the `<<PY` direction rather than `\n`. Quote the delimiter: `<<'PY'`.

### The admin run page, and a defect it found in the public one

`admin_run.html` folds Verdicts, Receipt, Key and the recording header behind
`<details>` (633 -> 884 lines, ~2700 px -> ~1400). The closed summary carries
the state word, anything flagged starts open, and `summarise()` only ever
raises `open` so a re-render after a decision cannot shut a card the operator
opened. `git diff -U0` filtered for `post(|fetch(|csrf|/admin/api|keydecision`
returns nothing: no review line moved.

Its playhead is a PORT of `web/runview.js` rather than a share. The reasons
were measured, not assumed: `View.build()` clears its host and builds its own
canvases, so reuse would REPLACE the admin canvas and lose the forensic layer
(checkpoint dots, stage diamonds, warp/portal glyphs, spectate labels, dashed
teleport segments, axes) that runview does not draw at all.

**And it found a real defect in the public viewer by hitting it.** A `.rec`
starts before the timer does; `runview.js` clamped `seek()` to 0 and mapped the
speed strip with `X(t) = t/dur*w`, so the prestrafe was unscrubbable and drawn
off the left edge. Measured: rid 5 opens at -2.130 s, rid 4 at -3.840, 2.8% to
6.3% of those timelines. Fixed in 933a8d7 -- the timeline now spans t0..t1.

**Dim-ahead is only checkable by measurement.** Neither of us could tell by eye
whether the erase ran. Mean brightness of drawn pixels in the path canvas:
66.4 at t0, 101.3 mid, 133.7 at the end (admin: 54.2 / 76.1 / 96.1). Monotonic
because the erased span shrinks. Use this rather than looking.

**Headless virtual time cannot drive requestAnimationFrame.** A control page
counting ticks under `--virtual-time-budget=9000` reported 5 ticks over 71 ms
and a `setTimeout(3000)` that never fired, so a "press play and screenshot" arm
measures nothing. Hold the parent's `load` event open so real seconds pass.

---

## Three sets of shipped content that were never in a release — 2026-09-28

One root cause, three symptoms, all found from one report ("surf_666 said it
has no zones"; "the backdrops show as error"). **`release.ps1`'s ship set is a
named allowlist, and three things the game asks for BY NAME were never named.**
Nothing was broken in code; the archives simply did not contain the files.

Measured, not assumed: `find release/stage-* -path '*zones*' -name '*.json'`
is 0 across all 20 stage trees.

| What | Files | Size | Consequence on a shipped install |
|---|---|---|---|
| `ftesurf/maps/zones/local/*.json` | 609 | 2.5 MB | no zones for ANY map; `cl_scores.qc:2180` on all 587 downloadable zoned maps |
| `ftesurf/gfx/thumbnails/*.png` | 12 | 31.5 KB | an error texture beside EVERY player's name, always |
| `ftesurf/gfx/mapshots` | 5,078 | 1.1 GB | deliberately not shipped — see the backdrop entry below |

### Why the icons were an error texture and not a blank

`drawpic` on a missing pic substitutes `R2D_SafeCachePic("no_texture")` and
draws it — `pr_menu.c:622-632`, read this session. The 0 it returns is
advisory and everything ignores it. The QC comment over `ui_map_backdrop`
claimed the opposite ("drawpic no-ops on a miss, so the cost of being wrong is
a flat backdrop") and that claim is what kept the blind fallback alive.

`drawsubpic` does NOT do this (`:688-712`), and `precache_pic` never draws at
all (`:820-861`), so only one of the three builtins has the behaviour. With
flag 512 (`PRECACHE_PIC_TEST`) `precache_pic` returns `""` when an image will
not load, which is an existence test that does not go through `fopen`.

`cl_players.qc:403` draws a voice icon per row with `drawpic`, and the idle
state `speaking_off` is always on screen, so this was not an event — it was
permanent.

### The backdrop, and why the atlas was the answer

`gfx/mapshots` is 269 MB at 720p and 876 MB at 1080p against a 33 MB
installer, so it will never ship. `gfx/mapthumbs` already does — six atlases,
28 MB, one 128x72 cell per map — so the picture was distributed all along at
1/225th of the pixels. `ui_bgatlas` blows that cell up and gaussian-blurs it:
nine taps, `{1,2,1}` separable, offsets in SOURCE TEXELS so the blur is
resolution independent, each composited at `w_i/(sum so far)` so the running
result is the exact weighted average rather than nine layers of paint.

Tint and wash were measured, not eyeballed: at the sharp path's 0.7 dim and
0.4 wash the top-left 500x300 of the frame was mean luma **9.7 of 255** — a
backdrop nobody can see. Full brightness and a 0.25 wash give **14.7** with
the panel still legible. A blur that has destroyed every edge cannot compete
with text the way a sharp photograph can.

### Zone downloads (`cl_zonedl.qc`)

Shipping the library fixes installs; it does not fix a map zoned after a
release, because both download paths compose exactly `maps/<name>.bsp`
(`PF_m_downloadmap`, and `cl_parse.c:1002`). CSQC now asks
`cl_download_zonesrc` — a CLIENT cvar, never `sv_dlURL`, which is whatever
host you connected to — and writes to `maps/zones/dl/`, tried LAST of the
three file sources so a fetched file can never beat a shipped one or your own
edit.

### Still open

- **The nginx zone location is not installed.** `/etc/nginx` needs root and
  `proto`'s NOPASSWD list covers only the `ftesurf@N` units, so this is one
  operator command. `surfd/maps.nginx` carries it and the 609-file set is
  already at `/srv/nvme/ftesurf-site/zones`. Until it runs, every zone fetch
  404s — the designed miss path, so the client degrades to its old behaviour.
- **`ftesurf/data/maps/zones/dl/` is never pruned.** A zone fetched for a map
  you played once stays forever. Bounded by the library's own size (2.5 MB for
  all 609) so it is not urgent, but nothing deletes it and nothing ages it
  out. Note the `data/` prefix: QC fopen reads the whole VFS but writes into
  the sandbox, so the relative path in the source names two different places
  depending on whether it is being read or written.
- **One attempt per map CHANGE, not per session.** `zdl_tried` holds only the
  last map asked about, so a rotation A -> B -> A asks for A twice. Bounded by
  map loads, which are the most expensive thing the client does, so a table of
  every name tried was judged not worth it. Caught on review by ftesurf-a1
  when the comment claimed the stronger property.
- **110 of the board's 740 maps have no web screenshot**, because they have no
  `thumbuuid` in `mapmeta.txt`. They render with no hero and no gap, which is
  correct, but they are also the maps a reader is least likely to recognise.
- **`tools/mapshots_web.py` output is not wired into any deploy.** The 630
  JPEGs were scp'd by hand to `/srv/nvme/surfd/data/webshots`. A map that
  joins the board later gets no picture until someone re-runs it.
- **Maps with no atlas cell get no backdrop either.** `ms_bgpage < 0` draws
  the flat fill, which is the old behaviour and correct, but it means the
  "every map has a backdrop" claim is really "every map with a thumbnail".
- **The half-texel inset in `ui_bgatlas` is predicted, not observed.** It
  exists because bilinear at 15x reaches into the neighbouring atlas cell and
  a neighbour is a different map. If a stripe of an unrelated map ever appears
  down one edge of a backdrop, that inset is where to look.

---

## A ship-set guard this session wanted, which does not exist yet — 2026-09-28

(Its sibling -- every test cfg turns the config auto-save off -- is
`tools/cfgguard.py` since 2026-10-03.)

### A ship-set gate: DONE -- `tools/shipguard.py` (2026-10-05)

Built, and it caught two defects in itself on the way, both of which read as a
clean pass.  The item is closed; what follows is what a future reader must not
relearn.

It parses `$ShipRootFiles`, `$ShipGameFiles` and `$ShipGlobs` straight out of
`release.ps1` -- it must not carry a copy of them, or the two drift and the gate
grades a ship set nobody ships -- resolves them exactly as `release.ps1` does
(non-recursive, with each entry's Filter and Deny), then sweeps `src/**/*.qc` for
asset paths and asks whether each one is in the result.  Exit 1 on any unexplained
miss.

The "cheap version" this item proposed was a `data/` + literal-asset sweep.  Two
corrections, both measured:

* The DIRECTORY rule proposed here is the one that would have MISSED the
  zone-library fault, because `Zone_LoadForMap`'s literal ends in a slash
  (`maps/zones/local/`) and a per-file comparison against it finds nothing.  The
  rule that works is a PREFIX over the shipped set, which is also what catches a
  `strcat`-built name (`scripts/soundscapes_` + map + `.txt`) and an extensionless
  one (`precache_pic("gfx/thumbnails/speaking_off")` resolves to `.png`).
* "Some misses are correct" was right but its two named entries were not the
  expensive ones.  The table is now DENY_EXACT vs DENY_PREFIX, 20 entries, every
  one carrying a reason, and all 20 are ASSERTED TO FIRE -- a deny rule that cannot
  fire claims to explain something nothing asks about.

THE TWO SELF-DEFECTS, kept because each looked like a pass:

1. **A prefix deny key swallowed its own subtree.**  `maps/` is a real search-root
   literal, and as a prefix it excused `maps/zones/local/` with a search root's
   reason -- so the largest of the three historical faults was invisible and
   `--mutate 12` reported NOT CAUGHT.  Splitting exact from prefix is the fix;
   running the falsifier is what found it.
2. **`fopen` was classified as an existence probe.**  It is a LOAD when the mode is
   `FILE_READ`, and excusing it hid `data/mapdl.txt` entirely -- the omission that
   forced the 0.1.15 re-cut read as a clean pass.  The MODE decides now, not the
   builtin.  This is the most important line in the tool: a read whose failure is
   silent (the feature draws nothing and complains nowhere) is the worst thing to
   classify as optional.

VERIFIED.  All five data files the menu reads flip to MISS when hidden, including
`mapdl.txt`; `--mutate` catches 9 of the 13 ship globs including `gfx/thumbnails`
and `maps/zones/local`; base run 0 misses over 143 asset literals; 0 dead deny
entries.

NOT COVERED, and it is a limit of the method rather than a bug: 4 of the 13 globs
have no literal in anything we author naming them, because the ENGINE resolves them
by convention -- `cfg` (the engine execs `default.cfg` itself, and no shipping cfg
execs another), `glsl` and `scripts` (a shader says `prog milk_scene` and the engine
builds the filename), `gfx/env` (`r_skybox milk` loads `gfx/env/milk.png`,
gl_warp.c:133).  `csprogs.dat` is blind for the same reason.  So a clean run means
"no literal asset path in src/ is missing from the ship set", NOT "the archive is
complete".  Extending the sweep to `.shader`/`.cfg` was measured and would add
exactly ONE path (`glsl/milk_dot.glsl`), which is not worth the prose false
positives those files carry.

WIRED 2026-10-05 as `release.ps1` **gate 4**, in the Gates step, so it runs before
staging and packing and ONE call site covers both the Windows and the Linux drop
(they share `$ShipGlobs`).  THE FALSIFIER ABOVE WAS RUN, NOT REASONED ABOUT: with
`'ftesurf/data/mapdl.txt'` deleted from `$ShipGameFiles` -- 0.1.14's actual fault,
reproduced -- `-Bump patch -BuildNumber 89 -DryRun -AllowDirty -AllowStale` printed
`MISS data/mapdl.txt   src/menu/m_main.qc:2117`, `reached through fopen()`,
`FAILED: 1 literal asset path(s) the archive would not contain.` and stopped with
no `[5] Stage` step at all.  Restored, the identical command ran all eleven steps
to exit 0, gate 4 reading `143 -- 56 shipped, 53 denied, 33 runtime, 1 pattern`
and the run carrying zero warnings.  The two `-Allow*` flags were passed only to
get past gates 1 and 2 -- a concurrent session had `ftesurf/cfg/default.cfg`
modified and its QC newer than the installed .dat -- and gate 4 has no override.
Three properties worth keeping if you touch it: the tool AND `python` are checked
for existence and either missing is a hard Fail, because a gate that cannot run
must not read as a pass; the tool's own stdout is echoed into the release log, so
a run records what it saw rather than only that it passed; and the failure message
names the two ways out (an allowlist entry, or a DENY with a stated reason).

## Full-depth boards are live; five things that fall out of it — 2026-09-29

The boards went from the top 25 of each to a crawl towards every place:
`momfetch --depth`, `momwatch --want/--backfill`, `momboards` incremental, and
the Pi's cron at `--depth -1 --want 25 --backfill 15`. Roughly 10 days to full
depth at ~3,000 requests/day. What that leaves open:

- **NOTHING CAN SHOW A RANK PAST 200.** `surfd.py:300` `BOARD_LIMIT_MAX = 200`.
  We are now collecting 2.9M times of which ~450k are reachable by any reader, so
  the other 2.5M are being stored for a feature that does not exist. The feature
  worth having is "where would I rank" / a name search, which is the only reason
  full depth beats top-200. Either build it or stop the backfill at `--depth 200`;
  doing neither means paying for rows nobody can see. Lex chose full depth knowing
  this.
- **The `runs` table is heading for ~2.9M rows, about 900 MB.** Measured
  307 bytes/row against 26 MB at 85,924 rows, and three indexes on `runs`. 65 GB
  free so it fits, but nobody has measured board query latency at that size --
  check `/api/board` and `/board/api/map` p95 once the crawl is a few days in, and
  `VACUUM` has never been run on this database.
- **momwatch fetches per MAP, so one stale stage board costs ~16 requests.**
  Staleness is measured per board, then what it hands momfetch is `--map` plus
  `--refresh`, which re-asks page 1 of every board that map has. The fix is an
  explicit `--board mapid:gm:tt:tn` selector in momfetch and passing the exact
  list. Its docstring claimed the opposite until 2026-09-29 and now states the
  true cost.
- **`mapwant` is never pruned and has no `served` column.** One row per map so it
  cannot outgrow the library, and `--want N` reads the N most recent, so a map
  viewed once long ago quietly stops being considered. That is the intended
  behaviour and it means the queue is a priority list, not a work list — nothing
  guarantees a viewed map is ever deepened except the backfill reaching it.
## Milk visualizer (Patch 467) -- 2026-09-29

### Still open

- **A STOCK MSYS2 MINGW64 CANNOT BUILD THE ENGINE: `opus.h` IS NOT WHERE THE
  MAKEFILE LOOKS.** `engine/Makefile:1073` adds `-I/usr/include/opus` (the msys
  runtime tree); the `mingw-w64-x86_64-opus` package installs it under
  `/mingw64/include/opus`. Patch 467 was built on the laptop with
  `C_INCLUDE_PATH=C:\msys64\mingw64\include\opus`. Falsifier: `make m-rel
  FTE_TARGET=win64` without that variable stops at `snd_dma.c:390`.
- **A BUILD WITHOUT pkg-config's freetype2 SILENTLY PUTS EVERY TTF ON THE BITMAP
  FONT.** `engine/Makefile:1102-1107` adds `-DNO_FREETYPE` when pkg-config finds no
  freetype2, and loadfont then returns FONT_DEFAULT without a word (sh_font.qc's
  "failure is not fatal"). The laptop's first Patch 467 build did exactly that.
  `build.ps1` could refuse an exe that neither imports `libfreetype-6.dll` nor
  links FT_Init_FreeType. Falsifier: build without `mingw-w64-x86_64-freetype`
  installed, open the menu.
- **`!!cvar4f` UPLOADS THREE COMPONENTS.** `engine/gl/gl_backend.c:4416-4417`
  (SP_CVAR4F -> `qglUniform3fvARB`). Nothing uses `!!cvar4f` today. Found reading
  the shader system for Patch 467; falsifier: a program with `!!cvar4f` on a vec4
  uniform draws its w as 0 (or raises GL_INVALID_OPERATION).
- **THE MENU TRACK DOES NOT SHIP.** `tools/mkmenumusic.py` writes a 13.5 MB WAV
  into `ftesurf/music/`, which is git-ignored and in no `$ShipGlobs` line, so a
  release has a silent menu (the visuals still run). Shipping it wants an OGG
  (~1.5 MB; no encoder on the laptop) and a ship-set line -- or leave menu music
  to whatever the player drops in. A decision, see lextest.md section 8.
- **THE SKY'S HORIZON SKYLINE HAS NEVER BEEN SEEN.** Every p467sky shot on
  surf_rookie was taken inside the start room, whose walls hide the horizon ring
  the spectrum bars stand on; the dome and the zenith were checked, the ring was
  not. Falsifier: `milk_sky 1` with music playing on an open map, look level.
  TRIED 2026-10-03 on surf_utopia_njv and NOT achieved: its spawn is an enclosed
  room too, `cmd setpos` 600 u up falls back to the floor within the 3 s wait (the
  board logs the landing) unless `cmd noclip` follows, and the world model's
  middle at z 15000 is outside every leaf (`voidvis: cluster -1 ... VOID VIEW`).
  What it needs is a known open vantage -- a stage start on an outdoor map, from
  the map's `info_teleport_destination` origins -- with `cmd viewpos` before each
  shot and the control taken at the SAME pose.
- **IN-GAME COSTS ARE SINGLE HUD READINGS.** The sky's ~0.7 ms (150.6 vs 168.1 fps,
  same view) is one instantaneous fps counter per state, not an average over an
  interval like the menu's `milk_bootcheck 4`. A proper arm would time a fixed
  replay with the sky on and off.
- **CSQC 3D POLYGONS CAN BE CORRUPTED BY A 2D FLUSH IN THE SAME FRAME -- read
  2026-10-03, still NOT reproduced.** `engine/client/pr_csqc.c` CSQC_PolyFlush's 2D
  branch rewinds with `cl_numstrisidx = csqc_poly_origvert;` -- the VERTEX origin
  where the INDEX origin (`csqc_poly_origidx`) is meant. Every fan has at least as
  many indices as vertices, so the cursor only moves backward, onto index ranges
  already queued in `cl_stris`. The counters are reset only by `clearscene`
  (CL_ClearEntityLists), not by `renderscene`, so the ordinary order (clearscene,
  3D polys, renderscene, then 2D -- the run line is 2D) overwrites indices of
  triangles that were already drawn and is harmless. It bites when a 2D polygon
  batch is flushed between queuing a 3D polygon and the renderscene that draws it,
  or before a SECOND renderscene in one frame. One-line fix (`origidx`), but it is
  the engine and wants an exe. Falsifier: R_BeginPolygon 3D quad, a 2D
  R_BeginPolygon quad, renderscene -- the 3D quad's second triangle is wrong.
- **THE NEW TRACKS AND EFFECTS DO NOT SHIP.** `tools/mkmusic.py` writes six
  tracks (~87 MB of WAV) and five effects into git-ignored folders, so a fresh
  clone or a release has a silent menu until someone runs it. Shipping wants OGG
  (no encoder on the laptop) and `$ShipGlobs` lines. A decision; lextest 9.
- **THE PANELS COST ~3 MS A FRAME ON THE N100 IN THE LATTICE.** In-world 86 fps
  against flat 122 at medium (MAIN). The slabs left the SDF (107 without them in
  the scene at all); what remains is the slab's shading and the per-pixel trace,
  unmeasured separately.
- **THE MONOLITH'S FOREST IS MOSTLY BEHIND THE PLAY DIALOG.** PLAY is the 2D create
  screen, so the terrace forest shows at its edges and in flights (and far off
  from MAIN). Moving the forest to a panel station, or giving PLAY a panel, would
  show it.
- **PICKING AND THE ORBIT ARE PROVEN WITH A FAKE CURSOR ONLY.** `milk_bootcheck 5`
  shows the trace landing on the entry at rest (to 0.002 px) and after an orbit;
  a real mouse, and dragging the volume slider on a panel, are unexercised.
- **THE IRIS FIBRES STRIPE.** 56 radial fibres are near the vessel's scene
  resolution and band visibly in the stills (motion unseen); and the tree
  crowns' 2x2 neighbourhood can clip a crown that reaches two cells over.
- **THE TRACKS ARE LEVELLED BY RMS, NOT BY EAR.** `master()` normalises RMS, which
  a sub-bass track satisfies with energy nobody hears -- so `ftesurf_void` was the
  loudest track by ear (-20.0 dB(A)) until its bells came down 8 dB (now -26.4).
  The spread is still -22.9 (monolith) to -33.1 dB(A) (dream, which is
  `mkmenumusic.py`'s own). An A- or K-weighted master would even them; it moves
  every track, so it is a decision.
- **ONE HARNESS RUN STALLED 100 s AT START, UNEXPLAINED.** 2026-09-30, a
  `milk_bootcheck 1` monolith tour: its 6 s step fired at 103 s, beside a
  `[focus] window is foreground` line. The identical rerun was normal (84 fps)
  and it has not recurred. A window being dragged blocks the main thread, and
  someone was at the laptop; not shown.
- **FRAME RATES ON THE N100 MOVE ~30% RUN TO RUN.** The same arm (monolith,
  720p, every tick) measured 17 and 24 fps ten minutes apart. Quote the pair,
  or a control run beside it, not one number.
- **THE SPEED PAGE IS MEASURED ON THE N100 ONLY.** Native, FSR 1, the
  checkerboard and the coarse pass exist (AGENTS, "THE SPEED PAGE") and are all
  off by default; nothing here says what they cost on a desktop GPU.
- **FSR 1 COSTS ~15 ms AN UPDATE ON THE N100 AT 2256x1380** (lattice 123 -> 38
  fps), more than the scaling saves there. Ours is GLSL 1.30: twelve
  `texelFetch`es and no fp16, where AMD's gathers; `textureGather` (GLSL 4),
  EASU without RCAS, or FSR every other tick would each cut it. Unmeasured.
- **THE COARSE PASS PAYS ONLY IN THE FRACTAL** (+19% at a raymarch a tick).
  The monolith and the vessel came out within noise (+3%, twice each): their
  rays pass near something early, where the cone has to stop, and their cost
  is the stepping near surfaces, which no start distance skips.
- **THE CHECKERBOARD HALVES DETAIL IN FLIGHT, BY DESIGN.** While `M_CAMFWD.w` is
  up the resolve fills from the neighbours instead of the last frame: history
  at an edge passes the neighbourhood clamp and left teeth. At rest it is the
  full image.
- **THE STREAKS HIDE BEHIND MODELS AT ONE DEPTH, AT DRAW TIME.** Each station's
  streaks fly at a single distance (its anchor + 5% + 2.5 m), so a model between
  that and the camera hides them and one behind does not -- a ring does not
  wrap round the cube, it passes behind it. And the test is made as each line is
  drawn into the trails: an echo drawn beside the cube stays drawn if the cube
  turns over it (decay 0.84 a tick, so ~0.2 s). The monolith tags no models.
- **THE STREAKS' WAVEFORM IS 8 BITS OF THE RAW MIX.** At the harness's
  `musicvolume 0.02` it quantises to a step or two, so the lines come out
  smooth; at the owner's 0.2 it is ~13 steps and the gain (capped x12) covers
  it. A waveform row the engine levels itself would take the volume out of it.
- **THE FRACTAL WORLD HAS NO TRACK OF ITS OWN** -- it plays `ftesurf_void`.
- **A MANDELBOX WAS TRIED FOR PLAY AND DROPPED.** Seen from outside it read as a
  lumpy cube at any scale tried (2.0-3.0, -1.5 to -2.6); PLAY is the
  pseudo-Kleinian with a taller fold box instead. Its interior is the unexplored
  alternative.
- **THE BEAT GATES ARE TUNED ON GENERATED MUSIC ONLY.** `p468react` replayed the
  six generated tracks. A loud, compressed master has flatter bass ratios, so
  fewer kicks may clear the 1.3 gate: drop real songs into `ftesurf/music/` and
  replay them (one `REACT_TRACK` block per song in the cfg).
- **THE FILMS' CROP AND HOT SPOT ARE LOCATED BY HAND FOR TWO IMAGES.** Another
  x-ray under the same names gets markers in its crop and the glow in the wrong
  place.
- **THE MENU'S MOUSE-LOOK IS UNMEASURED.** A minimized harness has no cursor, so
  the easing, the hover nudge and the present-time parallax (`MM_Camera`) were
  read, never exercised. Falsifier: move the mouse across the main menu and watch
  the cube stay framed, with no snap when the cursor enters the window.
