# P1500 — compiler string append bounds

## Change and limits

A compatibility-dialect string append now uses the existing token capacity and
length-error path before writing, reserving the final terminator. Accepted
strings and their complete embedded-NUL byte payloads retain existing semantics.
This is narrow compiler defensive hardening, not an anti-cheat detector,
sandbox, measured exploit or remote-reachability claim. No input capture,
evidence grammar, scoring, enforcement, mover, settings or QC Build change.

## Qualification

- The real standalone compiler passes six successful full-string payload checks
  and three acting length-refusal controls. Checking the emitted string section
  proves the append and complete NUL-preserving result actually occurred.
- An actual compiler built with the proposed guard omitted safely intercepts the
  two old out-of-bounds append attempts before writing. The untreated unsafe old
  compiler was never executed. A one-byte-too-strict compiler rejects the two
  legitimate separator-capacity controls, which the subject preserves.
- Independent frozen source review is CLEAR for the two-line production repair.
  This is not parser-wide audit completion or live remote-dispatch acceptance.
- Supported standalone compiler and full Windows client/server/five-default-plugin
  builds pass. The full build's 74 native warning payloads exactly match the
  prior qualified baseline: zero new. All three production QC VMs compile with
  zero warnings. Known Q208 system-header warnings in deliberately minimal
  compiler fixtures are recorded separately, not called product build warnings.
- Initial private environment/fixture mistakes are retained, not regraded.
  Optional dialect/escape fixtures with invalid test inputs were excluded from
  acceptance; the original nine required capacity/payload/refusal cases remain.

## Publication and delivery

Published engine source: `b077b6715ac9bcefecac13949075b3b3c5c5a086`,
tag `patch-1500`.

Final clean tag-linked rebuild and guarded dual-Windows delivery are pending.
No backend generation or lobby progs swap is implied by this compiler repair.
