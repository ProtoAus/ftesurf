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

Deployment and live Momentum acceptance are pending. No demo body, private
identity, credential or raw private backend output belongs in this document.
