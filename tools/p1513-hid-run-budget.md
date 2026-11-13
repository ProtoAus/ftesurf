# P1513 — optional signed-run upload admission budget

## Problem

Journal uploads have an absolute 64 MiB body cap, but no run-length allowance.
Choosing a production rate/floor is an operator policy decision, not a reason to
omit a separately configurable mechanism or invent a default.

## Change

Both settings must be explicitly supplied, through the existing application
setting loader (environment first, then `surfd.env`):

- `SURFD_HID_BASE_BYTES`: canonical decimal integer, 0 through 67108864.
- `SURFD_HID_BYTES_PER_TICK`: canonical decimal integer, 1 through 67108864.

Neither set preserves legacy admission exactly. A partial, empty, malformed or
out-of-range policy refuses route registration with a fixed configuration error;
it never silently disables an intended limit. Policy is captured at registration.
No production coefficients are chosen or enabled by this patch.

After the existing upload signature, server-owned receipt, run/nonce and
committed journal hash/size agree, the body allowance is:

```text
min(67108864, base_bytes + signed_counted_ticks * bytes_per_tick)
```

Only the existing positive integral signed finish clock is used. A missing,
nonpositive, noncanonical or overlength clock under an enabled policy is 503
`journal run budget unavailable`, not a player fault or an invented duration.
An excess is 413 before application body consumption or temporary-file creation.
Existing files are preserved. Normal signature/receipt refusal, absolute body
cap, separate rate bucket, body hash check and no-replace publication remain.
No new evidence field/schema, consent, verdict, score, automatic reread or
retention policy.

## Verified

```text
python surfd/test_hidupload.py -v
```

- Untouched source: a correctly signed, receipt-authorized short-run journal
  actually stores with 200 despite an explicit fixture allowance; the new 413
  assertion fails. Original RED retained.
- Windows 17/17 and ARM 17/17, no skips. Exact boundary, one-byte excess, longer
  signed duration, huge exact-integer arithmetic under the absolute cap,
  unavailable clock, invalid/partial policy, config snapshot, authentication
  ordering, preserved existing evidence and legacy multi-MiB short-run control.
- Byte-counted WSGI stream proves only the 1024-byte header was consumed on
  budget refusal; the temporary-file function was not called.
- Two fresh actual-application arms verify `surfd.env` admission and environment
  precedence, not just a stand-in route or setting callback.
- First ARM run exposed a test-only Flask 2.2 import-name incompatibility;
  use the real module name, not an invented child package. Original failure
  retained; runtime policy code was unchanged by that fixture correction.
- Related receipt snapshot checks pass on Windows and ARM; existing directory
  controls pass on Windows with its explicit file-mode skip. The separate Linux
  directory test hits an unchanged FakeClock missing monotonic; correctly
  module-bound subject and untouched prior control reproduce it with identical
  keeper code. It is retained, not repaired or labelled a green whole-suite run.

## Limits and delivery

Counted ticks are NOT elapsed wall time and can exclude viewing/parked intervals.
An operator must explicitly choose compatible journal overhead before activating
this policy; no field-derived safe default or genuine-player calibration is
claimed. It bounds application admission, not bytes already buffered by a proxy,
aggregate storage, retention or overall request wall time. Unknown clock is not
bad evidence. Existing default behavior remains unchanged.

Source publication is not production activation or deployment. Independent
clean-source reviews and existing guarded-generation/current-source/DATA/
fallback/live checks still apply. No native source, binary pin/tag, QC Build,
recorder/parser or evidence-history change.
