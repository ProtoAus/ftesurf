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
