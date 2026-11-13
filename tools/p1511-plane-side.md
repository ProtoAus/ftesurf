# P1511 — conservative ambiguous plane-side early exit

## Status

Native source published: feature `e087aac60`, integrated inspected engine
`24a3d0104ea58d34ab1b30443ecaa580f8eed06c`, tag `patch-1511`.
**Delivered to BOTH Windows native clients12Nov00:04:26UTC**; independent
readback00:05:04UTC. No native server/plugin/VM/Pi rollout.
Exact-helper CPU controls, independent source/oracle review and controlled
working-tree native builds pass.
Real renderer/replay functional checks pass and paused views were inspected.
An earlier exact-pixel claim was false: the RGBA difference reader checked the
alpha channel only; corrected direct bytes differ. Final clean-tag Full and
final-image functional compatibility and dual-client delivery pass. Wider/owner
visual acceptance and FPS measurements remain pending. This is part of the
worst-map lows continuation, not a claim that its remaining work is complete.

## Problem and change

`GLBE_BlendPlaneSide` scans all vertices to prove one mesh lies strictly on one
side of another admitted plane. Once its running minimum is at most `+2EPS` and
maximum at least `-2EPS`, neither strict result can be restored: further vertices
can only decrease the minimum or increase the maximum. Return unknown then.

The three added C lines do not change epsilon, eye-sign mapping, geometry
admission, face/material order, graph construction, memo keys, clipping or work
budgets. Callers still charge the complete original mesh-vertex counts. This
optimization does not buy extra pairs or extend a frame's sort budget.

## Pre-registered falsifiers and acting controls

- The unmodified full-scan helper must agree with the independently frozen
  reference in both ordinary and fast-math builds, but FAIL the actual work
  reduction assertion on the ambiguous 64-vertex fixture.
- The candidate must retain every helper result and make that same reduction
  assertion pass. A semantic difference, compile warning, missing arm, or no
  actual reduction rejects the candidate.
- Runtime/FPS acceptance cannot be inferred from the extracted helper.

Both source-bound variants use C99, `-O2 -Wall -Wextra -Werror`, with the second
also using `-ffast-math`. Each executes 1,312 finite helper cases against the
frozen full scan: negative/unknown/positive counts are **375 / 562 / 375**.

| Source | Ordinary | Fast math | Actual ambiguous-fixture visits |
|---|---|---|---|
| Unmodified helper | All results equal; intended work assertion fails | Same | 64 candidate / 64 frozen |
| Candidate | All results equal; exit 0 | Same | 2 candidate / 64 frozen |

The reduction is demonstrated for that fixture, not a general 32x CPU speedup
or an FPS measurement. The fixture starts at sides `-1,+1`; its second vertex
makes both strict proofs impossible. The parent's exact-one-visit prediction
was false and is retained as such. No arm was repeated to repair that reader.

Independent review found no native or default-oracle blocker. Zero vertices
still return unknown by source reasoning; production admission requires at
least three. Arbitrary nonfinite helper calls under fast math, floating-point
exception state, and invalid memory are not qualified by this finite corpus.

## Reproduction and retained limits

Use the existing test entrypoint from the engine checkout, with a uniquely owned
output directory:

```
python -B tools/test_gl_blend_planes.py --side-only --cc gcc --output <owned-output>
```

On this Windows UCRT toolchain, the compiler's bin directory must be in `PATH`
for its child tools, not merely passed as an absolute gcc executable. The first
empty-diagnostic compiler refusal is retained. The same generated C fails with
the inherited environment and compiles after that actual PATH correction.
Subsequent parent-reader wording/count mistakes were corrected from retained
normal/fast logs, without rerunning those arms.

`--side-only` explicitly does not qualify the complete memo/geometry suite.
The default legacy test still stops at its stale three-argument sort-call
source assertion while production uses four arguments. That coverage gap is
tracked in `BACKLOG.md`; its oracle was not suppressed or converted to a pass.
The separately reported historical cycle-fixture problem is not reproduced or
resolved by these retained runs.

LSP currently reports a missing `quakedef.h` through fallback configuration;
that is not a clean translation-unit diagnostic. The actual supported native
builds below provide compiler evidence independently of that fallback.

## Controlled native builds

