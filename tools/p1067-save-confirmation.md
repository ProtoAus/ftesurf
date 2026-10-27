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
comparison. Deployment provenance is recorded separately when completed.

This is not a byte seal, atomic/durable/authenticated state-prefix transaction
or protection against a later same-count content replacement. Those remain
separate work. No native/compiler audit, new forgiveness or delayed-output bank
policy is implied.
