# P1573 no injected clicks / no touchpads on the ranked board -- delivery (16 Nov 2026, ftesurf-31)

Lex, 16 Nov: "don't allow trackpads, no injected clicks please". Task root
C:\FTESurf-worktrees\acsteer-20261116-c5 (private fixtures under C:\FTESurf-private\worktrees\ same name).

## On main

806da8ba (5af889d4 patch, 40e5687a / a3cc3a17 / 3c0e8224 review rounds 1-3, records); engine ENGINE_PATCHES
Patch 1573 at ab9d849a0. QuakeC only; native tag unchanged.

## Verified

- Three VMs 0 warnings (fteqcc 1f2efd06). tools/p1573guard.py 8/8 on the installed client and on the 0.1.45
  release client; control (pre-patch progs) ranks both settings; `--latch` (private fixture) reads `clicks`
  where the round-1 and round-2 builds read on. test_reccheck 965/0.
- Reviews: predicate/flow and evidence/players on the first cut, then an integrity review of each fix. The
  remaining open case and the engine-side fix are in BACKLOG.

## Delivery, 15 Nov 2026 UTC (16 Nov local)

- Lobbies, ~19:58Z: `build.ps1 -Pi` from the worktree at 806da8ba, 12 rows and 0 players, warned, swapped,
  all 12 restarted. Live qwprogs `52f3c098`, csprogs `71f708cf` (.prev `9cd4a2ca` / `ed09b442`).
- Both installs: qwprogs `52f3c098`, csprogs `71f708cf`, menu `4561e872` (.prev = the 06:32 local rebuild of
  main, `61e46291` / `a0651dee`); csprogsvers `e6b6cf98` seeded in both. Same bytes as the tested build.
- `tools/pi_lobby_smoke.py` against 27510: PASS (served csprogs 71f708cf, board drew, no QC error); its fresh
  client printed both defaults-move lines from the lobby-served code.
- Comment-only trims after the deploy (no behaviour change, not redeployed).
