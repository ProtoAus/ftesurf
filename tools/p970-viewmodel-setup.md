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

## Delivery / human acceptance

The checks above establish implementation/component behavior, not the final
artifact's installation. Native tag/pin, clean role-compatible Windows builds,
dual-install hashes, matching account service/lobby deployment and provenance
must be recorded separately. `lextest.md` holds the pending small two-player and
linked-install owner checks. No Build bump or public release is part of P970.
