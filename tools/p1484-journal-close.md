# P1484 — callback-safe input-journal close

## Useful outcome and scope

This is existing-recorder evidence-integrity and allocation-lifetime maintenance,
not new cheat detection or an attestation that input came from physical hardware.
A finishing journal owns its exact closed bytes through callback-capable work.
Its later completion cannot discard a newer capture or replace a newer digest.
Pending or aborted completion is not available as a completed commitment.

Engine source/tag: `bb3e7cbac8cbfc1c585c891ab743a8b951d3f7dc`, `patch-1484`.
`qcbuild 89` is unchanged. Filename acceptance, evidence grammar, capture/consent
and enforcement policy are unchanged. The new declaration is internal to the
client; no VM/plugin interface layout or server protocol changed.

## Acting controls

`tools/test_input_journal_close.py` compiles actual End/Digest/LastDigest,
Begin/Drop, the existing permission helper, four actual host-abort functions,
and actual SHA-256/CalcHash, with explicit dependency hosts and a real OS-thread
worker/nonrecursive mutex. Its callback schedules use only synthetic constants.

| Arm | Result |
| --- | --- |
| Prechange engine `5ce7c7602f985b9d99cd21495f462e03c142639d` | 132 checks, 37 failures |
| P1484 subject | 136 checks, 0 failures |
| Existing cap/terminal regression, adapted context dependencies | 628 checks, 0 failures |
| Existing Begin/Drop regression, adapted context dependencies | 18 checks, 0 failures |

The baseline stops before competing mutation; allocation quarantine is a safe
host measure, not an executed physical UAF. Dependent continuation checks run
only after safe subject admission. The cases check complete worker/terminal
bytes, saved digest identity and state, surviving replacement captures,
returning nested closes, all four reviewed nonlocal exits and nested cleanup.
The old failed-write adapter now expects one hash, not a second globals rehash.

Journal/host compilation retains `-Wall -Wextra -Werror`. Unchanged crypto is
compiled separately with `-Wall -Wextra`; the same five extra signedness warnings
remain visible in both arms. The original compilation refusal is retained and
is not graded as the acting baseline. Independent frozen-diff review: no issues.

The inspected VFS path consumes/closes bytes before filesystem-hash work pumping.
Returning command callbacks are injected schedules, not discovered production
command dispatch or an observed post-callback VFS read/UAF.

## Build, readers and delivery

The standard `src/build.ps1 -Engine -Full -NoDeploy -Jobs 8` invocation built
client, dedicated server, five default plugins and three QC programs. Native:
74 existing warning occurrences, exact normalized diagnostic-payload multiset
match to the retained prior full control, zero new; QC: three times zero warnings.
Full rebuild is required here because an internal header changed. Linked stamp:
`git-8651-patch-1484-0-gbb3e7cbac`.

Reader regression: 949 checks, zero failures. The completed required corpus
baseline remains 568 files / 356 pre-existing faults, NOT a clean corpus.
Its exact reader blob and every original input hash are unchanged, so that
completed result is reused rather than regrading a timed-out extra sweep.

At 2026-11-10T19:45:54Z both Windows client executables received the same qualified
image, SHA-256 `006d65ac25a72a345d72cfe474101d2f8d87d37aaa44c12593805f512f0a120f`.
The existing build Deploy function was reused with source/predecessor/actor
checks, protected-file verification and ordinary `.prev` backups. Only the two
client EXEs changed; servers, plugins, progs, owner config and player data were
not replaced. No game process was stopped. Actual installed `--version` on both
images exited zero with the clean P1484 stamp; this early branch is startup/image
provenance, not rendered gameplay, capture or thread-behavior acceptance.
No release, lobby/backend generation or ARM deployment was needed or performed.

## Still open

Normal main/worker append synchronization, backend/input-ring counters and
foreign-thread native-plugin marking remain unqualified. Fatal allocator paths,
native Android runtime, hardware input, durability, latency and detector
calibration are not established by these controls. Optional owner gameplay
acceptance and the separate genuine parked-run capture remain pending in
`lextest.md`; no manual pass is inferred.
