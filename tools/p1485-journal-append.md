# P1485 — ordinary journal producers and callback-safe grouping

## Scope

P1480 protects Begin/Drop and P1484 owns finalization/hash and detached close
bytes through callbacks/abort. P1485 protects ordinary **main-side** Frame,
Event, Note and Synth compounds with the existing independent-physics permission
protocol. It does not add a lock to each Raw append.

A main-only active hint avoids consulting the shared buffer before exclusion.
Thread identity must qualify it first: the shared editor drain has a conditional
NQ/CSQC/debugger worker route, not a universal main-thread affinity. That admitted
worker route neither reads the main hint nor calls the main permission helper.
This is not qualification of an arbitrary foreign producer.

Relative-only CPU work shares an owned token. Nonrelative input releases only
this operation's transition before delivery. Initial and per-event empty paste
polls leave the token alone; the shared paste implementation releases it just
before an actual recipient, after consuming and clearing its queue. The plain
Flush interface remains unchanged. Later work reacquires using **current**
recording/permission state; it does not restore a pre-callback saved permission
over a callback's new ownership, or pre-journal later events across Begin/Drop.

Main Note/Synth protect their complete compounds. The five plugin Input shims
are live, address-taken entries in the default client; their defined-unused
warnings come from SERVERONLY, not dead client code. A separate main-only
poisoned hint, derived only after actual current poison is observed/set under
exclusion and reset by actual Begin/Drop, avoids a real lock for every subsequent
already-poisoned main API call. Original first-source Note provenance is retained.

No new captured field, grammar, consent, API-table/VM layout, detector, threshold,
ranking or enforcement policy. QC Build remains 89.

## Controls and measured results

`tools/test_input_journal_append.py` compiles extracted actual producer, drain,
paste, lifecycle, synth and permission bodies into one compact C executable.
The exclusion has a real nonrecursive OS mutex and actual competing OS worker;
UI recipients, identity checks, diagnostics and selected host state are scoped
adapters, not a running engine or actual clipboard/debugger/backend.

The original pre-guard acting control and retained subject are separate from the
later cache regression:

- Original control: **851 checks, 754 failures**; retained guarded subject:
  **857 checks, zero failures**. Most repeated control failures are producer
  ownership assertions, not cheat cases. All three actual competing-worker arms
  falsify the control and pass the subject.
- Initial guarded `fe1693a6e` versus final cached source: **868 checks / 3 failures
  versus 868 / zero**. Both retain all three worker-arm passes. Exactly the three
  repeated-mark mutex-count assertions falsify the initial guard: 1,000 main
  marks now own once, actual Drop/Begin resets the hint, and worker-first poison
  is observed once without replacing its source annotation. Inactive marks own
  zero times; a joined owning worker touches neither main-only hint.
- Lifecycle regression: **18 / zero**; close/actual SHA-256/abort regression:
  **136 / zero**. Raw/Line/End/close-context behavior was not rewritten for the
  cache. The still-valid cap regression remains **628 / zero**.
- Append compilation keeps the three signedness diagnostics in the exact frozen,
  unchanged dispatch body visible. Only that verified-equal block has a warning
  fence; changed guard/journal/host code stays `-Wall -Wextra -Werror`. Close's
  five pre-existing crypto signedness diagnostics remain separate from strict
  journal/host compilation. Typed fixture dependency declarations are not
  replacement lifecycle behavior.
- Independent initial frozen-diff and small cache-refinement reviews: no issues.

These are correctness and **mutex-call-count** results, not measured latency,
physical input, arbitrary foreign-plugin runtime, or actual native debugger/
clipboard acceptance. Native backend/ring, status/cvar publication, broader
foreign entry and platform/lifecycle-affinity coverage remain open.

## Clean integration and native build

Source `8131f3a4f090d877dc4bd22de9531d01c0447340`, tag `patch-1485`, includes
published `52f4f0ce9` (P1477/P1481/P1482) as well as P1479/P1480/P1484. The initial
reviewed C/test bodies were unchanged by that merge before the reviewed cache
refinement. No uncommitted peer source was included.

The standard `src/build.ps1 -Engine -Full -NoDeploy -FteRoot <owned engine>
-Jobs 8` built client, dedicated server, five default plugins and three QC
programs. Native warnings: **74**, the exact normalized diagnostic multiset of
the retained prior full build, **zero new**; compiler errors zero. QC: three
zero-warning programs. Seven native outputs were frozen from that clean source.
Clangd database regenerated through the QC tooling with an explicit owned engine;
its existing six unrelated input warnings remained, paste file had none. Actual
compiler results, not LSP cleanliness, are the build evidence.

Reader regression: **949 / zero**. The completed required corpus baseline is
**568 files / 356 pre-existing faults**, not a clean corpus. Reader source is
byte-identical to that completed sweep, and all 568 input hashes and membership
were rechecked unchanged. That result is reused, not represented as a fresh
whole-corpus measurement or new native-recording acceptance.

## Installed 10 Nov 2026, 21:44:05Z

Only the two Windows client EXEs were promoted using the existing build Deploy
function, with exact candidate/predecessor bindings and idle-actor checks. No
process was killed. The published peer's installed P1484+P1482 image was inspected
and preserved, not replaced with an older base.

- `C:\FTESurf\ftesurf64.exe` and `C:\FTEQuake\fteqw64.exe`:
  `76da219f43bbd4131eab96998df4678f74370f5ea8ed2d4c67a260ec16cd7d18`.
- Both `.prev` files retain predecessor
  `7930cc92097f6cc2f8899367f385312a8c58a6b08d919419dd5121859937c36f`.
  Original preimages and previous `.prev` images were archived separately.
- All 20 protected server/plugin/VM/config existence/hash observations matched
  before/after. No player data, generated progs, fleet/backend or Root action.
- Actual staged and both installed `--version` processes exited zero with
  `FTE git-8663-patch-1485-0-g8131f3a4f`.

The version branch proves linked image/startup identity, **not gameplay or live
recording behavior**. Normal-play owner acceptance remains pending in
`lextest.md`; the separate genuine parked-run prerequisite is still pending.
