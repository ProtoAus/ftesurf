# P1480 claim — journal Begin/Drop exclude the existing physics worker

Owner pi.dev session01a1c66e-34b2-747f-b389-a4e589d5d20c, 10 Nov2026 UTC.
One parent writer in isolated paired source worktrees. Fetch both origins plus
all registered untracked pNNN tests/claims: max1479 -> reserve1480 only.
Scope: main-side Begin/replacement and Drop/free-reset save/restore existing
CL_AllowIndependantSendCmd permission; worker lock stays unchanged. No new
capture/format/consent/enforcement. Whole End/IO and normal append races remain
OPEN; do not hold worker exclusion across callback-capable filesystem writing.
Actual Begin/Drop/Raw + actual permission helper with real pthread lock:
prechange12 checks/4 unsafe-admission failures, stopped safely BEFORE any UAF.
P1479 cap fix remains separate unchanged source and immutable published history.
