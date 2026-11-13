# P1541 — JARGON search-state correctness; performance experiments rejected

Status: retained product change is **CEM search-state and invalid-elite correctness only**. Current-main core-only build has zero warnings in all three programs; final read-only review found no blocking/high/medium issues. Clean-commit compatibility and deployment are still pending. No faster or better ramp-boarding result is claimed.

The unpublished1538 draft was overtaken by published1538–1540. After fetching both repositories and checking patch headings/untracked tests,1541 was reserved through the canonical shared claim. Historical artifacts retain their original labels and hashes; they are not redated or relabelled as published patches.

## Retained change

`SV_TASOptCommand` began a curve search with `bestv=-1` without initializing its active best vector. If all38 structured candidates were invalid, `SV_TASOptCurveResult` could center the following generation on a preceding search's vector. Invalid samples could also become arbitrary elites and shrink spread.

`SV_TASOptCurveReset` initializes active best/mean/spreads after aim/lead dimensions are finalized. Explicit seeds, priors, remembered lines and archive candidates remain separate. Elite fitting excludes **only the established-1 invalid sentinel**, not all negative values: legitimate trajectories can receive negative fitness after wall/loss penalties. Scoring bands, incumbent conventions, sampler/RNG, movement and plan decomposition otherwise remain unchanged.

All experimental changes to`sv_tasautosurf.qc` were removed; that module is byte-identical to the inspected baseline. No new cvar, boarding-window option or merged final objective ships in this patch. Native code/pins/tags, recorder formats, finish authority and qcbuild89 are not changed by this task.

## What was tested and rejected

Every arm, failure and exact source snapshot is retained. A failed continuation does not prove an entry physically impossible; a failed search does not prove the existing route optimal.

### Coordinated sampling — confounded, removed

Four of20 candidates received correlated three-knot perturbations without additional RNG draws. Helper properties passed. Observed stage2: pristine finished12.450 after566wall seconds; candidate did not finish by603seconds; stage5 both remained unfinished. A later audit found the candidate switched from headless to OpenGL. This is **not a valid causal regression or speedup comparison**. The unproven sampler was removed.

### Joint final board+finish — acted, failed

Matched640×480 OpenGL, same image/native trio/map/guide/settings, seed1,600s and explicit`backs10` both:

| Arm | Actual finish | Wall time | Backtracks |
|---|---:|---:|---:|
| Corrected control |12.450s |205s |5 |
| Joint candidate |No finish |605s budget stop |11 |

Candidate marker acted once. Its4/4 plan progress was not a finish. The joint product helper/cvar/fixture were removed; no second seed or default promotion was justified.

### Guide-based boarding window — did not act

The initial same-image0/1 pair both finished12.450/201wall seconds/5backtracks, but neither tried an alternative boarding point. Correct server set echoes did not prove feature activation. This was **not an acting comparison or algorithm null result**.

A bounded90s diagnostic confirmed knob/global1, eligibility and all other guards clear. The initial128u point ray from the guide missed, making`d0=-1` and rejecting every alternative. Later down-offset rays hit a floor instead of the expected face. A zero normal on a missed ray is **not a measured native normal**; no imported/native normal mismatch was established.

### Native-reached-state window — acted, no benefit

The next prototype retained the useful board objective, reused its actually played arrival, and generated nearby candidates from player-box traces around that reached state. Existing finish/coast authority was retained. An acting pilot found four valid candidates and actually played alternatives. It was not a performance comparison.

Fresh matched600s OpenGL pair, immutable same image, seed1, same guide/map/settings and server`developer0`:

| Arm | Actual finish | Wall time | Ordinary backtracks | Alternative trials |
|---|---:|---:|---:|---:|
| Corrected control |12.450s |217s |5 |0 |
| Native-window candidate |12.720s |298s |5 |3 |

The lower, higher and further-along entries actually played. Their normalized board energies were1527/1498/1542 against reference1548. Their initial continuations all failed existing coast checks. Candidate added0.270s of game time and81s of observed search time, so it supplied no benefit on this seed. This is a **single-seed observation**, not a statistical regression claim. The prototype was removed, not retained as a default-off unproved feature.

