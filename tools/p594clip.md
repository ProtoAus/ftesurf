# Patch 594 — fail closed on non-finite inherited native UI clips

Claimed after fetching both origins: published maximum heading 593; no other
untracked p594 claim in the affected checkouts. Parent engine source 452c8814a
has the P593 implementation 25ad9d56e; game source d3b7174.

Final P593 review found that the bridge intersects its inherited caller clip
AFTER P589's mesh-command validation. A malformed caller clip, or overflow while
converting a finite virtual clip to physical coordinates, must not authorize a
native service callback. This is a host-boundary robustness correction, not an
ImGui/panel/input milestone or a native-module sandbox.

Pre-registered falsifier: compile the actual host implementation with acting
service callbacks; feed inherited NaN, infinity and finite conversion overflow.
P593 must fail the no-native-callback/no-flush/owner-release assertions. Subject
must reject all three, release once to fallback and still draw valid clips in
both VMs. Existing valid mixed and P589 galleries must remain green. Build to
zero new warnings relative to the captured isolated P589 baseline. Keep the P593
tag immutable; use one separate forward patch and exact source/byte provenance.

Predecessor falsifier ACTED: 12 failed assertions, with native callbacks/flushes
incorrectly authorized in all three malformed cases. Corrected host controls:
170 assertions, zero failed; all 24 grader controls also pass. The host uses a
bit predicate equivalent to FTE's NaN/Inf test. Local engine source/tag:
`bed572f50475dc627df6bda482891b6da9a85495` / `patch-594`. Frozen full build,
valid GL regressions, publication and guarded native-only delivery are pending.

P593 source/tag remains immutable. This guard does not change QC/progs or Pi
payloads, service ABI, panels/input/model/preferences/Build; malformed clips are
host-stub controls, not real-driver fault injection.
