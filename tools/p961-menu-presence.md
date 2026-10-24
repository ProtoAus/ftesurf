# P961 — game-running presence before joining a map

Status: implemented, isolated builds pass and independent follow-up is OK with
notes. The initial P1 freshness/P2 budget findings are resolved. Native source
88a95f339db14caef0c0fcfdae48ed96e0fae569 / patch-961 is published; QC source is
recorded by feature6b9c90a6. Exact clean Full/NoDeploy Jobs1 passes:3VMs with
zero warnings,7freshAMD64PEs/5valid resource ZIPs,74inherited/zero new native
warnings. The final native actor verifies list/join/presence signatures, invalid
target refusal and new/legacy menu rows; original old-refusal control is retained.
Native source tag is patch-961; actual Makefile stamp is
`git-7778-patch-954-3-g88a95f339` (HEAD-count+29, annotated-tag ancestry and exact
clean source hash). The public lightweight source tag is NOT falsely substituted
for that compiled stamp or rewritten. Development delivery is VERIFIED:
24Oct2026 15:03:35Z live readback verified the matching schema22 Social backend;
15:21:41Z verified the qualified MENU/LNO in BOTH Windows installs. The service
handoff preserves all80 runtime inputs except the two reviewed Social files,
all historical values/bindings and the native/reader dependencies. It does not
restart the game fleet. The separately approved ordinary QC rollout compiled
all3VMs/0warnings and verified all12new epochs, hashes/predecessors and29,850
unchanged existing files16:51:08Z. Native/reader dependencies and runtime80 stayed
unchanged; no native/backend/AI action. A later independently published peer
cohort superseded those program hashes; it is preserved, not rolled back.
17:00:29Z current fleet readback and17:06:26Z source/cold-client review verify
published9b353d16, the same intended eight-field Friends modules, all12fresh
sockets/directory and matching actual network CSQC. Both Windows retain the newer
published P970 native/program/shader/cache cohort and matching C3 menus, with
14,618protected files unchanged. No downgrade or second restart by this task.
Do not confuse deployed source/transport with real two-person/human acceptance.
P954's separate native cutover was verified earlier09:52:46Z, not reused here.
Number961 claimed after fetching both repos and checking patch headings AND
untracked pNNN/test_pNNN files in canonical/owned trees (max960). The unpublished
P959 working label yielded to existing canonical peer959/960 claims before any
commit. Historical tests/reviews retain that label; implementation is unchanged.

## Contract and predictions, registered before implementation

A linked installation with accepted online/privacy settings sends a ten-second
MENU heartbeat while disconnected. The native MENU-only signer gains the explicit
`presence` operation in the existing first-party Friends domain; list/join proofs
cannot publish presence. No account/link consent, movement/recorder/collector
signature or input/evidence API changes. Connected lobbies remain the preferred,
joinable location. Main-menu presence is visible ONLY to mutual friends and has
no address or Join action. Saved friend names must not save active presence.

One additive schema21 table holds pub/linked-account/seen/challenge-expiry only.
No session capability is minted. Expired rows are removed on heartbeat; a replayed
or older challenge cannot renew the lease. SQL-backed state must work across
workers. Short-lived identity/presence metadata, not chat history or run data.

Falsifiers/control arms:

1. A genuine signed presence request acts; list/join substitutions, wrong signature,
   bad challenge/peer, unlinked and banned keys act on no presence row. Old native
   refuses the new operation; new native signs it and still handles list/join.
2. Same/older challenge replay does NOT advance seen; a fresh challenge does.
   The heartbeat expires after35s, even if an old proof is replayed later.
3. Other worker/connection sees the same row. Relink/ban/block/revoked friendship
   hides it immediately. Incoming/one-way adds reveal no app-running state.
4. Genuine lobby presence wins. Main-menu activity cannot produce a join address;
   a join against menu-only presence refuses with a useful message.
5. Privacy off, demo/connecting/connected state or missing builtin never publishes
   menu presence. Hidden main menu still heartbeats; late callbacks cannot post
   after cancellation. Timeout/backoff does not block Friends list/join.
6. Both connected CSQC and disconnected MENU display Main menu as active without
   Join. Old six/seven-field rows default to no menu presence; cached names have
   none; stale data is not current presence.
7. Migration20->21 is additive; existing data unchanged. Build3VMs with zero new
   warnings; existing Social suite and focused controls pass. Native diagnostics
   and actual client/signing smoke required; LSP alone is not native acceptance.

Required owner acceptance: two linked friends, one at main menu and one in a lobby;
confirm Main menu appears, no Join is offered, and closing/privacy-off expires it.
Main-menu shared chat and DMs are separately implemented/deployed under P963;
real two-person/visual acceptance remains pending.

## Current verification / first-review fixes

- Existing native/build entrypoint succeeds; all3VMs compile with0warnings.
  Two actual native actors: old refuses presence, new produces a verified Friends-
  domain presence proof; both still sign valid list/join and refuse bad targets.
  Actual MENU parser handles new8-field and legacy6-field rows.
- 53Social tests pass, including actual additive20->21 migration/idempotence,
  replay non-renewal, key/relation revocation, shared SQL, private/non-joinable menu
  presence,50s of controlled heartbeat/unchanged-poll replies, and combined NAT
  traffic (two accounts,24interactive +12background requests/minute).
- P1: successful unchanged polls now send a private `friend_end <snapshotHash>`
  confirmation. CSQC renews ONLY its matching completed snapshot and publishes
  MENU's epoch; partial/cleared/wrong snapshots and failed polls cannot renew.
  This reuses the existing command channel and retains16s stale behavior.
  The actual production QC helper acts in an owned native VM: controlled40s
  healthy after confirmation,20s without confirmation stale; wrong hash/loading/
  cleared refuse. This is a controlled-clock unit arm, not full end-to-end UI or
  wall-clock/performance acceptance.
- P2: presence has separate bounded30/min peer and20/min account budgets;
  interactive limits and the SHARED global240/min verification ceiling remain
  unchanged. Combined normal traffic passes; exhausted presence budgets do not
  block interactive lists. Peer/account caps still refuse excess requests.
- Retained first varargs warnings, wrong test-helper name and native-probe compiler
  path failure are not passes. No owner identity/data copied; only owned actors
  stopped. Final clean build/native proof passed as recorded above; service and
  Windows MENU and full fleet producer delivery are verified; owner checks
  remain pending. The328ebfa1/d76c82fe rollout changes only the two Friends modules
  from P967 composition9b2db0c1 and preserves the newer save/rewind fixes.
  Initial Windows promotion refused a real concurrent native upgrade before
  any mutation; Pi-only used the existing supported entrypoint, then retained/
  verified the newer Windows cohort rather than overwriting it. One fresh client
  downloaded current CSQC, loaded and drew cols9/type14 with no QC error, exit0;
  screenshot inspected. Its original old-hash smoke assertion remains a failure
  caused by the later peer rollout, not relabelled as a pass or rerun. The same
  actual download/render evidence matches the independently verified current
  cohort. Terms were not accepted: no live ranked-board query or human chat pass.
