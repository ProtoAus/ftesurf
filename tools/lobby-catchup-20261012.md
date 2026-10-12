# Lobby catch-up deployment — 2026-10-12

Requested: identify recent updates, deploy missing lobby-relevant updates, and
make them live. This is deployment/provenance, not a release or a new feature.
No patch number, Build number, engine pin or tag was changed.

## Frozen source and scope

- Product: `1f60e355ee3646e7e1e776a810c95c888cd8026e` (inspected origin/main).
- Native: `263d176862ccfd55fc3a82d5b65e20159d64a011` (`patch-679`, ENGINE.txt).
- Used clean detached worktrees, not the canonical engine checkout's different
  branch and uncommitted documentation. Those files and the owner's untracked
  config/reader backups were preserved.
- The fleet's previous CSQC was the P676 build; P677 labels/autohop ink had not
  been deployed there. The native server was also older than the current pin.
- Deployed the current pinned server and its matching Source map plugin, plus
  the current SSQC/CSQC pair. P678/P680 policies remain deliberately **inert**;
  this deployment does not activate a new prediction hook or reset policy.
- Backend runtime Python files already matched the frozen source. Its remaining
  differences were ancillary documentation/examples/tests, not missing runtime
  updates. No backend reload, database migration, nginx/unit edit or credential
  copy was needed. P681's default.cfg change was already live and was preserved.
- Both Windows installs' three VM files now match this clean build. Their native
  engine was already P679; it was not rebuilt or replaced for this deployment.
  menu.dat remains client-local and was not shipped to lobbies.

## Controls before swapping

- All three VMs built from clean source with `pwsh 7`, `build.ps1 -Jobs 8
  -NoDeploy`: **0 warnings** in each VM.
- P680 real dedicated subject: **71 checks, 0 failed**; P678 controls in the same
  session: **66 checks, 0 failed**. Deliberately weakened reset policy: the
  expected **2/71 failures** were detected, while P678 stayed 66/0.
- P677 labels: seven subject/control tests passed against the actual pre-P677
  lobby CSQC. Authored native/imported hop controls acted; inspected the label
  screenshot rather than relying only on marktrace text.
- P679 source-mount resolver: ten tests passed using the exact pinned fs.c.
- ARM server and hl2 plugin built from an archive of the exact native pin in an
  owned, non-web-served root. The shared p349build tree was not modified.
  Native build had the existing compiler/comment warnings; no native source
  repair or warning suppression was introduced.
- On **bhop_eazy and surf_ace**, all 19 normalized pm_dettest result lines per
  map matched the installed Windows P679 dedicated server, including srctrace.
  Aggregate result SHA256s:
  - bhop: `4c764f5b757040283fde29786a1309e923639240401ab3d96b9a30f37a02f2c2`
  - ace: `2a4f328c6a57700a2b33f833d2f702df42a898f285d053d18d33190e57eef2dc`
- The public p492voy recording, pin version 2, verified **PASS, ticks 4418 rows
  4418** on both platforms with its local zone table. A previously known-PASS
  fleet recording verified **PASS, ticks 3107 rows 3107** on the new ARM engine
  in an owned overlay. No historical verdict or player file was rewritten.
- Setup failures were not accepted as passes: missing isolated QC compiler,
  incorrect raw SVNREVISION argument, Python extraction API mismatch, a Linux
  manifest-directory argument, missing isolated hl2 plugin and missing zip were
  corrected only in the owned harness/build environment. zip was extracted from
  its package under the task root; no system package install was performed.
  `-NoDeploy -Pi` was rejected before copying progs; the final invocation was
  `build.ps1 -Jobs 8 -Pi` from the frozen clean worktree. Its output pair was
  byte-identical to the tested pair.

## Swapped and actually running

Native/plugin swapped at **2026-10-12T10:55:56Z**, with timestamped rollback
files. The standard Pi build procedure then uploaded and hash-checked both
progs, retained their `.prev`, and restarted all twelve fleet units.

| File | Deployed SHA256 |
| --- | --- |
| fteqw-svarm64 | `30af5da41b42aabf3dc26adb9940937934175001d644dc8904ae37c0842fb3b8` |
| fteplug_hl2_arm64.so | `babc07f9e2191cf081a96fd535321a13429b1b7484b8dd1ced04655e2c41c7f8` |
| qwprogs.dat | `cd5ecbdf7dd01db5369617e6087e4dc99e4a46b14708a786e421f02fcfc3f22a` |
| csprogs.dat | `d6b4d81e8c64261da04d4dca2da6d4efd2b5f6efb8a5688a96d9377b14560d7b` |
| Windows menu.dat | `d111ec13ee2827f4280742b75948b5ad96784b6dd6a6505136f7cb60d0f70752` |

Prior live native SHA256 was
`2c6d9b4e3a8532f76793a0a8c775d97d2edd8749e8213f0fd0f54ff2598091fe`;
prior plugin was
`b038a006e71316a8ebc3a91330f2796b39b9d7c277450e84e4bc84f7e1cb5b2a`.
Their rollback files remain in the live game directory as
`fteqw-svarm64.pre679-20261012T105556Z` and
`fteplug_hl2_arm64.so.pre679-20261012T105556Z`.

At **2026-10-12T10:58:29Z**, independent readback proved:

- All units ftesurf@1..12 active/running with fresh PIDs; every `/proc/PID/exe`
  hashes to the new native server, and each process maps the new hl2 plugin.
- All twelve actual UDP status sockets answer: 27510 through 27620, step 10.
  Fresh directory and socket observations showed all twelve empty before swap.
- Authenticated loopback queries, one cvar per request, read `sv_limittics 8`
  from every port; runtime `version` reports P679 on every port.
- Health says ok/12 lobbies, with a fresh directory row for every fleet port.
- Protected default/lobby-local/owner configs, addon list and installed list
  hashes were unchanged. Player runs/evidence/resume/saves/receipts aggregate
  file counts and content hashes were unchanged.

A fresh isolated client, with **no preseeded CSQC**, then joined 27510. It held
`downloads/csprogsvers/7ccff602.dat` with exactly the deployed CSQC hash, drew
board **cols 8/type 14**, reached its completion marker, captured an inspected
screenshot, and exited normally with **zero smoke failures / no QC errors**.
No terms were accepted or run submitted by the fixture. It disconnected normally.
At **11:01:33Z**, all twelve units' post-restart journals had zero fatal/VM/map
error markers; the directory again contained twelve empty lobbies, ages 1–4 s.

## Limits and workspace lifecycle

This proves deployment, native compatibility controls and an acted live client
smoke. It is not exhaustive human acceptance of every recent feature, a new
physics calibration, detector-policy change, or a new downloadable release.
Existing BACKLOG/lextest limitations remain.

Owner/session root: `C:\FTESurf-worktrees\lobby-live-01a12fa5\`.
ARM root: `/srv/nvme/agent-work/lobby-live-01a12fa5/`.
Only owned disposable worktrees/builds/overlays are retired; compact checks,
logs/screenshots and provenance are retained under those roots with OWNER.md.
Live rollback copies remain. No peer workspace or process was removed.
