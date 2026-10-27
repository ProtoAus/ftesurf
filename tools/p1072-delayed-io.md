# P1072 — queued player-origin effects retain their admission

The selected policy is **practice/unranked, not cancellation**. Supported queued
player-origin map outputs retain the admission and practice state that caused
them. When that lineage is no longer current, the actual affected player's
attempt becomes practice; the authored effect and continuing play are preserved.
Current clean admissions and genuine world-origin effects remain supported.

This is a bounded VM-local I/O-lineage change, **not full Rule-8 closure**.

## Implementation

`src/server/sv_bank.qc` provides non-aliasing admission identities, source capture
and the existing practice funnel. Delayed outputs store their own snapshot;
ordinary/nested dispatch saves and restores context. Recipient checks are at the
supported player physics writes, after existing refusals where present, rather
than assuming every input's named target is the benefiting body. Dynamic name
resolution remains delivery-time behavior. Integer exhaustion fails closed.

True arm/placement/rest/load/connect boundaries mint identities; disconnect
invalidates the old identity. Same-zone already-armed reconciliation preserves
both identity and bank practice. A readable but refused save does likewise.
Admission tokens are internal server state, not new captured recording fields.
No recording format, native ABI/pin/tag, threshold, Build or release change.

Published P1070 menu work is preserved. P1071 was already reserved by another
session's untracked test file; fresh headings/pending-file inspection claimed
one number, P1072. Native pin/tag remain P1066; qcbuild remains unchanged.

## Qualification

Private preregistered native control/subject probes each exercise25 cases with
the same compiler/image and genuine production I/O, timer and body-write helpers.
Only sprint is intercepted for synthetic player-like bodies. Delayed thinks run
on the native scheduler after actual server initialization; they are not called
directly by a test substitute.

Both arms preserve the asserted effects and running states (one deliberately
armed latch case stays armed). The subject alone practices the expected old,
previously tainted or invalid player lineages. Acting clean/world, cosmetic and
held-teleport controls remain clean. Actual activator-versus-named recipient,
delivery-time name changes, nested world-activator dispatch, existing recursion
cap/context restoration and integer exhaustion are covered. Two v1 regressions
were fixed: idempotent arms and refused saves had incorrectly advanced identity.
Acted clean and already-tainted-latch cases now cover both.

Stock three-VM builds have zero warnings. Fresh reader regression is930/0.
The complete current503REC/167pairedVIEW/10unpairedVIEW domain, every file hash
and reader hash match archived independent control/subject reports:312 findings
across311 faulted reports, unchanged. This is valid unchanged-dependency reuse
and zero increase, not a new sweep or a claim of a fault-free corpus.

Three independent final read-only reviews found no remaining issue in this
bounded candidate. Original reviewer timeouts, fixture API/include mistakes,
pre-initialization silence, incorrect old startup marker and incorrect held-input
expectations are retained as failures, never counted as passes. Every native
run restores the captured prior fixture program and stops its owned process.

Latest published-menu integration leaves all seven reviewed source files and
the complete baseline server/shared/definition/reader graph byte-identical.

## Limits and delivery state

The probes do not prove genuine client/input, real disconnect/reconnect,
successful save/retry retention, full recording/rank, hardware provenance,
calibration or human feel. Captured practice continues to use existing flags.

Commitments held outside the dispatch chain—including persistent map/button/
timer/pad/body/carrier state—and a native same-command completion fence remain
open. This patch must not be described as a complete bank or anti-cheat system.

Source `fae8bd6dad65281acc4ab49d50e8db932bd5bd46` and engine ledger
`04c4ebabc1eb4cb97866ac6908e1ead6c07c689a` were inspected and pushed exactly.
The clean owned tree's final stock3VM0warnings output retains the same reviewed
source and native-probe compiler. Initial binding wrapper wrongly expected only
six files; NoDeploy intentionally copies three SRC manifests too. The guard was
corrected against the SAME already-passed output, without rebuilding or replacing
any evidence. Production QW contains no fixture functions/markers.

At2026-10-27T20:04:05Z server-only delivery was verified: both real Windows
installs have the qualified QW DAT/LNO with prior copies preserved. Windows
owner processes were not controlled; they load it at their normal next VM load.
Pi QW SHA256 is `f0943780b849aa942765b803af51e523228a0dab7cdb74fb47099d1a900fcd33`,
previous QW `1fa6df95` retained. Stock -Pi would ship CS too, so the bounded
ordinary QW-only hash/.prev/atomic-swap and literal bare-unit restart primitives
were used, preserving installed CS `a043b93b` and peer UI. At the actual short
shared-sweep-lock boundary the directory showed12 fresh zero-player lobbies;
no busy-server force was used. All12 restarted once, each new PID/native-image
identity and NEW application-log spawn positive passed with no selected QC
errors. Every local heartbeat's lower-bound time is after the LAST restart;
local/public health200 and directory12 pass, maximum local age3s. Lock released,
stage consumed. No backend, native, menu/client, config, owner/player data, Build
or release payload was changed. Normal real-client clean-run human acceptance
remains pending in lextest.md, separate from native synthetic qualification.
