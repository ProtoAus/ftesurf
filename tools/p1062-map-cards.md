# P1062 — glass scenes, visible filters and map cards

## Problem / change

Owner follow-ups to P1059: keep actual map filters, remove only their collapse
button; fix Quit; larger Play/card presentation; green Complete fade with your
WOS/overall times and WOS/overall WR; translucent windows over MilkDrop with
section-based scenes. Quit compared a function pointer instead of calling its
synthetic-input guard.

- MENU alone opts into tinted glass while Milk is active. Both background layers
  blend; text stays opaque/native-sized. CSQC/HUD defaults and opaque fallback
  remain unchanged. No new native shader or renderer feature.
- Main/Maps/Story/Event/Settings select profiles0..4. Settings reuses shader0 with
  a separate pose/palette; profile4 never asks the renderer for nonexistent S4.
  The map's full-size JPEG no longer covers active Milk.
- Always-visible native12 Tier/Mode/Library/Extra chips measure/wrap. Same IDs,
  filtering and saved options; no collapse button or forced owner config.
- Wide128px/compact160px cards,160x90/128x72 thumbnails, larger Play/Download
  actions, separate metadata and four labelled native-size time cells.
- Complete is a known qualifying clean MAIN finish. A64-strip non-overlapping
  green fade avoids the first preview's double-alpha seams. Unknown is not false.
- Existing `/api/board` gains bounded `cards=` batches (16 cleaned names maximum),
  before its single-player dispatch. Same public identity/rate bucket; native
  build vs imported base scopes. Ranked WOS vs ranked+Momentum+KSF minima only,
  track0/leg0/styleclean. Local/community PBs are not relabelled as these records.
- In-memory per-identity cache, visible rows only, one request in flight,60s
  refresh,30s failure wait,12s deadline. Preserve cached timestamps on error;
  integer JSON/itos avoids float32 millisecond drift. No disk cache, raw IDs,
  evidence authority, schema/consent change or per-row network requests.
- Quit calls `ui_synth()`; the synthetic-input refusal remains. Remove the
  remaining Music entry from Settings, without disabling native desktop capture.

## Verified

- NoDeploy build: MENU/server0 warnings; same two untouched CSQC227 warnings,
  zero new. QC build number and native commit/tag pin stay unchanged.
- `python surfd/test_mapcards.py`:17 synthetic SQLite/Flask-route checks; all four
  minima, exclusions, variants, identity/unknown/unlinked cases, null vs false,
  invalid/oversized requests, integer2096300012. No live DB or packets.
- Existing `surfd/test_completion_pool.py`:46 checks0failed;
  `surfd/test_board.py`:328 checks0failed.
- Real-client matrix800x600/1280x720/1920x1111: five browser swaps and Settings,
  scene/glass0..4 acted, four integer times/Complete/import-only/incomplete acted,
  tier really filters and resets, at least one full compact card, bounded batch,
  sidebar/draft/selection preserved, Music entry absent, Milk-off opaque fallback,
  new uncached offline rows queued but emitted no HTTP.20 screenshots inspected.
  Runtime uses the existing `tools/test_ui_maps_runtime.py` transport/overlay;
  task driver and evidence retained under the documented owned menu task root.
- First map-card test passed functional checks but Windows logging blocked fixture
  cleanup; explicit logging shutdown fixed it. The first fade preview's overlapping
  strips were corrected and visually rechecked. Failed evidence was not relabelled.

## Delivery / limits

MENU-only dual Windows installation follows clean committed verification; no
native/client/server progs or player/config/content/updater files are shipped by
this feature. The new API source is tested but its live serving generation is
still held by guarded recovery; health/directory remain unavailable. Do not claim
real record values or deploy around that owner/gate. Basic API recovery must not
be held hostage to this optional new projection. No release or Build NN bump.

Human readability/feel, actual installed Play and real Quit remain explicit owner
checks in `lextest.md`; synthetic input must not be used to waive the Quit guard.
Authenticated social/send, real gameplay launch and numerical performance are not
claimed by layout fixtures. Native audio is separately under investigation:
video/default-output input is nonzero in paired capture, but the normal-sound
client's muted Windows session returns0. No native audio repair is part of P1062;
no owner session was unmuted and no raw audio recorded.
