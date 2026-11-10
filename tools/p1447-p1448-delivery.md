# P1447/P1448 paired backend and lobby delivery — 10 November 2026 UTC

## Implemented, verified and deployed

- The ordinary guarded backend activation completed at **00:24:39 UTC** with
  primary generation `bf18baf8c88731e44d3eb37dca37587abba59cde` OPEN. The previous
  generation and the new conservative fallback remain CLOSED. Actual readback
  found health OK, 12 registered lobbies, and normal request routing restored.
- P1447's viewer and P1448's Fetch Python/web/importer changes were included
  **together**, as requested in the former backend-pending handoff. Requested
  application source: `d108206ac690c69d4e187759ae5d8be6dae9675f`; the generation
  retains inspected existing runtime bytes outside that requested ship set.
  The explicit 85-file runtime profile and three external readers were qualified;
  this is not a claim that every retained runtime byte came from that Git tree.
- Activation preserved the SAME CURRENT database inode, schema26, original
  44-table DATA policy and eight identity digests. Only the two declared optional
  queue tables were allowed; existing queue contents were protected. The real
  CLOSED actor passed namespace, dependency, health and ordinary-request refusal
  checks before its fresh acceptance receipt/reopen. No database restore, old
  grant reset, detector, threshold, ranking, tier or hardware-attestation change.
- The first attempt failed before either candidate started because staged private
  manifests had the wrong permission mode. The failed attempt remains failed.
  A same-inode/bytes permission correction and independently reviewed bounded
  phase continuation completed the primary, without replaying the original
  transaction or reopening its predecessor.

## Actual consumer checks

The public website is **https://proto.bar/ftesurf/board/**, not the unprefixed
`play.proto.bar/board/` path. A first check against the latter returned HTML404
and is not counted as application evidence.

- **00:53:23 UTC:** one real public-HTTPS Fetch on hosted `surf_voyager` returned
  `202`, `Cache-Control: no-store`, Momentum `queued`; KSF answered `unknown` for
  that leg. The unhosted-map control returned404. This proves enqueue/routing,
  **not** eventual upstream arrival, complete player-profile walks or UI feel.
- **00:57:50 UTC:** public `board.html`, `board.js` and `watch.js` each returned200
  and their full SHA256s matched the accepted runtime manifest. Strata rendering
  and perceived build speed remain the human checks in `lextest.md`; no new
  performance measurement or manual acceptance is claimed here.

## QC deployment

Clean inspected source `db9840ca0f76a15d25fdc874edb103c1010cfe6e`, qualified
P1412 compiler `73f9a1a4`, existing `src/build.ps1` entrypoint: all three VMs
compiled with **zero warnings**. The production build reproduced the frozen
`-NoDeploy` artifacts byte-for-byte. No native engine/plugin/config/release or
Build-number promotion was part of this deployment.

- All12 NanoPi lobbies were empty at the directory preflight and were restarted
  through normal `build.ps1 -Pi`, without `-PiForce`. All12 fresh actors retained
  the expected executable, CWD and arguments; native binaries and configs stayed
  byte-identical. Postflight **00:44:21 UTC:** health OK/12; deployed QW/CS SHA256s
  exact and `.prev` matched the immediate preflight pair.
- All198 enumerated recorder/resume preimages were archived and every member
  verified both on-box and off-box. These were individually bounded live-file
  prefixes, not a simultaneous closed-writer snapshot. Postflight found **198
  unchanged original prefixes, zero missing and zero changed**; no player-data
  restoration, deletion or broad recorder exception.
- Full authenticated server-info replies from **all12** lobbies at
  **00:48:05 UTC** advertised client checksum **`f87e7c2a`**, size **5,223,474**.
  Its SHA256 was appended once to the released-code allowlist, preserving all
  original entries and the inode (114 ->115 lines).
- **Pending:** the two local Windows DAT/LNO promotions are blocked by another
  session's shared fixture gate. No installed files or owner processes were
  changed to bypass that gate. Lobbies are configured to serve the new CSQC;
  the local menu copies must still be promoted and hash-verified.
  Actual client download/render/Fetch and human acceptance remain pending, not inferred
  from server advertisement or the website's successful request.

## Runtime retention and rollback

Retain BOTH trees below, including their runtime, control and state artifacts:

- `/srv/nvme/agent-work/ac-resume-20261109T0300Z-c2aa/http-admission/fenced-primary-seven/`
- `/srv/nvme/agent-work/ac-resume-20261109T0300Z-c2aa/http-admission/fenced-fallback-seven/`

Also retain predecessor runtime/control/state, original receipts and failed
attempt history. These are runtime/rollback dependencies, not disposable scratch.
Rollback is qualified code-only recovery against **CURRENT** data, never an old
DB restore, manual grant reset or fence reopening. Inspect actual launcher,
serving actor, admission and dependencies before any later operation; do not
repeat this healthy activation merely to refresh records.
