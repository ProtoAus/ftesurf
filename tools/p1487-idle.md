# P1487 — vertical replay travel is not dead air

## Root cause and fix

`Watch_ScanRange` already parses all three recorded velocity components into `v`.
The separate idle expression rebuilt XY and forced Z to zero. Both upward and
downward ladder travel therefore qualified as stationary. Use `vlen(v)` instead.
The already existing speed/duration/padding gates and skip consumer are unchanged.
This applies to native/imported replay scans and range/stage/filter rebuilds;
no recorder, evidence reader, physics, pin/tag or QC Build change.

## Verification

Source base QC `206a4d94d06b0282932283e474b777e6905d454f` (product-identical to the
control `2dcc6041`), engine pin `b5c841c01`. Compiler: retained qualified
fteqcc64-p1412, SHA256 `73f9a1a471d603a8d0ee5a83432229ba2dd10affbf358ba41d345c8c15a94bd61`.
Three VMs built with `pwsh -NoProfile -Command './build.ps1 -NoDeploy -Jobs 8'`,
zero warnings. Latest QC LSP diagnostics unavailable (no QC server), not called
validation. Native control/subject use actual production progs and replay scanner,
not a Python copy of the classifier.

Synthetic FTESURF-REC9 presentation fixtures use continuous positions and these
velocities (u/s): horizontal100 at0..1.2, up100 at1.2..3.6, horizontal100 at3.6..4.8,
stationary4.8..7.2, horizontal100 at7.2..8.4, down100 at8.4..10.8,
horizontal100 at10.8..12, stationary12..14.4. No authenticity/physics claim.

| Sampling | Acting unchanged control | P1487 subject |
|---|---|---|
| 0.015s (961 samples) | 4 still stretches | 2 still stretches |
| 0.010s (1441 samples) | 4 still stretches | 2 still stretches |

Both genuine pauses exceed the0.5s gate and remain retained, including end-of-file
flush. Both vertical spans cease to be marked. Production logs show correct file,
sample count, FTESurf CSQC loaded and RUNLINES COMPLETE; no VM/unknown-command
errors. Both arms use idle_speed20/idle_time0.5/idle_pad0/skipfail0. Runtime
entrypoint is `tools/runlines_smoke.py`, with owned overlay, explicit SSQC/CSQC/MQC,
`--mount`, synthetic `--put data/p1487/...`, and
`--client-arg='+set vid_renderer headless -nosound +set vid_headless_sleep 0'`.
The cfg begins cfg_save_auto0/cl_idlefps0/cl_maxfps100, waits for startup, sets
log_name runlines_smoke, loads surf_dune and runs replay/status for both fixtures.

**Limit:** headless never runs CSQC_UpdateView/Watch_Frame. This checks the
production idle table, NOT actual rendered seeking, climb appearance or owner
acceptance. Tiny in-game check is pending in lextest.md. No extra optional GUI
campaign is needed before asking the owner.

Retained source/build/log/fixture evidence is under the owned task root
`C:/FTESurf-worktrees/storydemo-20261110-01a1c798`. An initial compiler/path
refusal, old compiler resource refusal, runner argv/fixture-path refusals and a
startup/renderer timeout were retained, not treated as product results. Correct
qualified compiler and documented runner contracts then acted. The production
builds and two successful arms above are the acceptance evidence.

## Story allocation report

The supplied exact count18446744071578836992 matches the earlier P1417 report,
not ordinary RAM exhaustion. `FS_LoadMallocGroupFile` narrowed a 64-bit file
length into signed int; P1417 rejects an unrepresentable length before allocation,
names the file, and fixes signed VPK entry sizes. P1421 adds sanitized console
tail retention and P1418 offers the crash report. Existing real control/guard
reproduction is recorded in engine ENGINE_PATCHES.md and tools/p1418-crash-reports.md.
Release0.1.42 shipped these fixes (tools/release042.md); current published0.1.44
inherits them. This task does NOT claim a newly reproduced fixed-build crash or
add a speculative second allocator fix. Need affected player's actual version
and, if0.1.42+, their crash record/file before attributing a recurrence.

## Delivery

Source `64d51b1d469cdeab81e8c78ad542cbb90337c716` and engine documentation
`455949d9e9fa51870afd7e4975fc4dccc0c4dc7e` are pushed to their main branches.
No native pin/tag, Build, release publication or backend change.

At2026-11-10T22:56:25Z, both `C:/FTESurf/ftesurf` and `C:/FTEQuake/ftesurf`
received only qualified csprogs.dat/lno using the existing build.ps1 Deploy
function. Exact CSQC SHA256:
`3b37b83162323135179509aeb46174498da6ad1b60001d8550a4f5d7675671fe`.
Both `.prev` images retain actual CSQC predecessor
`56522910e9b836012cdd3f09fee68789155022797eb0f021b28e7cf6e41dc6e8`.
The prior `.prev` images were separately archived.12 observed protected
native/menu/server/config hashes stayed exact; no owner's process was killed.

The unchanged build.ps1 -Pi block then uploaded/verified the qualified pair,
warned with the default10second countdown (no force), swapped with `.prev` and
restarted all12 lobbies. QW remains byte-identical
`fdce20d0ea73bad787fbdea4d3518de85adbc79110cd5120ce088eed23b88bb7`.
Postflight at2026-11-10T23:01:51Z proves fresh actors for all12, unchanged native,
backend actor epochs/configs and all214 recorder/resume payload/sidecar byte,
identity and captured metadata rows unchanged. Every preimage was captured and
all archive members individually rehashed on/off box BEFORE canonical staging
or restart; private preimages remain private. The first immediate postflight
met a startup status timeout; only read-only readiness/postflight was repeated,
not the swaps/restarts. A pre-swap JSON integer/string-key comparison refusal was
fixed in the observer without relaxing actor or data checks; original failure
is retained. Windows candidate-hash transcription refusal also preceded changes.

All12 full live serverinfo replies advertise the exact candidate folded-MD4
`0xc11262ee` and5304430bytes. The public1024byte status reply omitted the fields,
so the existing loopback hashed-RCON full-serverinfo reader was used once per
port, never logging credentials/full replies. Disk/live advertisement and native
scan proof are NOT cold-client download/rendered playback acceptance. The small
owner check remains pending; no speculative Story recurrence fix is claimed.