The current source retains published P1508 snapshot behavior. Its exact qualified
artifact dependency/flag closure was unavailable, so a controlled **Full baseline**
and then **C-only incremental candidate** were built with the same inspected
source headers, compiler, flags, stamp and one owned JPEG9c dependency snapshot.
Both used `build.ps1 -Engine -NoDeploy -FteRoot <own-engine> -Jobs 2 -PassThru`;
the baseline also used `-Full`. Snapshot source/destination bytes and original
source-before/after inventories matched. No writes into the retained input tree.

Both supported builds exit0; each builds all three VMs with zero warnings.
Only `gl_backend.o` changes. Baseline has74actual native warning diagnostics;
candidate has3, exactly the affected-compilation baseline multiset: **zero new
warning payloads**, not a claimed whole-build warning reduction. Same controlled
client stamp in both: `git-8699-patch-1508-4-gddabb7475-dirty`. The inspected later
P1512 engine commit changes documentation only and does not invalidate this C
or header control. All seven native images per arm are frozen under the owned
task root's `artifacts/native-side-{baseline,candidate}/` with source/inputs,
object, warning and PE-section comparison evidence. Server/HL2 relink differences
were recorded, not called byte-identical. Runtime comparison must hold a common
server/plugin set fixed and change only the client.

Builds ran in explicitly owner-approved non-timing tandem beside two minimal
peer games, Jobs2 and the supported memory floor. No FPS/runtime acceptance is
inferred. Generated HL2 header verification first refused a raw LF/CRLF mismatch;
a bounded whole-file comparison against exact original checkout CRLF plus the
single generator-path comment proved the sole difference. The raw generated
header/refusal were preserved and original checkout bytes restored. No baseline
build was repeated. Those working-tree controls alone did not qualify a clean
release image or installation; the subsequently completed clean Full, final-image
runtime and destination readbacks are recorded below. No recorder, evidence,
movement, protocol or QC Build change.

## Final clean-tag Full qualification

ONE fresh supported Full build from exact `24a3d0104`/`patch-1511` completed at
**2026-11-11 23:45:03 UTC**, exit0, using the same supported Jobs2/NoDeploy seam.
Client SHA256 **532842eaf16c832c54a1debd8fae17116aa755265d759d12ae5c2a715774f32a**,
9,016,570bytes, clean stamp **git-8704-patch-1511-0-g24a3d0104**. Fresh native
objects/dependency records prove the new tree and qualified headers were consumed;
no old dirty-stamp object reuse. Full74warning payloads match the prior Full
multiset, **zero new or removed**; all three generated QC VMs report0warnings.
The existing TLS checker acted on365fresh objects/10TLS symbols: **zero plain
address uses**, exit0. None of those generated server/plugin/VM images is a ship
set for this client-only change.

Owned dependency snapshot bytes/file metadata/topology match before/after; the
external Box3D archive was independently hashed both before and after this time.
Generated HL2 header differs only in ONE literal script-derived mixed-slash path
in its generator comment. Whole-file equality with that exact substitution was
proved, raw generated bytes/refusal retained, original checkout bytes restored
once; source/header hashes and clean HEAD/tag verified. The initial descendant
count reader omitted the historical root-dot entry, and the first path reader
missed the actual mixed spelling. Both refusals remain; neither caused a build
retry or a generic normalization. No timing acceptance is inferred from this
owner-authorized tandem compilation. Actual image/source hashes and detailed
receipt remain retained under the owned task root.

## Functional runtime and bounded visual check

Both controlled clients used the same frozen baseline dedicated/HL2 plugin,
P1507 CS bytes, map/replay assets and settings. Fairy33811 actually advanced
from0 through39seconds in both arms, then paused at15seconds. Main-view alpha
trace proves view eligibility, admitted commands, edges/work and plane/memo
paths acted. No assertion/VM fatal was found in successful-arm logs. This does
not prove the shortcut's exact hit count in gameplay; the extracted C work
control is separate evidence.

