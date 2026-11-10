# P1484 claim — callback-safe input journal close ownership

Owner pi.dev session01a1c66e-34b2-747f-b389-a4e589d5d20c, 10Nov2026 UTC.
Fresh both origins, patch headings, claim headings, line-strict tracked filenames
and all registered untracked pNNN test/claims inspected: max1483 -> claim1484 only.
One parent writer in isolated engine/qc source worktrees.

Existing End/hash/write integrity: finalize while existing physics worker excluded,
detach a finished buffer into a scoped main-only owner, restore prior worker
permission BEFORE callbacks/I/O, publish only the still-current closed digest,
free only that allocation and clean detached owners before actual host_abort.
No new capture/consent/wire/schema/ranking/enforcement policy. Normal append/
backend counter/foreign-plugin concurrency remains OPEN. No generic audit.
Actual-C callback/real-worker control at5ce7c7602:132checks/37ownership/publication
failures, baseline safely stopped/quarantined BEFORE deliberate unsafe memory use.
