# P1509 — contain the cron similarity phase

## Problem

The existing pass deadline is cooperative between comparisons. An in-flight
load, comparison or normal database operation can exceed it inside the cron
process before badge verification runs. Source-byte/move/pair/selected-SQL/native
lock limits remain useful, but are not whole-process containment.

## Change

Normal cron runs only similarity through a child of the existing `sweep.py`
entrypoint. Linux `/usr/bin/prlimit` installs a 512 MiB virtual-address-space
ceiling and 12 CPU seconds before Python/bootstrap starts. The parent waits at
most 15 seconds or the cooperative allowance plus five seconds, whichever is
smaller; on timeout it kills and reaps its own worker, then proceeds. Missing or
unsupported containment reports unavailable instead of an unbounded fallback.
Direct in-process APIs retain their existing cooperative contract.

The private worker requires actual inherited limits. It does not run application
migrations or account/ranking policy, initialize a missing database, or migrate an
older schema. Existing-only admission uses read-only exact-schema checks before
non-creating RW open. The configured native lock wait applies from the initial
schema probe through startup; ordinary connection callers retain 5000 ms.

Request/result bytes are bounded. Termination makes final pair counts unknown,
not a measured zero. Already-committed store-only rows, source rotation and
interrupted-source recovery are not erased or regraded. No new dispatcher target,
capture, recording field/format/schema, similarity threshold, verdict or ranking
policy is introduced. Native pins/tags and QC Build are unchanged.

## Verified

Existing entrypoints, using only isolated fixture DATA:

```text
python surfd/test_simcheck_process.py
python surfd/test_simcheck.py
python surfd/test_simcheck_budget_cli.py
python surfd/test_sweep.py
python surfd/test_schema_compat.py --work-root <owned-scratch>
```

- Actual Linux ARM: 16/16 process/admission controls, including a compared score-1
  synthetic playback pair with tiers unchanged; an acted blocked comparison
  killed/reaped before the following badge-phase call stub; an over-limit
  allocation with no numeric measurement; actual held-exclusive-lock startup;
  disabled/unsupported/missing limiter, typed wait, exact/default native wait,
  existing-only/no-create/older-schema and owned-connection closure controls.
- Windows exercises platform-independent controls; five Linux-only arms are
  explicit skips, not claimed passes. All 37 related entrypoints have zero new
  failures; two existing admin UDP/amplification assertions also fail identically
  on untouched source and remain unchanged.
- Actual original cooperative control enters a comparison, exceeds the same
  three-second test wait despite its one-second allowance, and is killed/reaped
  by its owning test parent. The subject's three-second test ceiling is a fixture
  override, not the normal fifteen-second default.
- An initial actual ARM candidate compared correctly but reran account migration
  and changed fixture tiers. It failed and was corrected, not accepted. A second
  startup control showed the old native wait preceding the requested budget;
  both admission connections now receive the requested wait before schema reads.
- Recording reader: 949 checks, zero failures. Unchanged read-only 568 REC / 183
  VIEW inputs retain their exact bytes and fault lists, including the pre-existing
  349 / 7 faulted files. This is not a fault-free or independently human-labelled
  calibration population.

## Limits and delivery

These are process address-space/CPU/admission controls, not a measured total RSS,
unconditional kernel-uninterruptible startup/reap deadline, fair scheduler or
full-fleet coverage guarantee. The enclosing admission lease must remain held
until its exact worker is reaped; never orphan a writer to satisfy a clock.
A called badge-phase stub is not native-verifier or browser acceptance. Synthetic
positives do not calibrate real-assist detection or a false-positive threshold.

Source publication is separate from deployment. Independent frozen-source review
and qualification of the existing guarded generation boundary are required
before ordinary backend rollout. No live service, native binary, progs, player
file or config was changed by qualification. There is no retrospective evidence
backfill or new capture/consent authority.
