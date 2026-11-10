# P1469 — report failed similarity collection as unavailable

Claimed 10 November 2026 after fetching both repositories and scanning published
patch headings, claim/test filenames and untracked pNNN files: previous max1468.
Scope: one fixed unavailable note from the existing sweep wrapper exception path,
plus the existing test_simcheck.py's real SQLite refusal/recovery control. The
stderr diagnostic remains. No schema, evidence, metric, verdict, threshold,
scheduling, detector, native pin/tag or QC Build change. Operator reporting only.

Implemented/verified locally: original completes with the one predicted failing
note assertion; subject passes all79 checks, including actual SQLite owner refusal,
unchanged verdicts, intentional-disable silence and actual same-connection pair
collection after refusal clears. Linux verification and commit/delivery provenance
follow. Not deployed, no formal anti-cheat or whole-resource-bound credit.
