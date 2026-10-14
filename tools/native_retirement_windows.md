# Separate Windows bounded retirement native gate

`test_update_native_retirement_windows.py` is a NEW full-superset subject gate.
It does not edit or replace historical pending-only graders, helpers, or the
in-memory protocol model. Tooling only: no product patch/pin, deployment, release,
push, tag, signing key or pin override. Unit actors are not native engine evidence.

## Inputs and invocation

The parent supplies exact before/subject clients and text-identical unstripped
companions, an already production-signed Windows loopback manifest and its entire
selected-platform object closure (repeat `--objects` for a union). This driver
verifies the signature with unchanged `updatefeed.verify`, all object hash/size
identities, and complete PE text equality before creating either fresh root.
Do not invoke wrappers in historical roots. Example for NEW owned disjoint paths:

```text
python -B tools/test_update_native_retirement_windows.py --engine <client.exe> --symbols <client.exe.db> --feed <signed/update.json> --objects <objects-root> --objects <additional-objects-root> --runtime-root <task>/runtime-harness/subject01 --evidence <task>/artifacts/harness/subject01
```

Run the exact before pair separately with `--expect-before` and different fresh
roots. Before expectations explicitly require pending-only reduction, completion
unlink despite corrupt/held survivors, completed-attempt3 exhaustion, and acceptance
of duplicate/exec-mismatched rows. A before pass characterizes defects; it is NOT a
subject safety pass. Client/companion/feed and Python dependency hashes are retained
in `result.json`, and client/companion/source bytes are rechecked before PASS.

The feed must contain distinct signed crosshairs xhair1/xhair2, a local zone, and
`gfx/env/missingtexture.png`/`textures/no_texture.png` sharing hash/size. No new feed
is signed. Ordinary object stores are read-only inputs, not hardlinks or installations.

## Implemented native matrix (20 scenarios)

* Unique/shared/preserved, same-size corrupt and separate wrong-size corrupt stage
  cases in BOTH row orders. Ordinary valid deletion must ACT; shared pending hash
  must remain; exact full signed original tuples and attempt2 must survive partial
  publication. Released/repaired completion is a distinct launch.
* A seeded reduced-authority case cannot adopt its valid outside resolved orphan.
  A completed no-journal case cannot adopt orphan objects, `.part`, `.install`, or
  `journal.tmp`. These are seeded controls, not process-interruption actors.
* Held signed STAGED leaf: readable/writable same bytes, independently observed real
  `DeleteFileW` error32 with no-delete sharing. Admitted completion at attempt2 must
  persist attempt3; another valid stage deletion ACTS. Completed-attempt3 cleanup
  must repeatedly start nonfatally without bumping, retaining exact authority and
  held object. Released restart retires the survivor. Before lost-authority and
  completed-attempt3 refusal are explicit different predictions.
* Final journal leaf unlink denial: already-completed fixture avoids substituting a
  failed journal-replacement actor. All valid objects are removed; exact journal
  survives repeated startup and released restart removes it last.
* Unresolved attempt3, even with repaired valid stage, refuses before mutation.
* Signed tuple, duplicate path, exec mismatch, unsigned envelope, journal version,
  and malformed journal refusal with unchanged seed metadata/content/stage bytes.
  Before duplicate/exec acceptance must ACT; other refusals remain mandatory.

The independent oracle hashes bytes directly with BLAKE2b-256 and computes shared
pending identities from fixture bytes and protected-zone policy. It calls no engine
predicate or model method. It grades the entire selected signed content closure,
ledger/version/certificate, exact tuples/budget, protected bytes, entire stage map
and outside temp/siblings. Full seed and post-containment runtime inventories are
mandatory via unchanged guarded shared exporters. Every native phase uses unchanged
`cold_phase`: actual launch marker/error/exit, natural job0 before AND after cleanup,
full exported inventory, then an independent semantic receipt. Receipt failure
retains its guard. Native failures remain FAIL; failure evidence is exported before
bounded owned-runtime retirement, and unknown export/containment keeps runtime.

The signed mirror rejects every GET. Its final census occurs after serving-thread
AND accepted non-daemon request-worker joins; zero is signed-mirror scope, not all
network silence. Busy-port rejection acts before any client launch.

## Client-free validation and remaining gates

```text
set FTESURF_TEST_SCRATCH=<task>/tmp/harness
python -B -m unittest discover -s tools -p test_update_native_retirement_windows_unit.py -v
python -B -m unittest discover -s tools -p "test_update_native_journal*_unit.py" -v
python -B -m unittest discover -s tools -p test_update_native_staging_windows_unit.py -v
```

Component validation: 15 new tests, 81 unchanged journal tests, 13 unchanged
staging tests pass with no skips on Windows. The new tests include a REAL Windows
leaf delete denial/release, but NOT a native engine matrix. Independent byte actors
falsify missing full rows, unlink-before-purge, unsafe shared deletion, lost corrupt
objects, missing positive deletion, outside adoption, budget reset, false refusal
mutation and failed semantic-receipt writing. On non-Windows only the real sharing
unit explicitly skips; the native driver refuses to run there.

Parent `artifacts/inputs.json` supplies verified signed feed/object inputs. Native
before02 PASS: 20 scenarios / 35 cold phases against parent's exact caeb0b before
build (`build-before-02.json`), with full exports and natural job0. Before01 remains
FAIL: the harness incorrectly expected an already-consumed partial journal.tmp to
reappear on completion. Corrected explicit temp-lifecycle tracking and added a unit
regression; no safety predicate was relaxed. Before02 uses entirely fresh roots.
These before results characterize historical defects, NOT subject acceptance.
Subject01 PASS against parent `build-subject.json`: 20 scenarios / 35 cold phases.
Both matrices used driver SHA256 `a268cb9a32f9b0cd5b266adcd0eeb4faf34dd0b80278739a8c74b54e76eaa06f`.
Read-only raw audit confirms 70 natural pre/post job0 phases, 110 full inventories
and 496 raw metadata/log hashes total. Both owned runtime trees were retired only
after evidence confirmation. Subject client SHA256
`a15436d3233c64b96394e2245797c56023a469471a5719085b16c1d17850ec68`;
source/build provenance remains the parent's build receipt, not a deployment claim.
Logs, raw receipts, CLI argv, diff and ownership are under the current task's
`artifacts/harness/`. Fresh independent reviews9c262fb3/e63c887b accepted the
core source/oracle/raw evidence within its documented cold scope. Corrected source
`7321da290913f67c047f1cf86103203ad79327d05dbacb44fe7ca9da695ec5d3` and
client `b566bf46b17a2f7cb4e95599e2089ad7fabff4dc9397ac5bc982ed6210480596`
were separately rerun as subject02:20 scenarios/35 phases, same oracle; e63c887b
independently reviewed that exact rerun. Neither matrix is a partial-read native
failure control or permission to publish/deploy the engine candidate.

The parent-owned `tools/native_retirement_interrupt.md` separately adds real
first-removal pre/post interruption and repaired restart evidence; it is not an
implicit extension of the cold component's coverage.

NOT delivered by THIS cold component: source-bound actual-removal interruption debugger,
cold/deferred live before/after interruption integration, journal publication failure
extension, retained-generation/new-live-apply actor, launcher supersession/repair,
Linux, hostile ancestor swaps/hardlinks, file/directory flush or power loss. Existing
native debugger source was inspected but not broadened without exact source builds.
The parent's next gate is exact-source before/subject execution and fresh independent
source/evidence review; the complete eight-row protocol rollout remains larger than
this minimum cold gate. Preserve failed fixtures/guards/evidence rather than adjusting
new expectations to make the subject green.
