# P1333 — requested current-file consistency, not historical remeasurement

## Problem

A stored similarity row can carry the exact two historical buffers' length/SHA256
without saying whether today's files still contain those bytes. Default review
correctly never rereads a source, but the owner had no explicit bounded check.

## Change

For a captured pair already in the authenticated run's bounded similarity panel,
`Check current files (this pair)` makes one POST through the existing session,
same-origin and CSRF control guard. It reuses the existing replay-path resolver
and historical A/B orientation. Legacy, skip, invalid, missing and off-panel
captures perform no file reads. Ordinary run details keep their no-reread contract.

The request opens at most two regular descriptors with nofollow/nonblocking flags
where supported. Each side reads at most its stored length plus one, capped at
16MiB plus one, in chunks no larger than64KiB. Both metadata identities are checked
before/after. Real EOF and the historical length/SHA are required for `matches`;
a stable observed difference is `differs`; unavailable, changing, over-cap or
unadmitted work is never a match. A shared two-second admission clock is
cooperative, NOT a hard disk/kernel/CPU bound. SQL reads reuse the existing owned
budget contract; borrowed callers' progress callbacks are not replaced.

The reply/UI carries fixed states and an observation time, not current digests,
paths or new identity. Existing public projections, database schema/rows,
historical metrics, captures, verdicts, badges and collector selection are not
changed. No background reread, automatic skip retry, history backfill or new
recording/device capture is added. The observation concerns bytes read at the
requested check, not authenticity, guilt, a coherent global instant or forever.

## Qualification (source, not deployment)

- Existing unmodified authenticated similarity/source entrypoint:10 cases pass.
- Windows focused old/new source suites:25 cases,0failures,1explicit POSIX FIFO
  skip. Real Node DOM click executes the actual renderer/post code, sends the
  guarded pair and leaves historical metrics visible.
- Actual Linux same source:25 cases,0failures,5explicit Node-absent DOM skips;
  the real nonblocking FIFO control ACTS there. Windows exercised those DOM cases.
- Real file reads+EOF, no database/public mutation, same-size restored-mtime edit
  in either panel orientation, exact extra-byte cap, mutation-acted/unavailable,
  missing/over-cap/expired work, legacy/skip/invalid/off-panel no IO, auth/origin/
  CSRF refusal, and borrowed progress-callback preservation are exercised.
- Initial new-test CSRF setup failed twice: a test-session lookup at `/` does not
  carry the `/admin` cookie. One bounded diagnostic compared the actual cookie
  contract/working controls; extracting the real owner's page token fixes the
  fixture without changing CSRF policy. Both failures are retained privately.

- Required isolated three-VM build:0warnings; hashes in BOTH Windows installs
  held. Reader949checks/0failed. Corpus548REC/168VIEW remains344/7faults: exact
  unchanged reader/buffer findings reused,168 pairedREC/VIEW reports parsed.
- Full existing admin control script retains two UDP-amplification/snapshot
  assertion failures. The exact unchanged prefeature admin source reproduces BOTH;
  no unrelated repair or whole-suite clean claim. Targeted HTTP/source checks above
  pass; actual Linux full admin controls also pass (Node absent there). The first
  owned Linux overlay lacked the existing public board.html; its404 is retained,
  and staging that exact static input fixed only the fixture. Initial standalone
  corpus import omitted its existing tools/ search path;
  the small wrapper seam was fixed without changing the reader or its findings.

At this source checkpoint, independent whole-feature reviews and actual backend
delivery remain pending. Human review
readability remains unconfirmed. Historical skip remeasurement and wider fleet/
whole-invocation hard bounds remain separate gaps, not closed by this feature.
No native code, engine pin/tag, qcbuild, protocol or evidence format change.
