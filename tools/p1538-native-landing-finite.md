# P1538 — finite context for bounded landing observation

## Problem

A newly admitted ordinary-landing observation could remain positive after an
unsupported numeric context was sanitized by normal movement. Existing airborne
observation and movement semantics must not change.

## Change

Capture finite entity/world gravity and velocity-cap eligibility before movement,
and require it only in the new ordinary-landing disjunct. Preserve existing
original-input admission, airborne behavior, water-jump checks, endpoint/ground
proofs, observation lifetime, complete movement state, and current interfaces.
No new traces, capture fields, ranking rules, thresholds or QC Build.

## Verified

The existing native FullWalkMove fixture gains four cases and 41 assertions.
Matched original product with the final fixture: 1814 checks, exactly three
unsupported-positive failures; subject with the identical fixture: 1814/0.
Geometry and complete playermove/movevars byte-preservation controls act in both.
Existing finite landing positives and older airborne behavior remain passing.
Windows dedicated build has zero new warnings against its same-target baseline;
original infrastructure/fixture failures are retained privately, not relabelled.

This is Windows synthetic source qualification, not final clean stamped images,
ARM runtime, full supported-world/HFR, human/device, calibration, independent
acceptance, security-audit completion or deployment. Independent delta review
and normal final build/deployment remain separate gates. The human test remains
postponed and the native/compiler/file-writer vulnerability lane remains deferred.
