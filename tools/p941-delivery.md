# P941 development delivery — verified 23Oct2026 06:39UTC

Four presentation/audio corrections are implemented, published and available.
Viewmodel LIGHTING parity remains an open matched-reference question, not a fix
or human acceptance. No release or Build-number decision was made.

## Inspected source and build

- QC feature:4682406d3c900605f4979cc45bd9efeb4008ae0e, published main.
- Engine ledger:eac4661f81665a7fbe404fc78c5f660c3f54b6ba, documentation only.
- Concurrent published P942 backend work retained; no backend deployment here.
- Native pin/tag939 retained. No executable/plugin rebuild or replacement.
- Clean feature commit rebuilt with three VMs0warnings and reproduced ALL three
  tested DAT hashes exactly. Only QW/CSQC DAT/LNO are promoted; MENU is protected.
- Feature/socket controls, failed arms and lighting limits: tools/p941-source-polish.md.

## Windows — 2026-10-23T06:36:04.1446454Z

Eight QW/CSQC DAT+matching LNO files installed in BOTH C:/FTESurf and C:/FTEQuake.
Existing guarded promoter was minimally extended with a gameplay-progs-only mode
and independent QW predecessor check. An acted wrong-QW control refused BEFORE
creating a transaction. Actual promotion required the exact QW/CSQC predecessor
hashes, staged/checked all eight files, preserved old .prev generations, checked
new destination hashes and refreshed .prev to this transaction's predecessor.

Before/after protection proves native executables, five plugins, MENU DAT/LNO,
configs and install metadata unchanged. No owner process was stopped; no owner
config or player data was edited. Exact receipts remain in the owned artifacts/
p941-windows-deployment.json and p941-windows-deploy.log.

SHA256:
- QW old:a4fb3f183478a460abc98dd1192ef6d2562cb93a873c91990a99890c0ff71f07
- QW new:c37d568a9de6463838d57e1d0f56605d2118147dfb238da56227abe9485d6338
- CSQC old:aa961fddd4fd74a58921595bb60e88b360e61dadeeb244f6c9da976942bb518b
- CSQC new:5b1500f1ca021514889998d8b1de6ee52640665c0bf40249be45c2a243d31242

## Pi lobbies — readback 2026-10-23T06:38:03Z

Fresh directory held every required lobby row, all0players. Exact live old pair
above and absence of either .new file were checked. Prior .prev generation was
copied/compared to a unique pre941 timestamped backup before ordinary promotion.
A first READ-ONLY path guess pointed at a nonexistent directory and failed; no
swap/restart occurred. Correct PiGame was read from the existing entrypoint.

From clean qc/src, using pwsh7 and the existing supported entrypoint:

    ./build.ps1 -Jobs 8 -FteRoot <owned-engine> -QuakeDir <same-qc-root> -Pi

No -Engine, -PiForce or -NoDeploy. Self-sink prevented extra Windows/MENU writes.
All three VMs0warnings, exact tested DAT hashes, built-in all12empty-row gate,
verified upload, ordinary .prev swap and all12restarts succeeded. Readback proves
live hashes equal the new pair above, .prev equals the old pair,12units active.
No config/tool/native/backend/consent/collection change was shipped.

A fresh real pi_lobby_smoke client with NO local CSQC joined27510. Downloaded
`downloads/csprogsvers/caf6dfa0.dat` has the exact new CSQC hash. Actual drawn
board9columns/type14, normal client exit0, no QC error, screenshot inspected:
0failures. This proves served code, not merely files present on the Pi.

## Acceptance, limits and retention

Native real-socket controls prove spawn0 -> equip1 -> respawn0 -> equip1, continued
idle after18.8297s, subtler nonzero model motion and real Axiom CSS metal samples.
Quiet walk and cached metadata controls are detailed separately. They are not
owner visual/ear acceptance, full movement/evidence qualification or FPS claims.

Lighting is NOT claimed fixed. The supplied CSS/Momentum BSP builds differ; an
owned exact-CSS-map control was stopped and its single map fixture hash-checked/
removed. Owner CSS getpos was requested for a matched BSP/camera/idle comparison.
BACKLOG.md and lextest.md retain this open case and small human acceptance check.

All owned clients/servers exited; no maintenance gate remains. Needed immutable
source/builds, native cohort, screenshots, downloaded code, failed-control history
and rollback receipts are retained under
C:/FTESurf-worktrees/source-polish-20261022T0746Z, explicitly for the pending
lighting comparison and reproducibility. No unexplained scratch root or new Pi
build clone was created, and no peer/player-data cleanup was attempted.
