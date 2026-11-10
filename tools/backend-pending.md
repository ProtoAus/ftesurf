# Backend handoff delivered together — 10 November 2026 UTC

The requested P1447/P1448 entries were activated together in the accepted primary
backend, with the corresponding QC on all12 NanoPi lobbies. Public frontend assets
and a real single-leg Fetch were verified. See the
[dated delivery and rollback provenance](p1447-p1448-delivery.md).

The two local Windows DAT/LNO copies still await a peer's shared fixture gate;
in-game download/rendering and human acceptance are pending. The activated
backend entries have been removed from this queue, not relabelled as pending.
Do not redeploy a healthy backend merely to refresh this handoff.

## Next qualified generation — P1469 unavailable similarity reporting

Include the published one-line `surfd/sweep.py` reporting fix from P1469: setup or
collector exceptions retain stderr and return an explicit unavailable/coverage-
not-measured tick-summary note. No schema, evidence, metric, verdict, threshold,
scheduling or resource-limit change. Existing test_simcheck passes79 checks on
Windows and79 on NanoPi Linux; [verification and limits](p1469-sweep-unavailable.md).
Not live yet: accepted runtime source bindings and namespace/Root prerequisites
must be qualified normally. Do not hot-patch an immutable serving generation,
reset grants, restore old data or reopen it to ship this small reporting change.
