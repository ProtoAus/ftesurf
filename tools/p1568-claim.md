# Patch 1568 claim — bounded large owner-history acquisition

Owner: parent jargon-sol-1113a session01a1d34e, 14 Nov 2026 UTC.
Fetched both repositories; published headings plus canonical/owned untracked
pNNN claims max1567, so claim1568 only. No Build/release decision.

Scope: retain existing authenticated owner Archive transport and full SHA256
binding while replacing whole-record allocations/8MiB cliff with bounded stream
I/O, checked integer byte accounting and finite disk/work limits. Reuse existing
native range-copy and write-stream APIs; any new hash/read seam stays narrow.
Actual >8MiB and odd >16MiB bytes, small positive and acting integrity/partial
refusals are required before delivery. No REC grammar/trust/rank/retention change.
