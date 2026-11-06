# P1351 — fresh pacing capture and unresolved Tensor2 work

6 Nov 2026 continuation of `frametime-smoothness-audit.md`. **No universal loading guarantee or measured final product performance improvement.** 0.1.41 was not rebuilt or republished.

## Sources, conditions and limits

Owned root: `C:/FTESurf-worktrees/ready-20261106T1706Z-01a1b1d2/`.
Native implementation matches engine `c28dcf9bd` / P1351; the measured pre-commit candidate was stamped `git-8481-patch-1350-3-g8302c314c-dirty`. The final clean native is separately stamped `git-8483-patch-1351-0-gc28dcf9bd`. Do not confuse the measured candidate binary cohort with the later deployed metadata-correct cohort. Candidate input hashes, source-bound receipts, build logs and raw captures are retained; the earlier binary was replaced by the final build, not retained as an immutable binary artifact. The reported timings therefore characterize that captured development candidate, not a final-byte qualification or a causal comparison against P1348/0.1.41.

- Real dedicated socket, Tensor2 replay r4729 (nominal475.410s), normal view,1920x1080, render scale1. Explicit `cl_idlefps 0`, measured `cl_maxfps 0`, `r_frametime_window 120`, `r_budget_csqc 0`, `pr_enable_profiling 0`, Christmas0, no diagnostic QC wrappers.
- Admission: at least4096MiB free and60s with no other game. Pre/post process censuses found only the owned client/server; both quit normally, rig lock released. Free memory while running at postflight was3374MiB; this is not proof of an isolated/constant-load host.
- Fresh application, starter seeds only: the owned smoke-generated GLSL history was hash-preserved then removed before launch. Owner/driver caches were not cleared. This is **not OS-cache-cold or driver-cache-cold**.
- The replay has no `.view` sidecar; native fallback angles apply. The small overlay also omitted authored zone files for Tensor2, so watcher energy falls back to jump samples. Native scene/replay inputs loaded, but this is not an exact owner HUD/zone fixture. Results are not a claim about every camera direction or exact owner view. The later Ceaseless boundary fixture separately copies its one shipped zone JSON; earlier Tensor2 evidence is not silently regraded.
- Each pass has seven60s windows and one55s window, paused/dumped/reset between windows. Exact retained raw samples, zero idle exclusions, no65536-frame eviction. Sampling covers475s/pass, but dump/command gaps advance replay time: last segment starts about431.7s, not420s; it can include the held end view. **Not uninterrupted475s moving-route coverage.** Do not pool per-window p99/tail means into an invented whole-route percentile.
- Initial reader requested p95, which the native dump does not expose; preserve that reader failure. It was corrected to the actual p90 field without rerunning the successful native capture.

## Exact raw-window results

Milliseconds; nearest-rank percentiles and slowest-fraction mean semantics are those of P1345's native dump. Printed precision is0.01ms. First-use and repeat are warm-state observations, not a product before/after experiment.

| Pass/window | Frames | Mean | p99 | 1% tail mean | 0.1% tail mean | Worst |
|---|---:|---:|---:|---:|---:|---:|
| first0 |20663|2.90|4.39|4.92|7.40|9.54|
| first1 |24953|2.40|3.89|4.37|6.09|8.13|
| first2 |19900|3.01|6.13|7.31|11.67|40.49|
| first3 |15793|3.80|7.78|8.75|12.15|34.64|
| first4 |19741|3.04|4.99|5.85|8.49|23.66|
| first5 |21439|2.80|3.94|4.50|7.10|13.14|
| first6 |20330|2.95|5.68|6.46|8.25|9.99|
| first7 (55s) |24594|2.24|4.10|4.86|7.10|10.27|
| repeat0 |20682|2.90|4.42|4.95|7.33|11.52|
| repeat1 |24602|2.44|4.14|4.63|6.23|8.02|
| repeat2 |23026|2.61|3.76|4.20|6.07|7.74|
| repeat3 |21060|2.85|4.68|5.14|7.22|10.68|
| repeat4 |19581|3.06|6.22|7.01|8.89|11.31|
| repeat5 |15905|3.77|7.40|8.19|10.44|14.43|
| repeat6 |17310|3.47|6.89|7.62|9.19|10.65|
| repeat7 (55s) |18799|2.93|6.53|7.40|9.31|11.71|

