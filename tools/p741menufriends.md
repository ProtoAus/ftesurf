# P741 — Friends in the disconnected map picker

## Scope

The map-picker Friends panel now has its own read-only authenticated connection.
A linked installation can list friends, see their current lobby/map and click
Join before loading a map. Initial Steam linking still uses the existing real-
input account flow on a lobby. Menu graph edits, private messages, generic Steam
presence and automatic linking are not added.

The connected panel still consumes CSQC's completed private snapshot. The
standalone panel neither publishes presence nor makes a menu user joinable.

## Implementation

- Native MENU-only `friends_sign` uses the existing install key for a separate,
  fixed Friends statement. Only list/Join targets are accepted; no seed, lobby
  capability, receipt authority or account-link consent is exposed. Connected,
  connecting and demo states refuse.
- The fixed HTTPS origin cannot be redirected with `lobby_dir`. Requests need
  online consent even when that directory is empty, and run only while the
  Friends panel is open. Older engines show an update-required message instead
  of calling an absent builtin.
- Short-lived challenges bind the peer, operation and target. POST verification
  rechecks the current key link, ban, friend relationship and live presence.
  There is no menu session/token mint, presence refresh or graph/message/link
  mutation, and no new database schema beyond P722's existing schema20.
- Read-only proxy exposure is two exact paths, not a social API prefix. Trusted
  proxy attribution, bounded request/account/global rates, body limits and
  no-store responses are retained. The verifier honors `SURFD_TOOLS` and the
  existing `SURFD_GAME/tools` fallback rather than assuming a repository layout.
- Lists are staged atomically in private buffers. Join gets a fresh backend
  decision, applies the existing host/address gate and prejoin/download flow,
  and resumes a name prompt with the intended account rather than a row index.
- An app timeout or hide abandons intent, not the HTTP transport. One outstanding
  transport gates further Friends requests until its callback completes. Native
  MENU generations survive VM resets so an old callback cannot enter a new VM.
  JSON address handles remain integers.

## Verification

- Existing `src/build.ps1 -Engine -NoDeploy -Jobs 8` in isolated inspected QC and
  engine worktrees: all three QC programs report zero warnings. Native client,
  dedicated server and matching plugins build successfully. No new compiler
  warnings in changed native units; existing Makefile dependency-recipe and
  unchanged-source clang-tidy warnings are not reported as new feature warnings.
- `python surfd/test_social.py`: 30 tests pass. Real Flask/SQLite and synthetic
  linked keys cover genuine signatures, pending-request privacy, accepted Join,
  malformed/cross-domain/tampered proofs, target substitution, expiry/peer
  binding, ban/unlink/offline rechecks, no session/presence mutation, rate caps,
  trusted versus forged proxy headers, and a deployed (non-repository) verifier
  layout through both configured paths.
- Existing `test_accounts.py` and `test_board.py`: all checks pass.
- Actual Windows MENU VM/native key signing against an isolated real service:
  accepted private list contains an online friend and a redacted pending request
  while disconnected. A pointer-driven Join is revalidated and reaches a real
  dedicated socket. Native signing refuses there; the connected CSQC/menu
  snapshot path still renders. Screenshots were inspected, not just counted.
- No Friends network activity under either empty or populated `lobby_dir`
  without online consent, or with the panel hidden. A delayed challenge released
  after Hide produces no proof POST. Malformed native signer inputs refuse with
  an acted valid disconnected-signature control.
- A 91-second held challenge times out in the UI without queuing replacements,
  including hide/reopen and another request attempt. An unrelated healthy URI
  completes while held; release permits a fresh accepted list. A later native
  run reuses this unchanged transport evidence rather than repeating the delay.
- Delayed old-VM and current-VM HTTP requests deliberately use the same callback
  ID across `menu_restart`: only the current VM response is delivered. This is
  an acted generic callback-boundary test, not a claim of native HTTP cancellation.
- Two independent security/integration reviews. All source-backed blockers were
  corrected; the follow-up integration review finds no remaining issues in its
  inspected scope. Initial compiler/fixture/consent/teardown failures remain
  retained privately and are not counted as passes. The corrected native
  acceptance run passes every planned check.
- `tools/test_reccheck.py` passes. The installed recording corpus sweep remains
  at 190 preexisting faults; the reader is unchanged, and no evidence grammar,
  receipt, physics or replay verification semantics are modified.

## Delivery and limits

Source publication, clean-commit staging and Windows destination status are
recorded below after their actual completion; build success alone is not delivery.
The live public challenge probe returned HTTP404 on 2026-10-16. P722/schema20
Friends activation is still separately gated from P717's completed schema19
transition. Do not run an ordinary app reload to migrate that generation, reset
its guard/schema or fabricate live accounts to obtain acceptance. The authorized
controller must accept the complete schema20 runtime and preserved data, then
install/check the two public proxy locations and run genuine-account checks.

The native feature commit `23cbdc9a77dd04edbe6097bcfca817e6ce8ed5a9`
and annotated `patch-741` are published. The QC/menu/service source is the
feature commit containing this document. At source publication, neither normal
Windows installation nor the live backend has been changed by this task. The
primary normal client was running at the installation gate; no owner's process
was stopped. Exact clean-commit staging and any later destination verification
will be recorded as a separate delivery update rather than implied by this build.

Repeated explicit `menu_restart` can still leave prior native HTTP transports
outstanding, as with existing URI users; this patch does not provide process-wide
HTTP cancellation/timeouts. Physical owner input, genuine linked-account live
acceptance and crowded-fleet performance remain unclaimed. No public release,
QC Build/version bump, live lobby/progs swap or backend migration is implied.
