# Lobby and install deployment — P892, P893, P897, P906, 2026-10-21 UTC

Lex 21 Oct: the two P882 follow-ups "do em?" (limits checked every tick; the 34 zone-tool limit zones,
which became all 195 zone-tool triggers), the surf_boreas console spam ("do we need it still?"), and "hold
0.1.29 until your P893 is done, and merge it in" (via ftesurf-39). P893 went through seven review rounds
(control flow and evidence, a cheater's gain; the later ones the reader against a hostile .rec), P892 three,
P897 and P906 one each. Order: reader, then QC (an engine with the opt-in global absent does not split), then
the native, then the installs.

## Source and builds

ftequakers main `2ec65d027` (tag `patch-893`, on P895's `f323cb68f`), patch log `371c059e0` and
`cd3a30f45` (P906; it also removed a second copy of the 892/893/897 entries that `663374ed7` pushed by a
script slip). FTESurf main `230d0ebf` (P892 `be49e2ac` .. P897 `83f0c6a6`, records `230d0ebf`), P906
`7dfd7e92`. Stamp `git-7675-patch-893-0-g2ec65d027`.

| Binary | SHA-256 | Built |
| --- | --- | --- |
| ftesurf64.exe / fteqw64.exe | `7128cc24...` | C:\FTESurf, build.ps1 -Engine -Full, FteRoot at the tag |
| fteqwsv64.exe | `75723406...` | same |
| fteplug_hl2_x64.dll | `4fc9c1d7...` | same |
| fteqw-svarm64 / fteplug_hl2_arm64.so | `8b940174...` / `91438f53...` | Pi /srv/nvme/agent-work/ents881-20261020T1620Z/engine893 (git archive of the tag), sv-rel + plugins-rel arm64 |
| qwprogs.dat / csprogs.dat | `96c0d288...` / `391784ef...` | build.ps1 -Pi from a clean worktree at 230d0ebf |
| csprogs.dat (P906) | `b4de829b...` | build.ps1 -Pi from a clean worktree at 7dfd7e92 |
| tools/reccheck.py (Pi) | blob `80af85da` | 230d0ebf |

## Gates

- PC, on the integrated build (main + these patches; engine f323cb68f + P893): p893tick.cfg (the lock puts
  `sv_tickparts 0` back without sv_cheats; 8/8 caught at 1, 3/8 at 0), p892tool.cfg (cannonball wires 14,
  edicts 215/35/96/523/750 as the control, bh7 arrival, reverie inert), p897quiet.cfg (developer 0: no
  momlimit, no said>; developer 1: the line). Earlier rounds: p893rec.cfg (135 rows, every step one tick, 92
  fl 8; the msec-only count's control 53 of 132 two-tick steps). test_reccheck 820/820 with each exemption
  rule mutated away failing its case; 1,291 real recordings identical under the old and new readers.
- Full engine build: 74 warning lines, the same set as the P890 and P879 full builds.
- Pi gate (owned overlays, port 27619, the P893 qwprogs on both natives): pm_dettest equal on bhop_eazy,
  surf_ace, surf_boreas, surf_pantheon, surf_axil (16 lines each); colin_blaster 9194, demise 3140, sandtrap
  5136 and a kitsune run PASS on both; `sv_tickparts` "1" on the new native, unknown on the live one.
- P906: p892tool.cfg reverie 164 prederr lines before, 1 after; the same maps on the 0.1.28 exe with the
  release qwprogs and the P906 csprogs, identical counts.

## Deploy (UTC)

- 07:06:15 tools/reccheck.py `80af85da` into game/tools under the sweep lock (was `2cd945c2`); backup
  `reccheck.py.pre893-20261021T070615Z`; imports, `tickparts` in HEAD_V9, sweep dry-run exit 0, no receipt
  failures.
- 07:07 lobby QC (build.ps1 -Pi; nobody online): qwprogs `96c0d288`, csprogs `391784ef`, all 12 restarted.
- 07:11 both installs, build.ps1 -Engine -Full from C:\FTESurf: exe `7128cc24`, fteqwsv64 `75723406`, hl2
  `4fc9c1d7`; QC as the lobbies.
- 07:15 lobby native: pi_swap893.py under the sweep lock, fleet empty, live pair patch-890; `8b940174` + hl2
  `91438f53`, all 12 restarted and read back (new exe, plugin mapped, UDP, stamp, pm_sourceversion 10,
  sv_tickparts 1, stable pids); protected trees unchanged; health ok.
- Lobby smoke (pi_lobby_smoke.py, 27510): PASS on the installed client and on the 0.1.28 release exe
  `ff0f0a2d` (csprogs `391784ef` served, board drawn, no QC error). Its lobby map had no zone-tool boxes, so
  the new client path ran offline instead (p892tool.cfg on the 0.1.28 exe), which found surf_reverie's
  mispredict -> P906.
- 07:49:51 P906 csprogs `b4de829b` to the 12 lobbies; 07:50 both installs. Smokes PASS on both clients.
- Later the same day ftesurf-39 deployed 0.1.29's natives to the installs (patch-900, which carries
  patch-893) and main's QC (with P906) to installs and lobbies.

## Rollback

Lobby native: for f in fteqw-svarm64 fteplug_hl2_arm64.so: cp <f>.pre893-20261021T071459Z <f>.rb && mv -f
<f>.rb <f>; restart every active unit. That is the patch-890 pair: never go below 890 (mover-10 files). The
P893 QC on the old native splits nothing (no reader of input_cmd_later). Pi reader:
reccheck.py.pre893-20261021T070615Z. QC: build.ps1 keeps the previous pair as .prev on the Pi and in each
install.
