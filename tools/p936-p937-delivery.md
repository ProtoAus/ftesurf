# P936 portraits / P937 local instruments — development delivery

Verified live22Oct2026 23:18:56 UTC. This is ordinary development delivery,
not a release/Build bump, human acceptance or a producer-family promotion.

## Exact source and destinations

- Public implementation: QC69b7e2a8 (including7ae7a80e), P9369b31c300;
  engine native5fd6c6790, tagpatch-937; later engine changes are documentation.
- Actual fleet QC: published compatible50e7d8f32a102b9ba4f57cd308aa8c41a91eb6f2,
  based49a1078a with ONLY portrait/audio/metadata/fixture hunks. REC13 retained.
- Actual backend: published compatible3f97cf9cbdc3a1a8e915916c328e2b9b6fd557ec,
  based servingcc0b7ffa. Schema20 unchanged. Sealed delta is steam.py,
  steamsync.py, surfd.py AND test_ranked.py; guards/witness policy/routes unchanged.
- Native client SHA256
  d44153264af9b57599af66828db9d217fa84694abf88f3c11d18284d10f84a7e
  in BOTH C:/FTESurf/ftesurf64.exe and C:/FTEQuake/fteqw64.exe.
  Both have git-7722-patch-937-0-g5fd6c6790. Previous images retained; no owner
  process stopped/restarted. Lobby native/HL2/plugin/producer NOT upgraded.
- Program SHA256 (matching both Windows installs; qw/cs also Pi):
  qwprogs.dat 9e0bde1c93ecd49f332363ff217b24c11eb2b668f26e26876e9968958a692a90
  csprogs.dat fb93200da1f242362c4f95fbaba1f327bb62cf2e0567c5a81a6baccbc4cd8439
  menu.dat b87d5321efd7e7bb397b8b69f2232912eefc1c8b89124411f31db8f4bace72a5
  Menu is Windows-only, never a lobby. Pi .prev pair retained.

## Validation and live readback

- All3VMs0 warnings. Full native0 NEW warnings: exactly74 unchanged from full
  P934 baseline. Independent input review OK; lifecycle P1/P2 accepted, fixed
  and explicitly closed after follow-up. Callback C unit acts4096 old/new cycles;
  subject balances allocations/frees. No concurrency/RSS/latency/performance claim.
- Compatible real dedicated/native audio fixture passes13 controls including
  actual A/D/hold/release/chat, same-body height/pitch, native queue activity,
  volume0, ACTIVE exact-one fade and3 repeated drain/restarts. Only owned actor
  muted; no run/consent files; actors stopped and verified junctions unlinked.
- Compatible ranked/API suite and entire archived backend suite pass. Matching
  compatible64px transport/game/menu upload and screenshot quadrants (inspected)
  pass before/after renderer reload. Original32px/no-picture controls retained.
- Backend promoted FIRST through unchanged guarded successor. Fresh worker,
  receipt/master process identity,7stubs/run,4cron routes and Mom watcher on the
  new admission inode verified. New admission OPEN; predecessor CLOSED/drained.
  Public health/board200;12lobbies present/empty at transaction/readback.
- `build.ps1 -Pi -Jobs 8` from CLEAN compatible source compiled, hash-checked and
  restarted all12empty lobbies. Worktree output is NOT C:/FTESurf: it copied only
  the secondary install, so the primary's six generated products were explicitly
  copied from the same clean build after preserving predecessors. Final3progs
  and native hashes verified in BOTH Windows installs. No owner/peer cfg copied;
  CSQC self-registers the audio defaults.
- A fresh owned cold-cache client connected to a real live lobby, downloaded the
  exact csprogs hash above and ACTED both replay and NEW motionaudio diagnostics.
  No account acceptance/link/ranking action. Actor stopped, links removed.
- Private before/after snapshot: all607configs unchanged; all27908pre-existing
  data entries retained with identical size/mtime/mode,12new; all12actual native
  executable + mapped HL2 cohorts unchanged. This is metadata preservation,
  NOT a full-content hash of all player recordings. Private inventories stay Pi-only.

## Failures/limits retained, not counted as passes

Initial compatibility portrait attempt loaded the old32px backend from the QC
checkout; it correctly failed. Existing fixture rerun from matching backend
checkout passes, no weakened assertion or new wrapper. Preflight rejected a
stale88 operator copy, then an incomplete expected delta (tests are sealed too).
Compared actual working predecessor's published7548 tools and complete Git/
witness delta, corrected inputs, reran unchanged preflight successfully. No live
maintenance gate was closed during preparation/debugging. A guessed full88 SHA
in a diagnostic refused before mutation. Unsupported -DeployDir refused before
compile/copy (the preceding primary-backup preparation had occurred).
Native incremental revision stamps required supported Full rebuild. See notes.

Owner-only checks remain PENDING in lextest.md: real portrait appearance and
musical pitch/volume/A-D timing. Queue/counter/pixel checks are not ear/feel,
measured performance or manual acceptance. Restart for the new native client;
reconnect for new CSQC. `cl_surf_tone 1`, `cl_surf_drums 1`; both0 to stop.

Evidence is retained in the owned requests-20261022T1646Z Windows/Pi roots:
p937-deployment/windows-p937/p937-live-cold results, compatible audio/picture
stdout/screenshots, immutable generation's full suite/build/cutover/postflight,
and private p937preservation snapshot. Serving runtime/control/state/operator
must stay; old generation retained for rollback. No private raw output exported.