Sample-weighted summaries (from summed sample time/count, not averaged FPS):

- First:167413frames /475.002sampled seconds =352.45fps,2.837ms mean; worst40.49ms.
- Repeat:160965frames /474.995sampled seconds =338.88fps,2.951ms mean; worst14.43ms.
- Repeat was **not consistently faster**. Different first/repeat windows regress in ordinary throughput despite lower large first-use spikes. No final numerical improvement is established; no before/after P1351 benefit or all-route acceptance is inferred.

## What the new late-work diagnostics reveal

The app's activation snapshot compiled47 known permutations, no pending/failed shader permutations, but648 registered file-image attempts included207 failures. The snapshot correctly stayed **incomplete**. These include optional probes; missing visible materials are not established by the count. A normal reconnect control inventoried460images/8failed attempts and also remained incomplete.

Before route capture,21 late compiles had accumulated5.508ms. By the end of first traversal:32 /114.011ms, so **11 additional compiles /108.503ms** occurred after the initial diagnostic check. The repeat added none. Late image completions went48->49 (one successful completion,0.062ms); the33 failed late lookups were already present before route capture.

Counter deltas between adjacent end-of-window reads (the pause/dump gap is included):

| First-use window | Compile work between reads | Last program family | Worst raw frame |
|---|---:|---|---:|
|2|1 /37.755ms|lightmapped + MIPFADE|40.49ms|
|3|1 /30.111ms|water + HQWATER/depth/fog|34.64ms|
|4|1 /20.345ms|lightmapped environment-mask variant|23.66ms|

Window2's spike breadcrumb recorded40.525ms total /40.489ms gfx with negligible worker/input/protocol time. The compile delta is consistent with that first-use hitch, but counters are between-read aggregates (including dump gaps), **not an exact per-frame causal join**. Do not label all gfx time a shader compile or all remaining cost a resource-readiness problem.

This positively falsifies a universal readiness interpretation: late material/program registration or unsupported/unremembered permutations remain outside the activation closure. Expanding the actual finite material/fallback/route dependency closure is still needed before strict timer/start admission. Simply increasing the wait budget does not discover resources that have not been registered.

## Tensor2 sky-query attribution

A diagnostic-only QC build is prepared with separate `Sprite_DiagEyeTrace`, `Sprite_DiagRoomTrace` and `Sprite_DiagPrefix` wrappers around the existing work. Exact trace flags, globals, query cadence and camera/cache rules remain unchanged. Its patch/build receipt live under the owned root; original product QC is restored and no diagnostic wrapper is deployed. Native VM profiling must be kept separate from the unprofiled frame results above. Profile operation counts are not calls; wrapper self time includes its QC-call overhead.

Source path: `Sprite_SkyTest` -> native `PF_cs_traceline` (`pr_csqc.c:3188`) -> `World_Move` (`world.c:2777`) plus `cs_settracevars`. `World_Move` traces world and local links, then the CSQC packet-entity brush path (`World_ClipToNetwork`,2522). `MOVE_NOMONSTERS` is **not world-only**; replacing it with world-only would remove brush/door semantics. Even isolated traceline-wrapper time includes trace-result marshalling, not just BSP traversal.

The gate initially refused headroom below4096MiB, then admitted after memory recovered and60s quiet. Final clean P1351 native plus diagnostic-only QC produced a positive ordinary-route profile; pre/post snapshots found only the owned actors, both quit, rig released. Continuous unrelated host activity is not proven absent. Profiling was enabled for roughly8s before the snapshot. The dump took additional time to print, but `qclib/initlib.c:1757-1823` copies/reset counters into a separate sorted table before printing: that later print duration is not part of these copied values.

| Function | Self seconds | Inclusive seconds |
|---|---:|---:|
| Sprite_DiagEyeTrace |2.637655|2.637655|
| Sprite_DiagPrefix |0.046053|0.046053|
| Sprite_SkyTest |0.026653|2.710361|
| Sprite_SkyTick |0.056533|2.766894|
| CSQC_UpdateView |0.052144|5.674022|

