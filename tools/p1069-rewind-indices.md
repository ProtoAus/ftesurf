# P1069 — require whole recorder generation and rewind indices

Saved recorder generations and row coordinates are existing integer indices.
Range comparisons alone did not establish that: malformed numeric metadata could
skip a branch-cut check or enter a fractional warm-buffer rewind.

The generation check now requires a value in its existing range and an integral
index. The rewind entry rejects non-whole row coordinates before either buffered
or stream dispatch. No new numeric gameplay limit, stored field, recording format,
forgiveness or delayed-output policy is introduced. This is index validation, not
save authentication or a substitute for the existing branch/serial/cut checks.

## Native falsifier

The private fixture uses the production full writer and full reader. A production
rewind performs a real cut; production recording appends a distinguishable new
tail. Fourteen contexts cover current/old/future/negative/malformed generations,
invalid row coordinates and independently confirmed or failed cold copies.

Published control accepts invalid warm matches; the subject preserves only the
valid current-generation warm match. A confirmed cold copy still works when the
warm generation does not match. Both fixture compiles have zero warnings and use
the same unchanged native dedicated server image. Two initial fixture interface
compile errors were retained, then corrected against the actual production call;
neither was a native pass.

Limits: synthetic entity and minimal recording rows; sprint only intercepted.
Not real player input, signed/rank acceptance, an actual client map restart,
full stream/native-checkpoint coverage or atomic/durable/authenticated pairing.
Standard isolated three-VM build passes with zero warnings; the recorder suite
passes930/0. Every hash of the same503 REC/167 paired VIEW/10 unpaired VIEW domain
and the reader source remains unchanged from P1067, reusing its exact independent
control/subject reports:312 existing findings on311 reports, zero increase.
Server-only delivery from clean committed source
`693544632b0ae163427dd4706a438357f0206f07` is verified at
2026-10-27T17:45:07Z. Both Windows server DAT/LNO roles match the qualified output;
predecessors are retained, and menu/client/native/owner-config roles were unchanged
during that copy. Pi QW-only hash/previous-file checks and all12 ordinary restarts
completed, with fresh active PIDs, positive application startup logs and no selected
startup QC errors; directory12 and health pass. The existing CS cohort was retained.
No menu, native, backend, Build or release payload was shipped.

The first remote restart incorrectly included `.service`, which the literal sudo
grant does not permit; it stopped no unit. The same verified handoff resumed with
the standard bare unit spelling. All12 then restarted, but an immediate postcheck
was not accepted as a pass; independent fresh readback established their active
state/startup logs instead, without repeating restarts. Both failure records remain.

Live/Windows qwprogs SHA256:
`1fa6df95f566e5457ab0dbcbc525287642bdd409111600fdec342211ae58f73d`.

## Delivery scope

This is a server-only correction. Another session owns P1068 menu work; delivery
must not overwrite its menu/client payloads or pause that work. Qualify all VMs,
but deliver the changed server roles to both Windows installs and the lobby fleet,
leaving unrelated native binaries, menu/client payloads and surfd untouched.
