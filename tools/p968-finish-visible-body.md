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
Publication and compatible Windows/Pi delivery remain separate pending gates. Pi directory availability currently blocks
ordinary promotion before any staging; no peer backend or old transaction may be
restarted/reused to bypass it. P965 Windows delivery remains separately recorded.
