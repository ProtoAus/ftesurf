# P1514 — bounded water-jump gravity-use observation

## Status

Implemented and source-qualified; independent frozen-source review and deployment
are **pending**. Engine commit `622268893990308398dc7f2066f433855f2f16bf`, tag
`patch-1514`. Neither Windows install nor any lobby/backend was changed by this
qualification. This is not a complete retained-state bank or anti-cheat sign-off.

## Problem and bounded change

Source11+ water-jump movement returns before the ordinary airborne gravity-use
observer. Retained non-default gravity can change the body during that path.
P1514 captures that actual move's forced-XY velocity, clear-first-trace result and
accepted endpoint before categorization. It reuses the existing default-gravity
clear-path and landing probes, setting the existing command-local use signal only
when an actual body difference is established.

Admission of a retained property is not proof of its use. In particular, the
assist may expire during this command and still move. A default value, discarded
clamp difference, collision or landing is not promoted into a positive witness.
The new subset is finite, airborne, shallow/no-water, Source11+ and clear-path.
Legacy/deep-water, grounded, portal/slide and nonfinite contexts remain outside
this proof. No physics, wire/API/schema, reader or new ranking rule is added.
Existing practice-run policy consumes the existing signal.

## Verification

- Supported Windows `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8`, isolated
  source: build exit0, 74 inherited warnings, none in `pm_source.c`. Incremental
  subject build exit0, zero warnings. Both real Windows installs untouched.
- ARM64 `make -C engine sv-rel FTE_TARGET=linux_arm64 -j2`, low-priority offline
  source export: build exit0, 16 inherited warnings, none in `pm_source.c`.
  All768 exported source files checked by SHA256 before build; the sole overlay
  over native24a3d0104 is the qualified `pm_source.c`.
- Actual native `pm_selftest` on **both platforms**: exit0, **1690 checks,
  zero failures**, including **82 new assertions over14 cases**. Full playermove
  bytes agree between unarmed and armed observers. Positive default-gravity
  controls establish a body difference; collision, landing and expiry controls
  prove those paths actually acted. End-of-command signal reset is checked.
- With the final test function and old production runtime, the ARM control acts
  and fails **exactly four** expected-use assertions. The subject passes all four.
  Earlier Windows old-runtime controls also missed those four signals; their
  additional misconfigured landing-fixture failure is retained, not a pass.
- `python tools/test_reccheck.py`: **949 checks, zero failures**. A90-second
  wrapper interruption is retained separately; the same script completes with
  sufficient execution time, without changing assertions.
- Existing corpus: **568REC +183VIEW**, identical file hashes and reader results;
  existing **349REC/7VIEW faulty** counts unchanged. This is parity, not a clean
  corpus, a field catch-rate measurement or a verdict on existing players.

The two native subjects used exactly the same raw `pm_source.c` bytes (SHA256
`332f6c32ad678049c1b53549f9f126aed976310b1dada4d33cd4585976c90547`). The engine
commit's other changes are the patch ledger. The subsequent native parent update
was documentation-only. Qualification binaries are pre-publication controls,
not version-stamped deployment artifacts.

## Limits and remaining delivery

Independent reviews must bind the final clean engine/QC source and unchanged
proof inputs. Source publication does not substitute for those reviews. After
review, the normal clean, version-stamped Windows/ARM build and guarded native
rollout must preserve previous binaries, recorder/resume data, actor/dependency
checks, destination hashes and live provenance. No deployment gate was acquired
or left held during this offline work. No release/QC Build number was requested
or changed. Other retained-state commitments remain explicitly partial.
