# P968 — bounded visible-body finish forgiveness

Production still used the engine-cleared carrier transfer window and global
speed cap, dropped upward components, missed general freezes, and put pending
finish/load forgiveness inside unsettled-start logic. The historic p455rebase
is NOT merged or ready: its proposed dwell does not close same-packet/new future
commitments. This patch deliberately takes the documented bounded alternative,
not that failed completeness argument.

## Change

SV_TimerFinishForgive reads the live latched carrier using the existing cashout
scale, the mover's maxspeed with existing cvar/default fallback, and separately
refuses an upward body or carrier. Save/physics holds, MOVETYPE_NONE and airborne
bodies cannot grant. JumpWatch calls it after fresh-hop tagging (which cancels
an older pending forgiveness), outside the start-settlement block. The same four
tag/counter latches clear on an actual grant. No new field, evidence row, threshold,
collection, format, native pin/tag, Build or release.

## Acting proof and limits

Preregistered full production SV_TimerJumpWatch executes in the native dedicated
VM, with only sprint output redirected and ordinary StartFrame fixture scheduling.
Fourteen control and14subject contexts; both compiler runs have0warnings:
ordinary rest, latched horizontal/upward carrier with zero transfer window,
rising body, mover cap below global cap, already-settled start, save hold,
MOVETYPE_NONE, airborne, over both caps, falling body plus upward carrier,
cap fallback, no pending and no hopped tag. Exact unchanged and changed tag/
counter results are checked, not absence of a print. Both use the same native
binary; whole production module bytes and fixture outputs are retained.

These are explicit-state rule-boundary tests, NOT a driven real push-volume,
engine cashout/physics, socket input, cold-reader/signing/posting, performance
or owner gameplay claim. Future/mover/name-addressed commitments and the P455
round11 bank remain OPEN in BACKLOG. This does not make the broader settled-body
leaf done or promise no future speed can arrive. Reader/grammar/history untouched;
prior reader evidence remains scoped and its known corpus read failure remains.

Standard production3VMs/0warnings now qualifies. Parent direct review checks
actual carrier cashout source, scalar fallback, separate vertical terms, hold
polarity, fresh-hop cancellation before the moved call and unchanged four-latch
grant. Native control/subject bind the identical native binary and frozen module.
This is a direct review, not an independent reviewer or full old rule audit.
Published source100db5f7 and engine32c7d106. Qualified Windows composition53c54f97
(3VMs/0warnings, whole timer byte-identical) installed server DAT/LNO in BOTH
installs at2026-10-24T12:28:27Z. All4destination hashes and exact P965 preimages
passed; .prev/prior history retained and11fresh native/client/menu/config hashes
unchanged. No process signalled: not an already-running reload or owner pass.

Combined P968/P965 Pi composition8223a1c8 is qualified/published:3VMs/0warnings,
QW byte-identical to main P968 and CS byte-identical to actual fleet; timer equals
native subject and save module retains P965. Source base0577d431 was NEVER APPLIED;
actual predecessor stays P964, not P965. This does not rename/retry a failed apply.
Promotion remains pending. New feature-boundary read-only check still finds
directory unavailable, exact P964 QW/current CS unchanged,
no .new or P965 phase. No staging/restart/backend transaction has been performed.
Do not restart a peer backend or reuse an old transaction to bypass availability;
recover actual ownership/directory then requalify the fresh canonical/pinned/empty
boundary. P965 Windows delivery remains separately recorded.
