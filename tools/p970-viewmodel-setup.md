# P970 — linked workshop setup and actual followed-player viewmodels

## Contract

`src/shared/sh_viewmodel.qc` and `surfd/viewmodel.py` share a version1 numeric
setup: enabled, fixed catalog knife/hands/layer IDs, arms visibility, finish,
seed/scale/rotation/fade/wear, handedness, bob/sway, general/Legacy weapon FOV,
muzzle-flash/sound settings and workshop position. It is cosmetic configuration,
not inventory, executable paths, bindings or movement/recording state. Catalog1
IDs are append-only; unknown versions/IDs and non-finite/out-of-range data refuse.

The account route uses the existing proven lobby social capability, never a
caller-selected account/GUID. Schema23 adds one table without rewriting account,
run or link history. Saves compare revisions; stale writes refuse instead of
silently replacing another connection's setup. Corrupt/unknown rows remain intact.
Client load generations and dirty snapshots preserve newer local edits.

Public setup replication omits workshop position. First-person rendering uses
separate effective values and transient shader parameters, not the observer's
archived cvars. Authoritative weapon/event/mode stats and a bounded inspect
counter/variant drive the followed model. Third/free/replay cameras and a disabled
target cannot fall back to the observer's model. Mounting watched missing content
cannot change the observer's selected knife. The workshop still edits OWN choices.

`FTESURF_VIEWMODEL_FOV` / `VF_VIEWMODEL_AFOV` (227) is scene-local:0 restores
normal settings, -1 inherits world projection, positive values below180 choose
weapon projection. It neither replaces world FOV nor writes archived preferences.
The matching compiler knows the scalar property; rebuild the compiler as well as
the client after updating its type table. Engine-header changes require Full.

## Recorded checks

- Native Full Windows build succeeds at Jobs1 with the existing74-warning
  baseline. Jobs8 exhausted available memory; no owner's process was stopped.
  All three QC VMs compile with zero warnings using the matching compiler.
- `cd surfd; python -m unittest -q test_social`:65 tests pass, including valid
  proof/capability ownership, cross-account/token refusal, stale revisions,
  corrupt row preservation, the revision ceiling and additive migration.
- `cd surfd; python test_accounts.py`: all standalone account falsifiers pass,
  including the25-statement concurrent migration race. Run it standalone, not
  imported alongside another suite that changes the module search path.
- Actual dedicated socket with two clients: target Butterfly is ready; observer's
  OWN viewmodel is explicitly disabled yet watched setup renders. All transmitted
  render settings match and own preferences remain byte-identical. The independent
  weapon-FOV field reports68 while world projection stays at its previous value.
- Actual target input advances both shot counters; target and observer report the
  same `@lookat01..03` inspect clip. Third person and target-disabled hide the model,
  re-enable resumes it, and leaving spectate restores the observer's own M9/setup.
- Synthetic client-transport load controls preserve a newer seed555 against a late
  reply, then restore all21 fields from a clean validated load. This is NOT real
  account authority or a live linked-account round trip; route authority is tested
  separately with real verified-proof fixtures.
- Watched inspect and workshop/account controls were inspected in screenshots;
  no QC/shader/property errors. No owner acceptance, missing-content matrix,
  native QW tracking matrix or live cloud deployment is implied.

## Measured transport pitfall

QuakeC `tokenize(cmd)` splits commas as punctuation. An unquoted21-field setup
arrived as42 tokens and was correctly refused, leaving no public setup. Quote the
bounded CSV in EVERY console direction: setup publish, action publish, load,
saved and acknowledgement. `serverkey()` reads lobby capabilities;
`getplayerkeyvalue(-1, ...)` does not substitute for serverinfo. Positive socket
controls are required: a quiet log or zero-warning compile does not prove either
transport acted.

## Guarded schema23 preparation

The transition guard explicitly supports schema23 only when `viewmodel.py` joins
its exact dependency set. Older schema19/20/22 sets and the default19 are
unchanged. Schema23 has nine base hashes, or ten with explicit `hid-v1`; missing,
extra, altered or wrong-schema dependencies and receipts still refuse before
application import. No generation/schema rebinding or approval shortcut is added.
The POSIX transition and Linux candidate suites pass with actual synthetic
candidates for19/20/22/23, collector/viewmodel tamper refusal, ordinary import
controls, closure replay, forked lifetime and full drain. These are offline tests,
not authorization, product migration acceptance or live data-preservation proof.

## Delivery / human acceptance

Windows delivery verified24Oct2026 16:34:49Z: native source584b21bc / tag
v1.00-p970 and client source0c129e18 installed in BOTH Windows installs. All27
planned file swaps and rollback/history copies verify;14,659 protected existing
entries verify unchanged. Current approved eight-field Friends menu a283fe2a is
preserved, not replaced by an older seven-field menu. Client SHA256 ef252640c8ab,
native client ff8e38e45cc9. The final paired artifact controls pass18 checks;
an installed-primary-client/secondary-dedicated-server smoke passes four more.
Its first probe correctly failed before weapon-selection acknowledgement; the
corrected probe waits for actual selection before requiring ready/render/fire.

Pi lobby delivery verified24Oct2026: standard build.ps1 -Pi from clean9b353d16
(includes the published P971 retry safety fix) compiled all three VMs with zero
warnings and shipped server2b0a8c940dcb / clientef252640c8ab plus the two committed
knife shaders. Fresh positive UDP emptiness and exact predecessors were checked;
all12 actual systemd processes restarted, with expected cwd/native hashes and
positive QW sockets. Live/prev hashes and29,855 protected existing entries verify
unchanged (config hashes plus config/data metadata); native/backend/menu were
not changed. A fresh isolated client downloaded77cc3dcf.dat, byte-identical to the
qualified client; board UI/log/screenshot checks pass without QC errors. That
fixture has no online consent: its board frame is not online-times acceptance.

Cloud saving is NOT live. The active account service is still its sealed schema22
runtime; schema23 needs a separately reviewed additive migration/source-witness
handoff, including the new module. The existing exact schema20-to22 operator and
its historical review/consent seals cannot authorize or execute this new cutover.
No live database, admission gate or frozen witness was changed for P970.
`lextest.md` holds the pending small two-player check and, after backend delivery,
the linked-install owner check. No Build bump or public release is part of P970.
