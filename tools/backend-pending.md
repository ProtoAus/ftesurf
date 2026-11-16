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

## 16 Nov 2026 22:43Z: the P1592+P1595 generation shipped surfd.py + mapmanifest.py ONLY

LIVE (tools/p1592-delivery.md): runtime delta surfd.py + mapmanifest.py at main 6d228cb1; `sweep.py`, `test_sweep.py`,
`test_replays.py`, `test_mappool.py` stay at the previous bytes, so **P1469 and P1580 below are still pending**.
The next generation should also carry:
- `tascontent.py` as a new sealed runtime member: mapwatch has failed `ModuleNotFoundError: tascontent` under every
  sealed generation since 15 Nov, so the map list (data/mapwatch/mapdl.txt) has not been rewritten since then;
- mapwatch's canonical cron schedule `23,53 * * * *` (scan every 30 min) as a reviewed contract change;
- main's sweep.py/test_sweep.py (P1469, P1580); ftesurf-a8 reviews that lens and later does P1580's env activation.

## 16 Nov 2026: the P1590 generation shipped surfd.py ONLY

The generation that went live 16 Nov 14:12Z (P1590, tools/p1590-delivery.md) changed one runtime file, `surfd.py`
(main f052b3ec). Its identity names f052b3ec as source_ref, but `sweep.py` and `test_sweep.py` are the bytes the
previous generation ran: **the two entries below are still pending**. Compare runtime bytes with main when
building the next generation.

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
catches a nonce relayed between two of the Pi's own lobbies; that rule needs no setting. DTLS/TLS/TCP/
WebSocket clients sign the address with a scheme (`dtls://` etc., net_wins.c); it is stripped first.
If the public address changes, ADD the new one and keep the old in `SURFD_RCPT_HOSTS`: without the old
one, every new receipt faults, and `--reread-receipts` faults every older receipt signed on it.
Existing rows are judged only after `--reread-receipts` (200 a pass).

BEFORE ACTIVATION, run `sweep.join_account_key` over a COPY of the live DB (each receipt's runid and pub;
never the live file) and record the fault count here. Expected sources of honest-looking faults: the
owner's ranked rows moved to his account by hand on 11 Oct (signed by his old install's key), and runs
older than the 90-day `runpins` prune whose key was unlinked when the account already had 64 `installs`.
DONE 16 Nov (ftesurf-31, main 363ab0eb's sweep.py, SQLite backup of the live DB into agent-work, deleted after):
2,299 receipts, all signed; **0 faults**; 1,147 "the receipt's key is one of the credited account's", 1,152
"no account is credited with this run". Discriminates: each of the 1,147 with its key swapped for a made-up one,
or for another receipt's real key, faults (1,147 of 1,147 both ways).

Windows only, not run on the Pi: test_rcptcheck 827 checks/0 failed (was 800),
test_sweep 427 ok/0 failed (was 388), test_receipt_{identity,initial_partial,
late_hid,late_rec,late_view,metrics} 0 failed. Mutants fail a named arm: 8 of 8 in
the first round, 5 of 5 in the review round (runpins without `pub = ?`, checks
before the other joins, svport only when configured, no scheme strip, no `runs`
credit). test_receipt_angle_reasons fails one check ("epoch: reader detail names
the measurement/abstention") identically at f5d4450f without this patch.