The matched1280x720 screenshots were inspected, but **are NOT pixel-identical**.
The first reader used `ImageChops.difference(RGBA, RGBA).getbbox()`, whose alpha-only
behavior hid RGB differences. Corrected direct RGBA byte equality and RGB bounding
boxes disprove that result. Both the false reader output and correction are
retained; no gameplay arm was repeated. Earlier exact-pixel wording is retracted,
not a pass that survived this correction. Render smoke and finite helper-result
agreement remain separate valid evidence; broader/owner visual equivalence is
pending. Screenshots/clock gates/input hashes/raw logs remain under the owned root.

The first local bridge boot refused its spectator argument: the actual server
reported spectator connected while the unchanged helper requires client connected.
The successful own unranked loopback arms used spectator0; the original refusal
was retained, not called a product failure or repaired by weakening the helper.
The owned CS/cache and helper-managed config were exactly restored; only registered
own clients/server stopped. No shared clipboard was touched in these arms.
Peer presence changed from two games to none, so these functional arms are
explicitly not FPS evidence. A separate150second normal quiet-gate attempt
subsequently found two foreign games and the shared lock; it acquired no lease
and ran no timing arms. There is **no measured native FPS improvement**. Do not
turn the local64-to2work fixture into a gameplay percentage or general speedup.
Development delivery is based on bounded semantic/work, compiler and render
qualification; numerical/owner feel acceptance remains explicit and pending.
The subsequently completed clean-tag Full and destination checks are recorded below.

## Delivery

Final clean-tag Full qualification and actual final-image runtime pass. The clean
image advanced Fairy33811 to39.0247s then paused15s with installed P1508
server/plugin copies and unchanged own frozen VMs. Actual main-view alpha-sort
admitted commands/edges/work and CSQC loaded; no captured assertion/VM fatal.
This is not current peer P1512 VM, ranked/evidence or owner acceptance.

**One** independently reviewed native-client-only transaction completed at
**2026-11-12 00:04:26 UTC**, with independent destination readback00:05:04UTC:

- `C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe` both exactly match
  final image SHA256 **532842eaf16c832c54a1debd8fae17116aa755265d759d12ae5c2a715774f32a**,
  positive clean stamp **git-8704-patch-1511-0-g24a3d0104**; original file modes
  restored, staged temporary files absent.
- Both live predecessors were exact published P1508 client
  **4b6c6cf817d170a30179fbd8765bc29034f5333ebce5692b89ca7c5e411d9bf2**.
  Full target+previous-image archive member readback preceded canonical staging;
  older `.prev` preimages retained in archive. Current `.prev` and `.pre1511`
  each preserve that P1508 client. Neither previous image was read-only here;
  the reviewed operator preserves read-only previous images when present.
- **19,594 captured existing protected files byte-unchanged**, zero activation
  errors/deltas: other native programs/server/plugins/QCC, current progs/LNO/menu,
  configs and player data. This does not claim a complete new-file census or
  arbitrary metadata preservation. Current peer P1512 VMs were retained, not
  replaced with generated or older P1507 fixture VMs.
- Manifest/source pins independently clear; actual execution-boundary source,
  full predecessor, target-process, collision, protected dependency and exclusive
  stage/rollback identity/hash checks passed. Actual per-target/previous/rollback
  hashes and protected observations were persisted before postcondition asserts.
  No healthy transaction was repeated, owner/peer process killed, shared clipboard
  used, or player data restored. Exact installed image was already functionally
  exercised with the installed common native dependencies, not an owner session.

No native Pi rollout, release or QC Build bump. Immutable Full images/raw input,
header, dependency, warning, TLS, runtime and transaction evidence are retained in
the owned task root. At12Nov00:10:07UTC the uniquely owned
`engine-clean-1511` source/build copy was actually removed through ordinary
`git worktree remove`, **no force**, after all seven source/frozen/receipt image
hashes and retained evidence matched. Exact path/registration absence and
unchanged frozen images/evidence/QC build files were verified afterward; published
source/tag remain. Original source/dependency snapshot and runtime fixtures remain
explicitly retained under `C:\FTESurf-worktrees\lows3-20261111-sol01a1cae9` for
reproduction and pending native performance/owner checks, not unexplained scratch.
Private preservation/rollback archives remain in the separately owned private
root; no player-data or foreign-root cleanup occurred. Numerical native FPS is still
**unmeasured**; see BACKLOG and lextest. Do not conflate this native work reduction
with P1507's separate bounded fairy 0.1% improvement or promise flat worst maps.