Successful played-line exit diagnostics were780u/s, vz+894, z-9851 for control and780u/s, vz+891, z-9857 for candidate, both heading135degrees. These are optimizer diagnostics, not independent physical first-contact/impact/launch reconstructions.

The remaining late/deep-board, room-to-turn and platform-landing goal is still unresolved; see ROADMAP and lextest. None of these experiments establishes global optimality, impossibility or that maximum contact energy suffices for a useful launch.

## Retained-code verification

- Inspected QC base2416c68920614fef89f33caac92b5c578cbb77ae; engine documentation base08c8495b803a1eb4928843ccbdbf411df507a2dc. Owned worktrees fast-forwarded to inspected published mains ea96309d/70273fa7, with solely this task's retained delta reapplied. TAS modules/tick dependencies are unchanged by those published intervening commits; helper source, driver, fixture and tick hashes still match the4185-check evidence.
- Compiler SHA2561f2efd0616f60e2c3d29372cb7c32f8cad1f15cb0831d8e2490e5468048550bc. Existing pwsh7`src/build.ps1 -Jobs 8 -NoDeploy -PassThru`; three programs, zero warnings.
- **4185 actual-QC VM assertions** for the retained code: acting pristine stale-best/invalid-elite controls; reset sentinels; all-invalid grid/generation; valid/zero/negative/mixed fitting; all20 sample/RNG equivalence across generic/demo, lead/free-command dimensions and stored retrieval. The deliberately incorrect`>=0` gate is rejected by valid-negative assertions.
- The fixture extracts production helpers plus pristine functions from the resolved baseline, compiles them with fteqcc and runs the existing standalone qclib target. Scores are synthetic and world side effects stubbed; it proves **no movement, warm-start grid, main dispatcher, platform landing, native verification or performance gain**. The miniature ABI warning belongs to this test VM; normal product builds have zero warnings.
- The broader now-removed prototype had4480 helper/transition checks and independent reviews. Those are historical prototype evidence, not extra retained-feature coverage or physics proof.
- Completed controls have a pre-existing strict-REC duplicate-board-counter fault. Actual in-game finish is observed, but the files are **not fully structurally valid/native-verified recordings**. Sparse per-packet poses cannot establish exact physical first-contact or impact timing. BACKLOG records the unresolved compatibility/restore issue; no recorder repair is included.

To run the retained synthetic fixture, choose a fresh output below an owned task root:

```text
python -B tools/test_jargon_cem.py --out C:/FTESurf-worktrees/<owned-task>/cem-check --qcvm <isolated-qcvm.exe>
```

This host's existing standalone target needed UCRT DLLs on PATH and C`-std=gnu17` because the compiler's default C23 mode conflicts with its legacy boolean enum. Those are test-build flags, not an engine/header change.

## Provenance and remaining delivery

Earlier Claude series used different settings, versions, budgets or presentation modes; they are context, not equivalent arms. No timing difference from those runs is credited to this patch. All accepted pairs used fixed640×480 OpenGL. Effective FPS was not independently measured. The maintained2500MiB/quiet guards were unchanged; an extra agent-only5GiB preflight block was preserved separately before using the maintained gate for the bounded diagnostic. No other process was killed or player data/config reset.

Immutable arms, source/diff snapshots, compiler/unit logs and identity-free summaries remain under`C:/FTESurf-worktrees/jargon-sol-1113a/`, including`artifacts/rejected-joint-source/`, `boarding-b96-source/` and`rejected-native-window-source/`. Private identity/process output is not committed.

Completed final scoped read-only review: safe reset initialization order and preserved explicit seeds; reserved sentinel and fatal-dispatch conventions unchanged; actual fixture/source hashes and intended mutation failures inspected. No blocking/high/medium findings. It did not execute builds, native compatibility, recorder verification or performance tests.

The first final build controller lacked the documented compiler-on-PATH setup and stopped before compilation. Same invocation then compiled all three programs with actual0warnings. Its naive reader matched the word in`0warnings` and falsely flagged the healthy build; corrected only the observer against retained outputs, without rebuilding. Both original failures remain preserved.

Next delivery gates: clean inspected-commit build/current-Windows-native compatibility, exact inspected-SHA publication and normal dual-Windows/Pi deployment with preservation/destination/live UTC evidence. No release, native rebuild or Build-number bump is part of this task.
