# P682 development deployment — 2026-10-12

## Product, reviews and exact-build provenance

- Product: `0a66924dd0f250d48cb417dcb1f048e9e035f2b6` (P682 feature + rate fix).
- Engine ledger: `7ce9d666073851a49dd50bb3cf189bddd4b88a5a`; documentation only.
- Reviewed candidate `093b3909441ca81b08fbab343ed40dd49d8471d7` remains preserved.
  The push guard caught concurrently published release tooling `196a628`; both
  P682 commits were integrated in a separate clean worktree. All QC/fixture
  inputs and all three program outputs match the reviewed/tested candidate.
  No published history was rewritten and no peer uncommitted files were shipped.
- Independent selection/bounds/effect-free and recorder/go reviews complete.
  The original one-token P1 was fixed, falsified by the old-rate mutant and
  accepted in bounded fix re-review. Provider/revival failures were reported;
  authorized retry used the same native reviewer role/model, not another CLI or
  provider. Reviews inspected source and retained acting evidence, not new runs.
- Retained real recorder/pin/write/read/load/hold/release subject **98/0**;
  independent rate **4/98**, spatial **7/98**, held **2/98** named expected
  failures; grader **16/0**. Earlier reader and unchanged load/reset evidence
  remain observations from their recorded runs, not rerun review evidence.
- Exact-commit and integrated-commit production builds via pwsh7
  `src/build.ps1 -Jobs 8 -NoDeploy`: all three VMs, zero warnings, byte-identical
  to retained tested programs. Final normal `build.ps1 -Jobs 8 -Pi` also had
  zero warnings and byte-identical output. No native rebuild or release.

## Reversible swap and destination verification

The normal Pi guard saw a fresh row for each of twelve active lobbies, all
empty; a preceding independent UDP socket probe also proved each empty. No
`-PiForce`. The documented build procedure staged/hash-checked both progs,
renamed the pair while retaining `.prev`, and restarted every active unit.
The worktree's SurfDir is not the canonical install: verified staging files
were then explicitly deployed to **both** `C:/FTESurf/ftesurf` and
`C:/FTEQuake/ftesurf`, retaining each file's immediate predecessor as `.prev`.
menu.dat stayed Windows-local, never sent to lobbies.

| Program | Deployed SHA256 |
| --- | --- |
| qwprogs.dat | `424afeebea4f25c33ffd0d0d4c7d46b3520294cf9cb21ee5079414a8b6524205` |
| csprogs.dat | `3e33342c3296afde1bece3f581830665ebb153535b2dd68108a882365ce4e669` |
| Windows menu.dat | `f13f792cb416ff0752ce51c1ac2cd0520e462a0f9a7c314b18caae2492e407c1` |

Destination hashes and rollback predecessor hashes were independently checked.
Prior fleet/Windows SSQC was `cd5ecbdf7dd01db5369617e6087e4dc99e4a46b14708a786e421f02fcfc3f22a`;
prior CSQC `d6b4d81e8c64261da04d4dca2da6d4efd2b5f6efb8a5688a96d9377b14560d7b`;
prior Windows menu `d111ec13ee2827f4280742b75948b5ad96784b6dd6a6505136f7cb60d0f70752`.
CSQC/menu differed from those installed predecessors at just byte `0x73`, in
fteqcc's compile-date header; no client/menu behavior changed in P682. SSQC
contains the reviewed server selector/preparer changes.

At **2026-10-12T17:02:36Z**, independent fleet readback established:

- Twelve active/running units, each with a fresh PID and an acted UDP status
  socket, ports 27510..27620 at ten-port intervals, all empty.
- Every running executable still hashes to the installed P679 native server;
  the matching Source plugin remains mapped, not replaced/deleted.
- One-command-at-a-time loopback authenticated reads: `sv_limittics 8` and
  unchanged P679 native version on every port. Credentials read internally,
  never printed or passed on a command line.
- Destination progs are the expected build and `.prev` is the captured
  predecessor. Protected native/config/addon/installed-list hashes and mtimes,
  plus aggregate runs/evidence/resume/saves/receipts content observations,
  are unchanged across the swap/restarts.
- Health OK with twelve lobbies and complete fresh directory rows.
- Both Windows installs independently hash-match all three programs; protected
  native/plugin/owner/default config hash+mtime guards are unchanged. No owner
  game was stopped; already-running local sessions need map reload/restart.

## Acting served-program smoke and limits

Two isolated fresh clients, one using each Windows install's actual engine and
menu, joined lobby 27510 without preseeded CSQC. Each downloaded
`downloads/csprogsvers/6dbf6df8.dat` with the exact deployed CSQC hash, drew
**board cols 8/type 14**, reached its completion marker and exited normally;
both had **zero smoke failures / no client QC errors**. Both screenshots were
inspected. No terms accepted or run submitted. Bright known missing-map material
remains behind the successfully drawn board; this is not a map-content repair.
At **17:06:55Z**, the directory was again twelve empty lobbies, ages 0..4 seconds.

Post-restart journal visibility is unavailable to the SSH account: that probe
was refused as a gate, not counted as a clean server journal. Live socket/PID/
version, program hashes and client smoke are the actual accepted integration
observations. No permission/unit change was made to obtain journal access.

The preparer remains **inert**. Fleet/client smoke proves served-program
integration, not a production READY call, native snapshot application,
admission/prediction/baseline reconciliation, future persistence or asynchronous
copy-failure parity. The retained dedicated actor is the acting body-policy
proof. Existing BACKLOG/lextest and contract limits still apply. Native pin/tag,
QC Build 89, evidence format, ranking/defaults and backend runtime are unchanged.

Evidence/checkpoint/ownership: `C:/FTESurf-worktrees/rewindprep-20261012-1352/`.
Only owned, verified disposable copies are retired; history, compact logs,
screenshots, exact program staging and recovery manifests are retained there.
