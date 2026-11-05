# P1313 — preserve movement, not a fresh clean retry arm

## Boundary

A retry deliberately restores movement. That is not permission for a fast restored
armed start to become a fresh clean attempt. Use the existing practice eligibility
rule, not a velocity clamp or guessed reconstruction of saved jump phase.

Only after successful `SV_RetryApply` placement, an ARMED player still within its
own start-box group is checked with the existing `SV_TimerNotFast` walk/jump limits.
An unsafe fresh arm goes through `SV_TimerPractice`, retaining body and flags and
making the existing dirty/practice state sticky. Multi-region and configured
hull-band occupancy use the same existing `SV_ZoneInBox` semantics as the timer.
Running retries, positions outside the armed box and direct Multi-Session-style
restores do not pass this new wrapper-only guard. Ordinary low-speed/normal-jump
arms remain eligible. No change to `run_t_startok`, saved phase or movement.

No new captured signal, native/API/format/flag/tier/ranking-policy or QC Build.
The public native source/tag remain the separately qualified P1312; this is SSQC.

## Verified so far

- Retained untouched published module and candidate run through the actual retry
  wrapper, writer/reader, consumed latch and state-file deletion. Twelve explicit
  state/body cases distinguish the five formerly missing practice marks from walk/
  jump boundaries, running/outside-box/direct restore and existing status controls.
  The candidate marks all five and preserves exact origin/velocity and prior bits.
- Existing five normal-load plus fourteen grant/EOF controls remain unchanged.
- The fleet-qualified `c24`/git-7809 compiler repeats both counterparts; all three
  VMs pass the actual `build.ps1 -NoDeploy` entrypoint with **zero warnings**.
  The older local `7ccb` results remain historical, not the fleet toolchain. The
  first external counter-module include-path failure is retained; the existing
  source-local control seam was fixed, not another numbered wrapper introduced.
- Mandatory reader suite **949/0**. The exact three-glob RUNS sweep has **544**
  inputs and retains every old byte and paired classification: **344** faulted
  recording reports and **7** faulted views. No fault-count increase, clean-corpus
  or SAVES claim; the fixture writes only its private test data.
- Private original vectors, raw results, recipe/compiler/native identities and
  exact build outputs stay private. The fixture uses synthetic explicit entities;
  it is NOT a real native map_restart, held-jump/dwell, ranked finish or human pass.

## Current state

Local candidate, not published or installed. Fresh independent whole-feature
source/state and recorded-consequence reviews remain pending. Actual deployment is
recorded separately; no old-data failure or passed test is rerun/regraded to promote. Small human check is
pending in lextest.md; broader saved-phase/native bank coverage remains partial.
