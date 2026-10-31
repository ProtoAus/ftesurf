# P1140 TAS sharing/browser — development-fleet delivery

## Pinned source

- QC: `d182bf3989a047575b4ef10439af12d820004c3a`.
- Native: `2ddb4fe130463ea8e9035f2dffce35d56b2193e1`, `patch-1140`.
- Served CSQC SHA256:
  `713bbd93e58387730e539ca910cede8fe4022886b230f8b9bae1dc8b2f4a26a7`.

The final independent namespace review is clear. Clean full native/QC builds and
acting native transfer, normal-load, retained/recovery-file and lifetime controls
qualified these exact sources. Home-enabled Open is deliberately fail-closed;
the normal FTESurf manifest disables home. See [the client contract](../tasrev.md).
The frozen qualified artifacts were copied without a rebuild. No Build-number
bump or public-release publication was performed.

## Actual deployment and readback (UTC)

- **30 Oct2026 23:56:10:** both Windows installs received22 exact frozen native,
  plugin and generated progs/LNO artifacts through the existing deploy function,
  only while idle. All22 destination hashes and exact `.prev` predecessors pass;
  1499 protected configuration files remain byte-identical. Player data was not
  a deployment target. No owner's process was killed.
- tasrevd's append-only released-code file received exactly the approved CSQC
  hash. All old bytes remain an exact prefix; owner,0600 mode and inode are
  unchanged. The actual live service environment points at that file and reads
  codes per request. No service restart, schema or nginx change was needed.
- **31 Oct2026 00:08:58:** existing paired no-force promotion updated native/HL2
  plus QW/CS progs on all12 positively empty Pi lobbies. All12 restarted, none
  skipped; new native process images and mapped HL2 inode/hash bindings pass.
  Live and `.prev` hashes match the prepared four-file set and predecessors.
- Before any restart, all4 existing part payloads (1,426,033 bytes) were archived
  against the exact prepared inventory and individually verified off-box. No
  unknown-completion part was excluded, restored or declared disposable; all12
  lobby actors had no open part descriptors at the archive boundary.
- A fresh isolated client copied from the installed Windows native build joined
  a real lobby with no local CSQC. It downloaded the exact hash above, drew the
  board's empty state (9 columns/type14), captured a screenshot and quit normally
  without QC errors. This is not populated-board or human visual acceptance.
- **31 Oct2026 00:17:08:** after that client left, all12 new actor epochs and
  native hashes still match. All35,837 prepared old protected entries, including
  all original parts, remain unchanged: zero changed/missing, no exclusions.
  Protected configs and backend generation/dispatcher hashes remain unchanged;
  the canonical sweep lock is released. Exact predecessors and prior-`.prev`
  bytes are retained for a guarded rollback, not automatic downgrade of a
  potentially generating fleet.
- Public HTTPS directory GET returns the expected map/schema response. The
  checked map has no published revisions; no real-account project was uploaded
  merely to manufacture acceptance.

## User-visible scope and remaining work

Local TAS practice now has explicit share, current-map browser, informational
contribution ranges and protected download/open through the normal project
loader. Share does not sign automatically or recursively publish private parents.
It does not confer human eligibility, a verified finish/time or board admission.

Real-account linking, a physical Sign click, first public Share and rendered
Shared/Open acceptance remain pending in [lextest.md](../lextest.md). The canonical
native-VFS runtime qualification, enabled queue/TAS board,10ms profile, remaining
optimizer and editor work are still part of the overall TAS task. This delivery
is progress, not a claim that the entire TAS project is complete.
