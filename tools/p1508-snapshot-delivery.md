# P1508 — bounded QuakeWorld snapshot delivery

## Scope and status

Implemented, independently reviewed and deployed on 11 November 2026 UTC to
both Windows installs and all twelve lobbies. Both native builds and the acting
CPU controls pass; destination hashes and live lobby actors/plugins are verified.
Human confirmation of the reported save/load failures remains pending. No QC
Build number or release-package decision is made here.

This repairs a demonstrated server packet-delivery defect. It is a plausible
lead for the reported prediction errors and `msg overflowed` warnings, not proof
of Mark's exact load/reset problem, rare game exit, or a client crash fix.

## Problem and change

Replacement stats could exhaust space needed by mandatory client data/entities.
Discarding an overflowing local snapshot could then clear pending stat/entity
updates without delivering them. Reusing an unacknowledged frame slot also needed
explicit recovery before its counters were retired.

- Prepare and diff every replacement-stat seat before side-effectful client data.
- Serialize mandatory client data once, measure its bytes, and reserve those
  bytes plus the shared entity-admission threshold and negotiated prefix on the
  same snapshot-capacity ledger. Reclaim optional reservation only when needed
  for essential admission; preserve the final optional append/drop policy.
- Requeue explicit locally discarded/current or unacknowledged stale frames.
  Preserve the existing sequence check for ordinary network-loss recovery.
- Preserve source-phase priority, wire order, stat encodings and legacy/NQ flow.
- Account for the complete six-byte voice header before admitting its payload.

This does not guarantee that a variable-size entity payload can never overflow,
change independent transport discard behavior, or undo every QC side effect
already consumed before a later discard. No movement, recorder, verifier,
evidence-policy or protocol-format change is claimed.

## Source and qualified images

Windows/main source: `041181a7be42c5e75cf869e626af0b2b8598e7b3`,
`patch-1508`, stamp `git-8695-patch-1508-0-g041181a7b`.

The Pi actually ran the separate p1383-arm source
`90979d61c875ab7aa9bf9c285eb115ee007e7c76`, not engine main. Its minimal backport
is `0c293d5404348f16699e953fc4e88a9f2e211494`, `patch-1508-arm`, stamp
`git-8490-patch-1508-arm-0-g0c293d540`. Unrelated later main changes were not
copied to the fleet. The affected send/entity code and CPU fixture match main's
canonical Git blobs.

| Image | SHA256 |
|---|---|
| Windows client | `4b6c6cf817d170a30179fbd8765bc29034f5333ebce5692b89ca7c5e411d9bf2` |
| Windows dedicated | `3ecf2adb1c8ea6b7607c3ad63e6125b3e7da258884dec7890082fd40fd36f046` |
| Windows HL2 | `ef684f9001e32a01e2d5580886d83c046ecc4890b799a0230ba718a90b4ee206` |
| ARM dedicated | `cb85fcfc87593a64701641447637f9ffc2e601a33a1b571e6d0c8ad9fc5f9fc9` |
| ARM HL2 | `4d16a6e47383f3c911fd147b9d14863e8e21c0c836161942f75ec26fb433e4e6` |

## Verification and limits

- Existing native CPU scheduling controls: 44 checks, zero failures. Actual
  production datagram/drop/ACK/budget seam: 15 checks, zero failures. Literal
  pre-fix source passes the original 44 and fails exactly the nine intended
  delivery controls. Numeric/string updates are observed on later wire output,
  not inferred from silence. Split seats, stale slots, optional voice and
  legacy/NQ exclusions have acting controls.
- CPU transport, client-data and entity/PVS services are bounded doubles. This
  is not a real-client packet trace or measured latency/performance result.
- Full Windows client/dedicated/five-plugin build passes. Native diagnostics
  have exactly the prior qualified 74-warning payload multiset: zero new.
  All three production QC VMs compile with zero warnings, but those validation
  outputs are NOT a QC deployment in this native-only operation.
