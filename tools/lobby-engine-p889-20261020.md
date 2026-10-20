# Lobby engine deployment — P887-P889 (with main through P883), 2026-10-20

Lex's six-map list of 21 Oct (local): surf_demise's ramp (P887), surf_pantheon's floating ramp (P888,
Source mover 9), surf_nuclear's spawn hub on the lobbies (P889). Lex: "do it" (the integrated build) and
lobby deploys are "always yes". Peers asked first: ftesurf-19 (P877/P878/P880) and ftesurf-30 (P883) said
nothing of theirs on main must stay off the lobbies; ftesurf-2a's P882 (mover 10) merges on top.

## Source and builds

ftequakers main `e6d7ca9f4` (annotated tag `patch-889`) = main `0a884e464` + P887 `c9f9ff913`, P888
`d72ad64e8..6ed2387d3`, P889 `29d23b4ac..b6d5badf9`, merged on branch maps6-int. Stamp
`git-7637-patch-889-0-ge6d7ca9f4` (count + 29), one string per binary.

| Binary | SHA-256 | Built |
| --- | --- | --- |
| fteqw64.exe (client) | `a2ce8e61...` | worktree engint, m-rel -j2, ARCHLIBS given |
| fteqwsv64.exe | `05e3ccf4...` | worktree engint, sv-rel -j2 |
| fteplug_hl2_x64.dll / fteplug_cod_x64.dll | `9d369cd3...` / `e2fa205c...` | plugins-rel hl2 cod |
| fteqw-svarm64 | `82adf4b8...` | Pi `/srv/nvme/agent-work/maps6-20261020T1640Z`, git archive, sv-rel arm64 -j2 |
| fteplug_hl2_arm64.so | `2c94e483...` | same root, plugins-rel hl2 |

MODPLUGFUNCS_VERSION 6: the exe and the hl2 (and cod) plugin must be swapped together.

## Gate (`artifacts/pi_gate889.py`: new pair vs live patch-842 pair, owned overlays, port 27619)

- pm_dettest, every pre-888 line EQUAL on bhop_eazy, surf_ace, surf_boreas, surf_pantheon, surf_axil
  (pantheon trace 8353e678, mover ce9d56af = the Windows P888 build). `fixtrace` on pantheon
  4f01c891098e50ca -- bit-identical to Windows -- "wrapped 1 at proptrace" (its "unwrapped decided" is 0
  by geometry: a clip brush sits over ramp07); axil 85484f19, decided 82, wrapped 109.
- pm_verify PASS on both pairs: surf_colin_blaster_69000 9194, surf_demise 3140, bhop_sandtrap 5136.
- surf_nuclear: "Unable to load models/props_underground" 25 (live, no stand-ins) -> 4 (new + the
  placeholders dir); the 4 left have no .phy in real Portal 2 either.

## Swap (`artifacts/pi_swap889.py`, run by `artifacts/swap_waiter.sh` once the fleet was empty)

Guarded by an empty fleet (lobbies.json and each unit's UDP status), the live pair being patch-842's
(`2cf4be41` / `2ba5b17e`) and the gate's PASS; held `/tmp/surfd-sweep.lock` for the whole swap.
22:13:20Z: native and plugin renamed in (old inodes kept as `*.pre889-20261020T221314Z`),
`game/placeholders/{1tf,2csgo,3portal2}_placeholder.vpk` (sha256-checked, one mtime) and `placeholders`
appended to `ftesurf/fs_addons.txt` (backup `.pre889-20261020T221314Z`); the 12 units restarted one at a
time. 22:14:49Z: every unit a new stable pid, 0 restarts, new exe, new plugin mapped, UDP status,
`version` patch-889-0-ge6d7ca9f4, `pm_sourceversion` 9, stand-ins on `path`; health ok/12; cfgs, progs
and the runs/evidence/resume/saves/receipts trees unchanged by aggregate hash.

ROLLBACK: for each of fteqw-svarm64, fteplug_hl2_arm64.so, ftesurf/fs_addons.txt:
`cp <f>.pre889-20261020T221314Z <f>.rb && mv -f <f>.rb <f>`, then restart EVERY active unit. Never copy
over a running binary or a mapped plugin in place. Rolling back below 889 makes the sweeper REFUSE every
pin-9 file (final).

## Windows installs and the client connect (23:13Z)

PC check from copies of the integrated binaries (installs untouched until it passed):
- P887: surf_demise save 3 base shot reddish 29,346 (branch build 29,433, old 49), gap p50 red 56 (57).
- P888: surf_pantheon pm_dettest lines equal to the branch (fixtrace 4f01c891, wrapped 1); Lex's save
  001 at pin 8 EXACT 1955/1955, the pin-9 copy diverges at row 625; the drop's probe hits the clip brush
  over the real ramp (normal 0 .744 .668), no ramp07 triangle.
- tools/pi_lobby_smoke.py with the new client against 27510 on the new native: served csprogs 25e272c3,
  board drew, no QC error, screenshot inspected. Failures 0.
Installed 23:13:36Z in C:\FTESurf and C:\FTEQuake: client a2ce8e61 (ftesurf64.exe / fteqw64.exe),
fteqwsv64 05e3ccf4, hl2 9d369cd3, cod e2fa205c; .prev the P878 set (2b3d9817, 1814e7da / b9949d6f,
26c81233, 3f69a8fb / d67bc959). No game was running.

## Limits

- Players on an older client predict the phantom on pin-9 lobbies (snap on those props) and, without
  the game, miss the stand-ins' collision (prederr on surf_nuclear's hub) until they update.
