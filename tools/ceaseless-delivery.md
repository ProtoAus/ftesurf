# bhop_ceaseless (Lex's list, 25 Oct 2026): P990 + P1002 delivery record

Hashes are SHA-256 prefixes. Times UTC, 25 Oct 2026. Task root
`C:\FTESurf-worktrees\ceaseless-20261025T0200Z` (shots and diffs under `artifacts/`).

| Lex's item | Patch | State |
|---|---|---|
| Start floor refraction "a little intense" | P990 | its Sine proxy swings $refractamount 0.005-0.01 (drew a static 0.05) |
| Alpha textures sort incorrectly | -- | not identified; lextest asks Lex to point at it |
| Missing wall textures, bright cracks, colour highlights at spawn | P990 | 6-face pre-7.5 cubemaps load; reflections not darkened by $color |
| Roof missing looking up 45 degrees | P990 | sky mask written 2x farther on Source maps (r_sky_forcedepth_scale) |
| Start-platform button / labels without colour | P990 | UnlitGeneric base + $envmap drawn (vmt/unlitreflect#BASE) |
| Water not animating, water warp (save 6) | P990 | $flowmap water animates (frames 1 s apart: 23.5/14.8/7.0% of pixels); $underwateroverlay still not drawn |
| No rain drops | P990 | rain's detail scroll and mask: small, moving streaks |
| Chain, tree, butterfly, dragon colour | P990 | same cubemap fix |
| Speed trigger does not push (*5, AddHorizontalSpeed) | P1002 | AddSpeed inputs + filter lookup: walking in under the table pays +500 (530 u/s) |
| info_particle_system not loading; read all particle systems | P1002 | 22 of 23 systems baked (particles/bhop_ceaseless.cfg); images load; colour fade over life not translated |
| Save 7: glass/water floor, black portals, black detail, roof, tree | P990 | palm-room floor, cracks, crystals drawn; no black regions in the rig shot |
| Sword refraction static, z-fights (save 9) | P990 | ripple animates (vmt/refractanim), decal bias 2 |
| Bridge gates missing (save 11) | P990 | FadeMaxDist -1 props drawn (3,100 props on 25 maps) |
| Read all entities, add func_lod | P1002 | func_lod: Solid key = not solid, Source's distance fade (198 here, 2,167 on 44 maps) |

## Builds

- Engine: ftequakers main `3a7a48a83`, annotated tag `patch-990` (P990 + both review rounds).
- Install exe: branch `p990-installs` `c07242eb5` = `3a7a48a83` with engine/common/fs.c,
  engine/client/m_download.c, engine/client/sys_sdl.c at patch-983 (`1b2227972`), holding back
  pi.dev's P987, P988, P989, P995 (entries claim no deployment; nobody cleared them). The code diff
  from patch-983 has the same patch-id as P990's own commits. Stamp
  `git-7843-patch-990-1-gc07242eb5` (16 hits, one string). ftesurf64/fteqw64 `6d14fb17`.
- hl2 plugin `7205771c`, built from `3a7a48a83` (the held-back commits touch no plugin file).
- QC: FTESurf main `bc95d08e` (built from the worktree at that tree): qwprogs `04466ec0`, csprogs
  `2e6801f9`, menu `2a0a3f80` (unchanged). fteqcc `c24ede65`, 0 warnings.

## Deployed

- 05:08:28Z C:\FTEQuake: fteqw64.exe `6d14fb17` (.prev `495c188e`), fteplug_hl2_x64.dll `7205771c`
  (.prev `6a8995ec`).
- 05:11:05Z Pi lobbies 1-12 (`build.ps1 -Pi`, nobody on any lobby, no -PiForce): live qwprogs
  `04466ec0` / csprogs `2e6801f9`, .prev `02837107` / `a7a2b239` (ftesurf-7e's 28dfc228 deploy).
  All 12 units active from 05:11:09-05:11:20, same MainPIDs at 05:22:33Z, 12 lobbies on the board.
- The same run synced C:\FTEQuake\ftesurf (qwprogs/csprogs .prev = 7e's pair); 05:11:50Z
  C:\FTESurf\ftesurf by hand, same hashes and .prev.
- C:\FTESurf\ftesurf\particles\bhop_ceaseless.cfg `cae9cf22` (re-baked with pcf.py's materials/
  prefix; previous kept as `.pre1002b-20261025T0430Z`), data/mapparticles.txt carries its 23 lines
  (backup `mapparticles.txt.pre1002-20261025T025528Z`). C:\FTEQuake has no particle bakes (as before).
- 05:35:10Z C:\FTESurf (Lex's game closed, his go-ahead): ftesurf64.exe `6d14fb17` (.prev
  `495c188e`), fteplug_hl2_x64.dll `7205771c` (.prev `6a8995ec`). Both installs now match.
- 05:35:38Z lobby smoke (`tools/pi_lobby_smoke.py`, lobby 2 port 27520, C:\FTESurf's new exe, fresh
  client with no csprogs): served csprogs `2e6801f9` = the deployed build, board drew (surf_beginner,
  screenshot looked at), no QC error, 0 failures. Rig trimmed to logs/screenshot/downloads.

## Not done / limits

- C:\FTESurf (the checkout) sits at 28a442f2 with tracked edits, so it was not fast-forwarded; its
  tools/pcf.py predates the materials/ fix.
- BACKLOG.md "bhop_ceaseless (P990, P1002): what is left" has the rest, including surf_boreas'
  stale particle bake (left alone: Lex's boreas checks are pending) and the latent filter case.
- None of it is owner-checked: lextest.md has the checks.

# P1012-P1015 (Lex's lists 2 and 3 of 25 Oct, and his first list's leftovers): delivery record

Task root `C:\FTESurf-worktrees\pcfcolour-20261025T0540Z` (shots under `artifacts/`).

| Lex's item | Patch | State |
|---|---|---|
| Particle colour changes over life not translated | P1012 | Color Fade -> rgbdelta (+ engine pre-age cap); gatelight warm to blue, crystal green to pink |
| Underwater overlay not drawn, engine warp instead | P1013 | water_cheap volumes draw effects/water_warp01; overlay-less water: no warp, fog kept |
| surf_boreas bake has the image-path bug | P1012 | re-baked: tesla_glow draws its own image (the dome is a compact glow) |
| Saves 14-15 missing particles | P1012 | startboost1 circles, butterfly dots drawn (Source's 100000 draw distance) |
| Save 16 boost particles in a square | P1012 | spread along both rails (box placed by cl_emit.qc; Source's 100 emission rate) |
| Save 17 particles behind the wall | -- | the blob is a gatelight emitter 325 units off, in view; Momentum sends every system (no PVS cut) |
| Save 21 redrain bundles up | P1012 | spread across the wall |
| Saves 19-20 tunnel particles / pop-in | P1012, P1014 | spiral's ring drawn; the tunnel pane fades from ~700 units |
| Saves 23-24 portal pops in | P1014 | pane alpha honoured, no depth write while fading |
| Save 28 drops at random angles | P1012 | rotationstart 45 + Source's angle: upright |
| Download errors at map load | P1015 | no doubled url, no refused map pak; booster.wav is missing from the map itself |
| Saves 25-27 water lines from far away | -- | measured (refraction offset at distance), not fixed: BACKLOG, a Momentum shot decides |
| Save 13, saves 19-20 facets, save 18 | -- | BACKLOG |

## Builds

- Engine: ftequakers main `f319b575f`, annotated tag `patch-1015` (P1012's p_script.c cap, P1013,
  P1014, P1015, two review rounds). Install exe from that commit with nothing held back: the
  installed patch-1003 build already carried pi.dev's P987-P989/P995 (record 62cf29f9). Stamp
  `git-7849-patch-1015-0-gf319b575f` (16 hits, one string). ftesurf64/fteqw64 `5b8e3de0`.
- hl2 plugin `e9fba935` from the same tree (byte-equal to the rig-tested build).
- QC: FTESurf main `ecca95fd`: csprogs `337a78e3` (P1012's cl_emit.qc), qwprogs `04466ec0` and
  menu `2a0a3f80` unchanged. 0 warnings.
- Bakes (tools/pcf.py at `ecca95fd`): particles/bhop_ceaseless.cfg `b9340414`, surf_boreas.cfg
  `7ca03ba3`, data/mapparticles.txt `9b373966` (other maps' rows unchanged).

## Deployed

- 08:06:56Z both installs, no game running: C:\FTESurf\ftesurf64.exe and C:\FTEQuake\fteqw64.exe
  `5b8e3de0` (.prev `57060bff`), fteplug_hl2_x64.dll `e9fba935` (.prev `0cc86b08`). fteqwsv64 and
  the other plugins unchanged (no server or plugin code in the batch).
- ~08:07Z Pi lobbies 1-12 (`build.ps1 -Pi`, nobody on any lobby, no -PiForce): csprogs `337a78e3`,
  qwprogs `04466ec0` (same bytes). The same run synced C:\FTEQuake\ftesurf (csprogs .prev
  `2e6801f9`); C:\FTESurf\ftesurf by hand, same hash and .prev. seed_csprogs: both installs
  `5f138138`.
- 08:08:47Z C:\FTESurf\ftesurf bakes (previous three kept in the task root,
  `tmp/bake-installed-before-*`: `975b9a78`, `3985adcd`, `9a977983`). C:\FTEQuake has none.
- 08:09Z lobby smoke (`tools/pi_lobby_smoke.py`, lobby 2 port 27520, C:\FTESurf's new exe): served
  csprogs `337a78e3` = the deployed build, board drew (surf_beginner, screenshot looked at), no QC
  error, 0 failures. Rig trimmed to logs/screenshot/downloads (6.7 MB).

## Not done / limits

- Not owner-checked: lextest.md's P1012-P1015 entry.
- BACKLOG "bhop_ceaseless (P990, P1002, P1012-P1015)" holds the rest.

# P1016-P1020 (Lex's fourth list of 25 Oct: butterfly orbit, Momentum shot, water cost, ent_info): delivery record

| Lex's item | Patch | State |
|---|---|---|
| Butterfly particle should spin around it | P1017 | orbit + spawnmode shell; butterfly, spiral, gatelight, stars turn (rig ring A/B) |
| Save 25 water from far away (Momentum 0021) | P1019 | refraction offset falls off past 512 units: fine-line energy 19.5 -> 14.1 (Momentum 12.9) |
| Refraction/reflection cost at renderscale 2; micro-audit | P1018, P1020 | sky room water shares targets (4.3 -> 3.3 ms over the start room), 1024 cap; hl2_water 5 screen-space (3.0 -> 1.4 ms in the start room) |
| ent_info "unimplemented class" for info_particle_system | P1016 | says the client draws it (and the plugin applies color_correction) |

## Builds

- Engine: ftequakers main `d37aa2296`, annotated tag `patch-1020` (P1017-P1020 + review rounds on
  7e's 15d288cdd). Stamp `git-7859-patch-1020-0-gd37aa2296` (16 hits, one string). ftesurf64/fteqw64
  `5c5df1fc`; hl2 plugin `29e53471`. fteqwsv64 and the other plugins unchanged (no server code).
- QC: FTESurf main `6b7d57b3` (on 7e's 1861831b): qwprogs `19e09cca` (P1016), csprogs `b3529a28`
  (P1017 shape 3, P1020 menu row), menu `069ec469` unchanged. 0 warnings.
- Bakes (pcf.py at 6b7d57b3): particles/bhop_ceaseless.cfg `b5ccdeea`, surf_boreas.cfg `7ca03ba3`
  (unchanged), data/mapparticles.txt `c05555ae`; they need patch-1020's engine (orbit/shell).

## Deployed

- 11:05:40Z both installs, no game running, installed state as 7e's record: ftesurf64.exe/fteqw64.exe
  `5c5df1fc` (.prev `c416c542`), fteplug_hl2_x64.dll `29e53471` (.prev `e9fba935`).
- ~11:06Z Pi lobbies 1-12 (`build.ps1 -Pi`, nobody on any lobby, no -PiForce): qwprogs `19e09cca`,
  csprogs `b3529a28`, .prev `117c0942` / `5c61096f`. Same run synced C:\FTEQuake\ftesurf; C:\FTESurf
  by hand, same hashes and .prev; seed_csprogs `1c79fdae` in both.
- 11:07:13Z C:\FTESurf\ftesurf bakes (previous kept in the task root tmp/bake-installed-before-*).
- 11:07Z lobby smoke (lobby 2, port 27520, C:\FTESurf's new exe): served csprogs `b3529a28`, board
  drew (surf_beginner, screenshot looked at), no QC error, 0 failures. Rig trimmed (6.7 MB).

## Not done / limits

- Not owner-checked: lextest.md's P1016-P1020 entry. hl2_water 5 is opt-in (Lex's cfg stays 2).
- BACKLOG "bhop_ceaseless (P990, P1002, P1012-P1019)": water colour (cyan vs Momentum's blue), the
  main view's reflection at hl2_water 2, mode 5's fog-colour reflection misses.
