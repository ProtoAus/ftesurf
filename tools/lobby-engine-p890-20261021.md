# Lobby and install deployment — P881, P882, P886, P890, 2026-10-20/21 UTC

Lex 21 Oct: limitmovement and slide "do it", ropes, network2008's fail teleports, per-map fix files "do
it"; "ship now, fix after" for multi-tick limits; the 34 zone-tool triggers are a follow-up. Five review
rounds (control flow and evidence, a cheater's gain). Deploy order per the reviews: reader, then QC (its
empty-target guard must precede P881's engine, and an engine applying a fix with old QC writes no
`entfile`), then the native with the fix file.

## Source and builds

ftequakers main `b3d851127` (tag `patch-890`: P881 `902e48750`, P882 `3fb0f76cc`, P890 `b3d851127` on P888's
`e6d7ca9f4`), patch log `2af5c856f`; FTESurf main `f4b00b9e` (P881 `ca76a34c`, P882 `536db9be`, P886
`1f6b9263`, P890 `f4b00b9e`). Stamp `git-7640-patch-890-0-gb3d851127` (one string per binary).

| Binary | SHA-256 | Built |
| --- | --- | --- |
| fteqw64.exe (client) | `abe4e7f9...` | worktree, build.ps1 -Engine -Full -NoDeploy |
| fteqwsv64.exe | `862a2ccf...` | same |
| fteplug_hl2_x64.dll / fteplug_cod_x64.dll | `f27ea1a5...` / `e7535d19...` | same |
| fteqw-svarm64 / fteplug_hl2_arm64.so | `3c2dbd26...` / `84e04c8b...` | Pi /srv/nvme/agent-work/ents881-20261020T1620Z, sv-rel + plugins-rel arm64 |
| qwprogs.dat / csprogs.dat | `29856955...` / `5f6d1119...` | build.ps1 -Pi from a clean worktree at f4b00b9e |
| cfg/maps/entfix_surf_network2008_final.cfg | `37100699...` | f4b00b9e |

## Gates

- PC: pm_selftest (15 new checks) on the full build; cfg/test/p890fix.cfg (21 modified, drops arrive at
  fall2 at 0..-24 u/s against -1260..-1272 without the fix), p882lim/rec/rec2/sim/edge(2).cfg; test_entfix
  15/15, test_reccheck 801/801, reccheck over ftesurf/data/runs 213/337 with faults before and after.
- Pi gate (owned overlays, port 27619, new pair against the live patch-889 pair): pm_dettest equal on
  bhop_eazy, surf_ace, surf_boreas, surf_pantheon, surf_axil (16 lines each); colin_blaster 9194, demise
  3140, sandtrap 5136 and a kitsune run PASS on both; `entfile 4242` REFUSEd as a different lump and
  `entfile x1` as unreadable by the new native, both PASSed by the live one; a mover-10 relabel EXACT on
  the new, "not a mover this engine has" on the live; network2008 `0 removed, 1 added, 21 modified` on the
  new, nothing on the live. (A first run read a fix file staged before the relay blocks, 19 modified, and
  failed; restaged from the commit and rerun.)

## Deploy (UTC)

- 2026-10-20 23:48:55 tools/reccheck.py `2cd945c2` into game/tools under the sweep lock (was `e66270cb`,
  before P869: momtrig, catapult and reverse reach the Pi with it); backup `reccheck.py.pre890-20261020T234855Z`;
  imports, sweep.py --dry-run exit 0, no receipt-step failure.
- ~23:50 build.ps1 -Pi from the clean worktree: 12 lobbies, nobody on; qwprogs/csprogs swapped (.prev
  `89550455` / `25e272c3`), all restarted, live hashes read back. C:\FTEQuake QC by the same build.
- 2026-10-21 00:00:19 `pi_swap890.py` (guard: empty fleet, live pair patch-889 `82adf4b8`/`2c94e483`):
  native, plugin and the fix file under the sweep lock; rollback `*.pre890-20261021T000015Z`; 00:01:44 every
  unit a new pid on `3c2dbd26`, plugin mapped, UDP status, version patch-890-0-gb3d851127,
  pm_sourceversion 10; protected cfgs and data trees unchanged; health ok/12.
- 00:02-00:03 tools/pi_lobby_smoke.py with the new client against 27510 (surf_kitsune): served csprogs
  `5f6d1119`, board drew, no QC error, 0 prederr, screenshot inspected.
- 00:04:17 both installs (nothing running): ftesurf64.exe / fteqw64.exe `abe4e7f9`, fteqwsv64 `862a2ccf`,
  hl2 `f27ea1a5`, cod `e7535d19` (.prev P889's `a2ce8e61` / `05e3ccf4` / `9d369cd3` / `e2fa205c`); C:\FTESurf
  QC `29856955` / `5f6d1119` (.prev `89550455` / `25e272c3`); C:\FTEQuake gains cfg/maps with the fix file
  and tools/reccheck.py `2cd945c2` (.prev).

## Not done

- Records scan for warps the empty-target lookup produced before P881 (private note; BACKLOG).
- NEVER roll the sweeper below 890 once a lobby has written a mover-10 file; 890's rollback copy is
  patch-889.
