# P1067 — refuse malformed save confirmation without losing warm memory

The existing save-prefix confirmation field distinguishes missing historical
metadata from a present unconfirmed prefix. Its reader now recognizes a present
known field before the generic short-row skip, and accepts confirmation only
with the existing exact arity/value. Other short recorder rows remain ignored;
unrelated unknown keys retain their forward-compatible handling.

This closes a cold-restore fallback to legacy behavior. It does not change the
warm-first branch/generation check: matching live memory remains usable even
when the disk copy is explicitly unconfirmed or malformed. Missing metadata
keeps its historical interpretation. Streams, recording formats, stored fields,
forgiveness and timer policy are unchanged.

## Verification

A private native fixture calls the production full state writer, full state
reader and recording rewind/void path. On the inspected published control,
16 acted cases reproduce malformed-marker cold acceptance. The same 16 cases
with the correction refuse those cold restores while preserving missing/valid
cold cases, explicit-unconfirmed refusal, unrelated unknown keys and all eight
matching warm-memory cases. Both fixture programs compile with zero warnings
and run against the same unchanged Windows dedicated server image.

The fixture uses synthetic entities and minimal recording rows; only sprint is
intercepted. It is not real-player input, signed evidence, verifier/rank acceptance
or an actual client map restart. Standard isolated Windows build passes all three
VMs with zero warnings. The recorder suite passes930 checks, zero failed. The
same hash-bound503 REC/167 paired VIEW/10 unpaired VIEW corpus produces identical
full published-control/subject reports:312 existing findings on311 reports, zero
increase. Older differently sized corpus summaries are not substituted for that
comparison. Deployment at2026-10-27T16:53:52Z: the clean committed source
`c89dc4a44a9e70568268195fefffeefdf4544115` was rebuilt with the standard
entrypoint, all three VMs again zero warnings. Both real Windows installs match
all six DAT/LNO roles; predecessor files are retained. CS checksum caches were
seeded without deleting other downloads. The same qwprogs/csprogs pair was
hash-checked, swapped with `.prev` retained and loaded by all12 lobby restarts.
All12 returned active with fresh directory/health readback. Actual append-log
startup segments have positive spawn markers and no QC/builtin errors; an empty
systemd-journal probe was retained as unavailable, not counted as a clean log.
No native binary, surfd/config, Build number or release was changed.

Deployed qwprogs SHA256:
`f3f1447d3531c2a63315cde20ed7f3e292ca60fd4f80bbe0983c1eb51a8ded7a`.
Deployed csprogs SHA256:
`a043b93bf33475da0cabb226020a4e21f3ce1db382dd41ee1ef871465c63aceb`.

This is not a byte seal, atomic/durable/authenticated state-prefix transaction
or protection against a later same-count content replacement. Those remain
separate work. No native/compiler audit, new forgiveness or delayed-output bank
policy is implied.
