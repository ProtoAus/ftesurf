# P1169 — map-list update waits outside connected gameplay

DELIVERED on both Windows installs: only MENU.dat and MENU.lno,4 targets total.
Native remains P1162/520; actual server/client programs54fc2f59/b3ef8935 and all
other generated/cache/previous bytes are unchanged. No lobby restart or backend
operation occurred. Exact already-installed P1168 menu8a3705aa,
including profile/time/course readers, is preserved rather than overwritten by
older P1162 UI. The public MENU input closure and official version defines
reproduce that entire installed program byte-for-byte.

## Behaviour

- HTTP itself was already asynchronous. The hitching part is MENU's synchronous
  map-list validation/save followed by a complete catalogue rebuild.
- Do not request or consume the directory list while connected. One bounded
  valid response arriving after connection is owned in a zone and queued; no
  CRC/tokenization/filesystem-save/catalogue pass runs then. Disconnection drains
  it once; revoking online consent discards a queued body.
- Callback/media catalogue notifications coalesce as dirty state. Rebuild only
  disconnected and menu-visible, preserving current cached rows during gameplay.
- Explicit catalogue reload, boot warm-up and wrong-build file probing are also
  held while connected. This is deliberately more conservative than just a
  running timer: practice, paused runs, spectating and ESC are protected too.
- No new worker thread mutates QuakeC strings, menu buffers or UI state. That
  state is not safe to parallelize. This change schedules work outside play;
  it does not promise no other source of frame-time spikes.

## Actual controls and evidence

Official NoDeploy build:0server/0menu warnings; existing2clientF333. Only MENU
will be installed; generated server/client outputs are explicitly not deployed.

Actual private Native520 listen world, original installed SSQC/CSQC, local HTTP,
2179-row delayed response, real ARMED then RUNNING timer witness:

- Candidate6f8760a5: client2/state5/queued106787, no saved file or WOS rebuild.
  Forced refresh sends no second HTTP request. ESC plus explicit catalogue path
  preserves cached rows; timer remains RUNNING.
- After disconnect: client1/state2/rows2179/queued0/dirty0, all2179 rows saved and
  catalogue applied. No QC/native error; owned actor exits/rig lease released.
- Exact old installed8a3705aa under the same schedule saves/rebuilds DURING the
  actual running timer. The control exposes the original boundary, not a forced
  throw or a test that merely passes when no work occurs.

Failures retained in same fixture: direct public-source mirror initially missed
transitive include; next byte mismatch isolated to development vs0.1.33 literal.
Same compiler plus official MENU defines exactly reproduce8a. The initial GUI
teleport preceded QW spawn/begin and was overwritten, so it correctly failed its
RUNNING witness. Same fixture now waits actual begin and ARMED, not idle-as-pass.
No new name, fake request status, expected empty value or altered product gate
was used to get green. One failed build-list selector did not launch a compiler;
normal official build on the same changed MENU source succeeded.

No numerical frame-time, all-HTTP-worker, hardware input, GPU geometry, ranked
finish or human-feel acceptance is inferred. The older HTTP-worker close cost
in BACKLOG is separate, not claimed fixed. Raw receipts remain in the same owned
task's maplist-idle evidence; private data/config backups are never published.

## Final installed checks

Both actual installed native/menu/HL2+ImGui fresh private joins downloaded the
unchanged expected lobby CSQC, drew boards cols9/type14, captured screenshots,
exited0 and reported no QC errors. Before promotion a complete CURRENT15818-file
configuration/data archive plus52 generated/previous preimages was captured and
verified. After both cold joins all15818 protected files,224cfg and the complete
archive match. ALL non-target native/server/client/cache/previous images match
before. Only4 MENU/LNO targets changed; generated previous menus8a retained.
The caller initially lacked the registered snapshot parent; it failed BEFORE
any before/preimage/archive creation. Log kept; same parent marked owned and
same before phase succeeded, not a new namespace or protection reset. Source
branch/pin published; own actors exited/lease released. Human UX/hitch check
remains in lextest.md; automated deferral is not subjective acceptance.
