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
Correction-review disposition and exact source publication/server-only delivery
are recorded separately. No native, client/menu, backend/config/data, owner
process, Build or release shipment is part of this change.
