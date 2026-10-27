# P1073 — active button callbacks retain their source

P1072 covers ordinary queued/nested I/O. This increment covers the **actual
armed button callback** from Press/Use/Damage through Top, automatic Return and
Home, including outputs that themselves schedule delayed I/O.

The selected policy remains **practice/unranked, not cancellation**. Old/bad
player-origin callbacks practice the actual affected player through existing
write hooks, preserving the authored effect and continued play. Clean-current
and genuine world-origin actions remain supported.

## Implementation and scope

Gesture wrappers establish the root source before immediate outputs, preserving
an existing nested context. The actual scheduling helper snapshots it and stores
one VM-local function pointer beside the existing source fields. A native think
trampoline restores that context around the real callback, then restores its
caller. Callback-to-callback rearming therefore retains the original cause.

Source's activator behavior remains intact. In particular, ignored Use can
update an activator without replacing the pending callback; locked/refused input
must not retag that work. Actual replacement scheduling replaces the active
think. No clock, guard, count, physical movement or existing refusal is changed.
Buttons remain the existing state machine; this does not enable brush movement.
No captured field, recording format, native ABI/pin/tag, threshold, Build or
release change. Real max+1 inspection claimed only P1073, respecting published
peer P1070 and reserved P1071.

## Qualification and independent review

Clean local source954de018 against2471f03c was frozen before three independent
code/control, evidence/regression and adversarial reviews. No product defect
was found. The original14-case control/subject includes a qualification mistake:
a cosmetic rename executed before the intended held teleport, so that row proved
missing-target rejection, **not** the held guard. Those original artifacts and
all reviews are preserved, not renamed into passes.

The smallest fixture-only correction reverses creation order so the actual
player is resolved and refused before its cosmetic marker. Corrected production
control14/subject14 ACT with the same compiler/native/fixture/runner; the product
source remains byte-identical to all three reviews. No missing-target refusal
appears in either corrected log. Both arms preserve effects, timer state and
unrelated bodies; only the selected stale/bad causes practice in the subject.
Current/world-origin physical effects stay clean, held body stays put/clean,
intervening ignored/locked input preserves callback attribution, and nested
callback-to-delayed-output attribution survives. Final combined context is zero.

Case13 proves the old physical callback was canceled and a replacement cosmetic
Home output ACTED; **not** that arbitrary new physics is clean or all prior map
state was erased. Case10 is explicit fixture-cleared hop taint with the same
admission, not a genuine forgiveness/reset proof. Case11 changes source class,
not a real disconnect/reconnect/reuse test.

Reader raw stdout reports930checks/0failed. The postread wrapper used UTF8 for
Windows CP1252 stdout and failed after subprocess completion; exit code was not
persisted. The raw log is unchanged and the invocation was not rerun or promoted
to a recorded exit0. Prior unchanged-reader exit0 proof is separate. A fresh hash
check of the **entire current680-file domain** and reader exactly matches the
independent archived503REC/167pairedVIEW/10unpairedVIEW control/subject reports:
312findings across311faulted reports, zero increase. This is unchanged-dependency
reuse, not a new corpus sweep or fault-free-corpus claim.

## Remaining limits and delivery

Native probes use synthetic player-like bodies, intercepted sprint, production
helpers and actual native PUSH/ltime scheduling. They do not demonstrate real
client input/reconnect, actual recording/rank/PB submission, human feel or full
carrier/world-state retirement. The input receipts bind selected sources, not a
complete independently measured transitive build closure. Fixture progs restore
by byte comparison and owned process handle; retained CFG/logs are evidence, not
a claim that the complete fixture filesystem is pristine.

Persistent map/button/counter/timer/pad/body/carrier commitments outside the
active callback and native same-command completion remain OPEN. Neither P1073
nor the full anti-cheat task is complete merely because this increment passes.

Final stock3VM production build has zero warnings, same c24 compiler, allQC/SRC
input hashes unchanged during compilation and no fixture symbols/markers in the
production QW. QW SHA256 is
`da35b1ec855134a8b9dd66150627b1fb0bd25013eea443fda3cecd17b431a676`;
LNO `a75ae4cc`. This is separate from the instrumented native fixture build.
The independent correction review accepted the held-body evidence with no
remaining issue; all three original product-source reviews remain valid because
every reviewed source byte is unchanged. Original incorrect coverage stays
archived alongside the corrected evidence.

Source `b0f404fc7f794ff9370eaf7b51a4290b9629b43a` (including reviewed954de018)
and engine ledger `21a0d573bca3b033aa4c3589ecc206e443110a1e` were inspected and
pushed exactly. At2026-10-27T21:10:37Z BOTH real Windows installs have qualified
server DAT/LNO, previous P1072 DAT/LNO retained. No owner process was controlled;
Windows loads at the normal next server-VM load.

Pi QW `da35b1ec`/previous`f0943780` verified after ordinary QW-only atomic swap.
The actual short shared-sweep-lock boundary showed12fresh zero-player lobbies;
all12 restarted ONCE using existing literal bare-unit commands, no busy force.
Every new PID/native-image identity and NEW application spawn log passed with no
selected QC errors. EVERY local heartbeat lower-bound is after the LAST restart;
local/public health200 and directory12 pass, max local age3s. Stage consumed and
lock released. Protected CS`a043b93b`, peer menu, native binaries, backend/config/
owner/player data unchanged. Native lobby processes were normally restarted for
the QC swap; no backend service or owner client was signaled. No Build/release.
Human normal-clean-run acceptance remains pending in lextest.md; the remaining
persistent-state/native-fence scope is still open.
