# P740 — sparse KSF demos and prompt requested Momentum demos

## Scope / predictions

Enable the existing bounded KSF demo lane (`--demos` shares the existing request
budget), retaining the upstream refusal/cooldown ledger. The live KSF host was
already parked after HTTP500; do not reset it to force an acceptance example.

Add a foreground Momentum requested-only worker to the existing momgrab entrypoint:
cheap one-second queue polls, no ordinary board/held-run scans, at most two jobs a
pass, same global lock, persisted CDN pacing and cooldowns. Refresh explicit
requests between transfers in the background grab so a mid-batch click takes the
next slot rather than waiting behind the frozen automatic batch. Do not abort an
active transfer or bypass other queued users, request validity, expiry or capacity.

Falsifier: old source must download background A then B despite a click for C during
A; fixed source must take A,C,B. Queue-only mode must never scan the background
corpus, and invalid/poll/busy/cooldown cases must not start network work. Stop only
between completed transfers, leaving unstarted requests queued.

## Delivery boundary

Current serving schema20 generation is sealed under the existing Friends29
pre-import fence. Do NOT edit its runtime, manifest or source bindings. Reuse the
supported canonical legacy import dispatcher for the operator-approved KSF flag;
it must still check the same OPEN state/generation/hashes and hold admission.
The non-pinned canonical momgrab worker likewise imports surfd only through its
existing admitted forwarding entrypoint. No app/schema/native/QC/lobby restart or
new parallel OPEN guard is planned. The persistent worker is a new owned supervised
process and must be included in future source-transition drain inventories.

## Validation so far

- Local offline priority controls: 10 tests pass (including cold handoff,
  backwards-clock pacing and CLI batch/delay caps). Original e8afa04 mid-batch arm
  really transfers A,B and fails the expected A,C,B order; fixed source passes.
- Existing request suite: 9 tests pass, including served synthetic replay output.
  Existing momgrab control script also exits zero. No CDN traffic in these tests.
- Canonical admitted KSF importer: `--watch --max 0 --demos --go` exits zero,
  discovers four pending demos, makes zero upstream requests and encounters no
  dispatch/guard error. Scheduled KSF row enabled with `--demos` at
  2026-10-16T15:30:35Z, preserving its existing `1-59/5` cadence and other jobs.
  Sealed manifest/state bytes remain unchanged, admission OPEN; cooldown untouched.

## Persistent worker / transitions

`surfd/momrequests.service` is a **user** service for the existing proto backend
account; install it as `~/.config/systemd/user/momrequests.service`. It runs only
validated explicit requests, polls at one second, uses the same global momgrab
lock, and gracefully finishes the current bounded transfer on SIGTERM. Use
`systemctl --user stop momrequests.service` BEFORE a future source-generation
admission close/drain, and start it only after admission is safely OPEN again.
It holds an ordinary legacy-import admission lease for its lifetime, so include
it in source-transition inventories, not just the finite cron children.

The background momgrab schedule and minute momjobs fallback must use the updated
canonical helper too; the fallback adds `--requests-only`. All three canonical
entrypoints retain the existing pre-import dispatcher/fence. Do not edit the old
sealed route manifest or its runtime source to add flags.

## Review corrections

Both independent reviews of clean 7808c0a blocked promotion. Four new regressions
reproduce its stale-request resurrection (A,C,D), pacing-boundary delay (A,B,C),
stale BSP inventory reaching the converter, and unsupported 180-second forced
stop. The corrected loop rebuilds explicit requests solely from fresh validation,
reselects after pacing, refreshes the BSP filename inventory on a lookup miss,
and uses `TimeoutStopSec=infinity`. The separate transition close/drain remains
bounded and fail-closed: a slow active transfer can block a transition; never
force-kill it or bypass admission just to proceed.

Corrected Windows controls: 15 tests, 14 passed and POSIX SIGTERM arm explicitly
skipped; request (9) and existing grab controls pass. All four 7808c0a regression
controls fail for the predicted reason. The POSIX arm uses a real loopback slow
HTTP response, SIGTERM during the blocked read, and verifies full transfer,
settled request and clean exit after release; it is not a new codec fixture.
Original Linux 7808c0a checks also passed 10 priority, 9 request, existing grab,
45 KSF and user-unit verification; KSF controls remain valid because KSF source
has not changed. Corrected Linux/SIGTERM checks and follow-up reviews pending.

## Deployment seam

Corrected 44dc15e Linux tests all pass (15 priority/SIGTERM, 9 request, existing
grab, user-unit verification), and both follow-up independent reviews are clear.
The product blobs are identical after merging published P739 metadata; its native
pin/tag are retained. Both repositories are pushed.

