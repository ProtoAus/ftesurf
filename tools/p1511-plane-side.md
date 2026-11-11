# P1511 — conservative ambiguous plane-side early exit

## Status

Native source published: feature `e087aac60`, integrated inspected engine
`24a3d0104ea58d34ab1b30443ecaa580f8eed06c`, tag `patch-1511`. Not deployed yet.
Exact-helper CPU controls, independent source/oracle review and controlled
working-tree native builds pass.
Real renderer/replay functional checks pass and one matched paused view has
exact decoded pixels. Wider/owner visual acceptance, FPS measurements and the
final clean-tag Full build remain pending. This is part of the
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
build was repeated. Final clean-tag Full build, gameplay and actual destination
readbacks are still required before delivery. No recorder, evidence, movement,
protocol or QC Build change.

## Functional runtime and bounded visual check

Both controlled clients used the same frozen baseline dedicated/HL2 plugin,
P1507 CS bytes, map/replay assets and settings. Fairy33811 actually advanced
from0 through39seconds in both arms, then paused at15seconds. Main-view alpha
trace proves view eligibility, admitted commands, edges/work and plane/memo
paths acted. No assertion/VM fatal was found in successful-arm logs. This does
not prove the shortcut's exact hit count in gameplay; the extracted C work
control is separate evidence.

The matched1280x720 screenshots were inspected and have **exact equal decoded
RGBA pixels** (PNG container bytes differ). This verifies only that paused view,
not every effect/frame, human visual acceptance or pixel identity generally.
Screenshots/clock gates/input hashes/raw logs are retained under the owned root.

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
Final clean-tag Full and destination checks still apply.

## Delivery

Final clean-tag Full qualification is in progress. Only the two Windows native
clients are intended for this renderer change; server/plugin/QCC/VMs/configs/
player data are not a native ship set. Exact final image, clean stamp, predecessor
and protected-file readbacks must be recorded separately before delivery is called
done. The independently reviewed client-only transaction preserves rollback and
read-only `.prev` images. No native Pi rollout, release or QC Build bump is needed.
Do not treat source publication or helper controls as installation or a measured
improvement to worst-map 0.1% lows.
