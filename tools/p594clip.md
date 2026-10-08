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
bit predicate equivalent to FTE's NaN/Inf test. Published engine source/tag:
`bed572f50475dc627df6bda482891b6da9a85495` / `patch-594`. Frozen game source/test
commit `9e820a7`; published integration `8206480` adds only the already-published
peer off-ramp tooling/docs, not QC or native source used for the build.

Clean full build stamped `git-7118-patch-594-0-gbed572f50` has exactly the same
74 compiler warning message/count fingerprints as the isolated P589 baseline,
zero new; all QC compiles have zero warnings. Frozen valid bridge gallery
`p590-bridge-u16xorn0` and P589 gallery `p589-mesh-n418owc1` pass; 170 actual-core
host assertions, 24 bridge and 33 mesh grader controls pass. Logs and representative
screenshots inspected. LSP translation units retain baseline warnings only.

Guarded native-only swaps to C:/FTESurf and C:/FTEQuake keep P593 rollback;
progs/configs/data/Windows servers/existing DLLs are unchanged. Native SHA256:
`1667b333594b1c4517cb0df19e95c5545f6c2f960166412a456877bb05103e20`.
Actual INSTALLED executable paths ACT in `p590-bridge-qksc2vm_` / `-ek419z65`,
zero failed (52 screenshots per suite); destination hashes and protected state
verified 2026-10-08T11:34:11Z. No second Pi swap: P593 payloads are unchanged.

The no-flush host assertions measure the rejected DRAW path; resource cleanup
may independently flush as required by P589 texture lifetime. No native draw
callback is authorized with a malformed final clip.

P593 source/tag remains immutable. This guard does not change QC/progs or Pi
payloads, service ABI, panels/input/model/preferences/Build; malformed clips are
host-stub controls, not real-driver fault injection.
