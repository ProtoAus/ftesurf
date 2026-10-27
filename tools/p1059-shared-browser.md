# P1059: text navigation and shared browser sidebar

## Change

Owner requested compact update info at screen-top-left, original bold white
floating navigation without any panel backdrop, no Music menu, and
Lobbies/Maps/Story/Event swapping the main panel while Friends/chat remain.

- One shared sidebar, including active poll scope across all browser pages;
  draft and profile/DM selection are not cleared by navigation.
- Native24/32 display-face white nav, no slab/chips; compact native12px note at
  screen12,12 outside the translated shell. Maps title is Maps, not play.
- Maps fills the entire remaining left canvas with128x72 thumbnails and20px
  native-size names. Narrow canvases use112px rows with separate metadata/time
  lines; normal rows80px. No filter/thumbnail/Friends switches or filter strip,
  even when the saved legacy Filters flag is1. Saved preference bytes untouched.
  Search still finds uncatalogued/untiered entries; its caption says searchable.
- Music entry/autoplay removed, not Windows-output visualization or its source
  opt-in. Existing search/metadata/build/launch/download/board and development
  update checks/gates are unchanged. No native/pin/tag/qcbuild/API/site change.

## Evidence and limits

Owned root `C:\FTESurf-worktrees\menu-20261026T1632Z`;
PLAN-shared-browser.md pre-registered the real-control/bounds falsifiers.

`shared-browser-smoke.py` reuses the existing Runtime/overlay/HTTP entrypoints.
Public map metadata/atlases are read-only fixture inputs; fake account/mode data
is not linked-account authority. No private friend/message data or send occurs.
All HWND/input commands target only the owned runtime; no owner process stopped.

Initial candidate `artifacts/shared-browser/subject-a7d2501267`: all15 page swaps
across exact1280x720,800x600,1920x1111, populated Home/Story/Event, actual map row
selection, invariant sidebar and unsent draft retained. Screenshots inspected.
The saved owner Filters1 flag then required retiring its old strip as well.

Final candidate:
`9acf4b6c5b183faf1d8b319ac6f3c7b8447530dc3231e9a93ccea985219a230a`
(578654 bytes), `artifacts/progs-shared-browser/menu.dat`.
Final populated fixture `subject-df0f8a23be` passed all four pages at all three
sizes with Filters1, invariant sidebar, bounded full-size map list, real row
selection and preserved draft. The final1920 Event->Home click did NOT act:
real desktop mouse motion moved the hover from732,105 to439,1093 then431,1127;
separate down/up both reported took0. Retained as a failed input-driver arm,
not a pass or product attribution. Fourteen valid populated arms were reused.
`home-return-recovery.json` restored only that owned fixture's known links and
proved the missing Event9 -> Home0 callback/sidebar bounds with one atomic
NUMERIC ui_click. No replay of the14 valid arms or forged data/clock evidence.
The recovery checks only the missed callback, not populated data or draft.

NoDeploy server/menu0 warnings; same two untouched CSQC setproperty227 warnings,
zero new. QuakeC is compiler/runtime verified, not an LSP proof. Full native,
authenticated Friends/DM send, all-platform, and owner feel are not claimed.

## Independent outage/audio requests

Read-only Pi checks:12 actual lobby units ACTIVE, API8084 connection refused,
public /health502 and the separate maintenance generation's admission CLOSED.
Lobby1 public UDP27510 answered the status request; that is not full gameplay
acceptance. Existing guard owner must restore/handoff the supported serving
path; no unguarded worker, data/guard edit or service/process mutation was made.
Non-lock canonical tools/menu-backend-recovery-request.md records the request.
No backend/site promotion is implied by this local menu patch.

Both installed clients expose loopback/source/status controls. Saved source1,
reactivity1/menu1 and no production cfg source override were found. Owner supplied
snd_vis_status source1 supported1 active1 available1 packets27416 rms0.000000,
then closed the game. That proves active capture/packets with analyser silence,
not disabled support, capture recovery or a proven native bug. Actual audible
music/default endpoint and a focused known-audio control remain to diagnose;
no raw audio is recorded and local opt-in/config bytes are not rewritten.
Track the outstanding falsifiers in BACKLOG.md/lextest.md.

## Delivery

Clean inspected source/build byte binding, exact dual menu-only install hashes,
UTC, adjacent rollbacks and current protected-state preservation are recorded
separately at the actual boundary. No native/server/gameplay-progs/config/consent/
ledger swap. Owner look/normal navigation remains pending; source/staging and
unique evidence retained, generated copies/links retired only after verification.
