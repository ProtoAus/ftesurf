# Backend handoff delivered together — 10 November 2026 UTC

The requested P1447/P1448 entries were activated together in the accepted primary
backend, with the corresponding QC on all12 NanoPi lobbies. Public frontend assets
and a real single-leg Fetch were verified. See the
[dated delivery and rollback provenance](p1447-p1448-delivery.md).

Both local Windows DAT/LNO copies were promoted and hash-verified03:20:55 UTC
10Nov after the peer fixture window opened. In-game download/rendering and human
acceptance remain pending; native smoke was not launched through low-memory or
renewed-fixture admission blockers. The activated
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

## Next qualified generation — P1580 receipt server address and account key

`surfd/sweep.py` + `tools/rcptcheck.py` (deploy the new rcptcheck to `SURFD_TOOLS`
too; an older one is skipped, not fatal). A first full receipt read now faults
(admin-only: `receipts.verdict`/`reason`, `sig` untouched, no schema change) a
signed server address that is not the Pi's, and a run credited to an account
whose receipt key is in none of that account's keylinks/installs/runpins
(ROADMAP 14.3 b). README "Receipt address and account-key checks".

Set at activation, in `surfd.env`:

    SURFD_RCPT_HOSTS=180.150.62.57
    SURFD_RCPT_LAN=192.168.1.102
    SURFD_RCPT_PORTS=27510,27520,27530,27540,27550,27560,27570,27580,27590,27600,27610,27620

Unset, the address check notes "not configured" and faults nothing. The 16 Nov corpus (2,296
receipts) has 2,295 on the public address and 1 on the LAN one. A LAN address is reported as a note, never
passed or faulted (AGENT_NOTES: "a private address is nobody's" -- another network's server at that address
reads the same). The signed port must also equal the unsigned `svport` the writing lobby recorded, which
catches a nonce relayed between two of the Pi's own lobbies.
If the public address changes, update the setting or every new receipt faults.
Existing rows are judged only after `--reread-receipts` (200 a pass).

Windows only, not run on the Pi: test_rcptcheck 816 checks/0 failed (was 800),
test_sweep 0 failed (was 388 ok), test_receipt_{identity,initial_partial,
late_hid,late_rec,late_view,metrics} 68/96/158/227/268/120 ok, 0 failed. 8 of 8
mutants (each check or join removed, unset made to fault) fail a named arm.
test_receipt_angle_reasons fails one check ("epoch: reader detail names the
measurement/abstention") identically at f5d4450f without this patch.