The first existing `surfd-deploy.ps1 -NoReload -Only surfd/momgrab.py` transaction
stopped before copying anything: it required literal `surfd:app`, while this
sealed runtime legitimately uses `witness_wsgi:app`. Its stage, private database
backup and failure evidence are retained. The fix is in that same entrypoint,
not an alternate copy wrapper: explicit `-GuardStateDir <existing control>` is
permitted ONLY with `-NoReload` and ONLY the non-pinned momgrab helper. It proves
the private OPEN generation/closure, unchanged target hashes and recorded live
candidate PID/start/cwd against the pidfile. Legacy reload checks are unchanged;
no witness-name substring exception, new guard, sealed source or manifest edit.

PowerShell parse/narrow-mode controls pass. The existing synthetic Linux guard
fixture acts positively and rejects wrong PID/start, CLOSED, changed source and
insecure root; proof neither imports the app nor signals the candidate. Initial
fixture setup exposed inherited NVMe setgid; exact private test-root permissions
were fixed rather than weakening guard mode checks. Failed fixture evidence is
preserved. One tool review was clear; the other timed out after identifying a
valid allowed-input gap: `-Remote` could target the immutable source tree itself.
The corrected precheck rejects the source root, descendants, noncanonical paths,
and symlinked helper/temp destinations. New Linux controls fail on c66dd93's
source-root acceptance and pass on the fix, along with nested/symlink refusals.
This is a read-only identity/destination preflight, NOT a generation/CAS handover
or a promise to retain an epoch through copying a non-pinned helper. Execution
still requires its own admitted import at activation. Updated reviews found double-leading-slash aliases, replacement-marker paths,
and default backup running before destination proof. The corrected seam rejects
double anchors and reserved `__` inputs, proves identity/destination BEFORE the
backup, and substitutes the backup TAG before inserting the literal destination.
Five PowerShell controls pass, including an acted refused transaction that leaves
a synthetic SQLite subtree unchanged. The old 186d321 input, backup-order and
literal-destination controls all fail; its double-slash source-root proof also
acts/fails refusal, while corrected Linux root/nested/symlink/identity controls
pass. SQLite fixture handles now close explicitly before Windows cleanup.
Both 6474131 follow-up reviews were clear.

## Deployed and live

`surfd-deploy.ps1` from `35988cd`, `-Only surfd/momgrab.py -NoReload -SkipTests
-GuardStateDir`, 2026-10-16T16:39Z: `GUARD_MASTER_OK`, mode-600 DB backup,
`COPIED=1`, `VERIFY_BAD=0`, stage removed, no app reload. The guard state dir is
the one the original KSF cron row passes as `--state-dir`, NOT the WSGI `control`
folder beside it; the first `35988cd` attempt named the wrong one and stopped
before backup or copy.

16:43:19Z: `momrequests.service` installed (unit blob `1a3a53ad`), enabled and
active, its admission lease observed. The background row (`3-59/5`) runs the new
helper; a minute row `momgrab.py --go --requests-only --max 2` was ADDED (there
was no momjobs row before). Guard OPEN, sealed state/manifest unchanged.

Public HTTPS acceptance, 16:48:42Z: a short PB outside the automatic top ten,
its original absent before the request, showed Get. POST returned queued; polling
reached ready in 1.263 s. `/api/replay/N` returned 200 with a matching header and
212857 bytes; `reccheck` found zero faults (six notes); the board row then had
Watch. The worker's journal logged that transfer (`ok 1`, 1 filed, 1 linked).
No in-game playback was driven.

Readback 2026-10-16T21:58Z: same worker PID, 0 restarts, unit enabled; crontab
hash equals the post-change snapshot; deployed helper is blob `543e18e5`; the
minute row has logged no error; background grabs keep filing; `/health` 200.

KSF: the `--demos` row runs every five minutes and discovers demos (4 pending at
enable, 50 at 21:58Z) but has requested and linked none. The upstream is still
parked from its HTTP 500 at 2026-10-16T08:36Z, until 2026-10-17T08:36Z; the
cooldown was not reset. No KSF download or playback is claimed.

`tools/test_reccheck.py` exit 0; `ftesurf/data/runs` 295 recordings, 190 faults,
equal to the P741 baseline (no reader change in this patch). The default
selector also reads 268 save prefixes; one raised PermissionError in
`read_lines` and stopped the CLI (BACKLOG).

No demo body, private identity, credential or raw private backend output belongs
in this document.