The eye-traceline/trace-output bridge is **97.3% of SkyTest inclusive time**;
QC lowercase/prefix work is1.7%, remaining SkyTest body1.0%. SkyTick inclusive
is48.8% of UpdateView inclusive in THIS instrumented snapshot. No room-trace row
acted, so skyroom attribution is untested. These are aggregate VM-profile
seconds/ratios, not calls, unprofiled milliseconds per frame or FPS. Wrapper
entry overhead and native trace-result marshalling are included; native BSP
traversal versus packet-entity scans versus `cs_settracevars` are not separated.

This narrows the outstanding optimization target to the native trace/bridge,
not another QC prefix rewrite. Next falsifier: instrument native `World_Move`
versus `cs_settracevars`, then world/brush traversal separately, with unchanged
traces and positive moving-door/ordinary-visibility witnesses. Any proposed exact
query reduction still needs an unprofiled matched repeat control; no smaller ray
budget, weaker invalidation or missing-submission silence. No substantive exact
query reduction or measured final performance improvement is established.

## Fresh normal-QC Ceaseless boundary capture

Exact final/deployed P1351 native hash cohort, restored normal QC (no profiler/
wrapper), same1920x1080/uncapped settings. Initial fixture control refused before
measurement because the small overlay omitted its shipped start-zone JSON. The
failure/logs are retained as `native-boundary/failed-missing-zone-*`; the reusable
preparation seam was corrected to copy ONLY that one unchanged canonical zone
file. No zone/player data was edited. The same harness then positively warped
with `cmd zone_goto`, enabled noclip and swept vertically out/back twice.

`cl_upspeed 10000`,4s key-down plus0.2s endpoint/report settling per window. These
are synthetic4.2s slices, not exact single-transition latency or a matched
P1348-versus-P1351 product comparison. Both endpoint predicates acted:

- Out: active1/predicate1/cluster-1,4158world meshes, shape`ac51cd15` on both
  crossings; view z19833.025/19815.713, pitch89.
- Back in: active0/predicate0/cluster399,164meshes, shape`2699c989` both times;
  z15676.609/15657.063. Last inside screenshot retained1920x1080 with map drawn.
- Pre/post snapshots found only the owned actors. Other-session launches reset
  earlier quiet admission; they were not killed. No idle exclusions/capacity
  eviction; owned actors quit and rig released. No continuous-host-isolation
  claim or manual-acceptance substitution.

| Slice | Frames | Sampled s | Mean ms | p99 ms | 1% tail mean ms | Worst ms |
|---|---:|---:|---:|---:|---:|---:|
| first out |956|4.202|4.40|8.05|12.81|29.65|
| first back |1116|4.206|3.77|8.10|8.45|9.03|
| repeat out |1016|4.214|4.15|7.82|8.26|8.76|
| repeat back |1147|4.195|3.66|7.91|8.09|8.43|

Pre-warp diagnostic:4late compiles/0.910ms; by first-out end:7/59.196ms, unchanged
through the other three slices. Thus three new compiles/58.286ms occurred
somewhere between the pre-warp check, warp/lookdown preparation and first-out
end, **not proven all inside the measured4.2s**. First-use work still exists;
these slices do not establish a final improvement or the owner's perceived
first-pause reduction.

## Delivery and pending acceptance

Engine c28dcf9bd/tagpatch-1351 and QC0de32b5b are committed/pushed. Clean supported full native/three-QC build passed;32 readiness controls,442 frame controls and550 exact dump controls pass. Native full-build warning comparison:46 distinct pre-existing types on control/subject, zero novel types; changed implementation has no compiler warning.

At **2026-11-06T18:09:25Z**,10 native targets across BOTH Windows installs and each `.prev` hash-verified through the existing build helper's native target list. Both installed clients execute `--version` and return the expected clean1351 stamp. Owner configs and all existing QC/symbol files were hash-preserved. No lobby/backend/config/data or release publication was needed for this client-native-only change. Final native graphical/socket execution and separate Tensor2 attribution passed on the exact deployed-native hash cohort (diagnostic QC only for attribution). Fresh normal-QC void-boundary capture also passed its acting predicate/geometry controls as above; no owner confirmation has been received.

Human-only check remains in `lextest.md`: on Ceaseless, noclip out/back twice, compare first pause/repeats, map readability and restored normal lighting/props/glows/weather. Logs/predicates/timing are not that confirmation.