- Actual fresh old ARM source and candidate both compile server/HL2 successfully:
  identical 16 server plus one HL2 warning payloads, zero new. All source archive
  members match canonical Git objects before transfer and after compilation.
- ARM old/candidate each execute 1,608 positive numeric checks, zero failures;
  all 90 named full-content physics rows match across six maps. Prop-piece,
  wrapped-path and differing ride-path controls actually act. Approved historical
  compatibility controls pass under both images in a separate archived world;
  this is not current-world evidence admission.
- Windows old/candidate each execute the same 1,608 positive checks; all 90
  complete named physics rows match one another and the frozen ARM rows exactly.
  Both historical compatibility controls also pass under both Windows images.
  Actual module listings bind the unchanged image/plugin paths; earlier current
  listings hide the system path, so full-path binding there is transitive from
  the same-image historical runs, not a claimed earlier PID observation.
- Both platforms use the frozen current production QW for current-world gates,
  not the separately compiled validation output. Content file sizes/hashes and
  common config inputs are checked; output equality is not a claim of a complete
  cross-platform live-zone byte census. Historical worlds remain separate.
- Human save/load/camera acceptance remains PENDING in lextest.md. No actual
  client/server network trace, visual/feel or rare-crash fix is claimed.

## Delivery

### Windows — deployed 11 November, 18:12:04–18:12:08 UTC

- All ten default native destinations across both installs match the frozen
  qualified images. Each new `.prev` matches its actual pre-promotion current
  bytes. All twenty current/prior-previous preimages were individually read
  back from their retained archive and size/SHA256-verified before any target write.
- Executable stamps and DLL metadata contents identify the clean main build
  shown above. All 16,430 entries in the bounded protected inventory are equal
  before/after, including protected programs, configs and player-data inventory.
- No QCC, progs, config, player-data or nondefault native-extra promotion; no game
  was killed, paused or launched. This is native delivery, not a new release.

### Pi — deployed 11 November, 19:03:35–19:09:55 UTC

- Only the minimal ARM dedicated/HL2 pair was swapped. Both destinations match
  the qualified hashes above; both `.prev` files match actual prior current
  bytes. Original native UID/GID are retained without Root or ownership changes.
- Complete preimages of four native current/prior-previous files, nine recorder
  parts and 207 resume members were independently verified off-box before
  staging. Every member's bytes/size/hash and archived metadata were checked;
  exact source nanoseconds/identity metadata remain in the hashed inventories.
- A real live recording initially refused preparation. Its extra open/changing
  part was not ignored or copied as a closed file. After scoped coordination,
  actual empty/closed checks again matched the complete original preimages and
  actor births; no evidence was redated or preservation requirement waived.
- All twelve lobbies restarted, none skipped. Each live dedicated image matches
  the qualified hash, with the actual new HL2 inode mapped. Independent readback
  at 19:13:21 UTC reconfirmed every new actor and plugin, both destinations and
  both previous-image hashes. The rollout changed or lost none of the 58,271
  preexisting protected inventory entries; four new files were reported.
- Current progs/configs and backend generation/files remain unchanged. The
  rollout's sweep lock was released. No player-data restore, forced empty-room
  assumption, source-tree rebuild or automatic verifier downgrade was used.

The inherited-group restoration guard was corrected only after the actual
owned-setgid-parent capability was demonstrated; original UID/GID checks,
created-stage checks and identity-owned rollback remain enforced. Earlier
caller/reader/preflight refusals remain historical failures, not regraded passes.

The actual server packet-delivery fix is now available for the reported case.
Rejoining and retrying the same location with `cl_sl_leadin 0` was requested as
the small human check. Its result, rendered camera behavior and rare-crash
coverage remain pending in `lextest.md`; live deployment alone does not prove
Mark's exact cause or a measured end-to-end latency/performance improvement.
