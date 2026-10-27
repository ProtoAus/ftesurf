# P1070 — readable lobby cards and early sharp photos

## Problem and change

Home stretched128x72 atlas thumbnails.12px title/count text was anchored near
one end of a card and its map name near the other. A catalogue miss could also
be cached before catalogue loading.

Large cards now group16px lobby titles and map names with14px player counts
around their centre. Compact cards retain two-line/compact layouts and all
full-card join/hover targets remain. Grid sizing/count/fit is unchanged.

Up to16large cards can use local photos or the existing public960px web-photo
route as soon as the lobby directory supplies a valid map name, without waiting
for catalogue UUIDs. Prefer existing small local photos; retain atlas/no-image
fallbacks. Online consent and map-name validation gate remote requests. Native
async readiness prevents missing/error textures from being drawn. Probe local
files only on map/consent changes, share identical photo URLs and release stale
references. Native image download limits are NOT raised or bypassed.

HTTP URLs belong in a named shader's image map, not in a cachepic/material
filename. The source uses a fixed trusted HTTPS route and an explicit diffuse
map/default2d shader. No native, API, schema or player-data change is required.

## Verified

- Isolated existing build.ps1 -NoDeploy -Jobs8: MENU/server0warnings; exactly
  the same2old CSQC F333/227 warnings in untouched cl_viewmodel.
- Real documented public web route: surf_kitsune JPEG200,960x540,32681bytes,
  public max-age86400. Wrong R2/root routes were rejected, not treated as images.
- Native baseline/control: real fixture directory12/12, no sharp-photo requests;
  native baseline reproduces small/separated text and no catalogue photos.
- Native subject at actual1920x1111:12/12cards,12ready960x540photos drawn at
 183x103, only6distinct transfers for duplicate maps, each once. Last join-card
  hover target acts. Control/subject lobby crops inspected.
- Rotate one card to an unknown photo:11ready, safe fallback, one failed request
  without a retry storm; the shared former URL is not redownloaded.
- Downgrade consent: the offline-choice control acts, no new photo requests.
- Fixture uses string-lump-only loopback origin substitutions, not altered
  instructions/defs or production social traffic. Raw logs/screenshots remain
  private; public crops contain synthetic lobby data only.

## Preserved failures and limits

Early helper assertions incorrectly assumed equal origin lengths and that the
baseline contained the new photo origin. A foreign dedicated process briefly
blocked the existing runtime gate; it was never stopped. An unavailable loopback
socket was not reclaimed. Corrected routing uses full IPv4 and same-length full
photo-prefix replacement, rather than relying on shorthand127.1.

A137719-byte synthetic JPEG correctly failed the native131072-byte download
limit. The fixture was corrected to quality72/82841bytes, matching the web-photo
generator; the native limit was preserved. A zero-new-warning build alone did
NOT count as photo acceptance. Direct URL-as-cachepic is also retained as a
failed product approach, replaced by the actual native image-map transport.

This verifies fixture UI/rendering and the existing public photo resource, NOT
production startup latency, FPS, subjective legibility/feel or every map having
a photo. Live/default-Milk owner acceptance is pending in lextest.md. Catalogue
absence and unavailable/oversized photos still have intentional fallbacks.

## Delivery scope

MENU only. Native pin/tag remain P1066, qcbuild89 is unchanged. No lobby/server,
backend, recorder/verifier, config, installed-list or player-data update is
claimed. The separate native/backend lobby rollout and stats/times/completed/
zone-publish work remain pending and are not completed by this UI patch.
