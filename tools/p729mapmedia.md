# P729 — map pictures, boot manifest and reviewed zone drafts

## Scope and verified result

- Audited 764 live-approved surf/bhop maps plus 360 cached public-testing maps:
  1,124 known maps, 1,124 actual XL originals, zero unavailable screenshots in
  that inventory. A fresh authenticated public-testing census remains unproved;
  the upstream endpoint requires login. No stored login was read/exported.
- Preserved originals and generated bounded 1920x1080 backdrops, medium images,
  name aliases and one same-map deleted-thumbnail compatibility alias. All
  4,497 public R2 JPEG objects were compared against complete local bytes.
- Larger offline atlas generation acted at 512x288, selecting adequate-size
  input rather than stretching medium images. The game remains 128x72. Nine
  missing cells were staged on a new page without moving existing coordinates.
- After integrating published P728, full native/QC build passed with zero NEW
  compiler warnings (existing warnings preserved). Media10, backend11 (real
  Ed25519), installer3 unit tests and recorder regression passed. The corpus
  reader is byte-identical to the inspected baseline; private corpus inputs and
  individual results are not published here.
- Native runtime: boot manifest GET acted before opening the picker; offline
  consent restart sent no manifest/lobby request; selected HTTPS image reached
  1920x1080 and screenshot inspection showed the photo. A changed valid curated
  file replaced an existing cache. Invalid polygon structure, nonfinite data,
  HTTP404 with otherwise valid geometry and HTML kept that changed predecessor
  byte-for-byte; saved-local bytes were unchanged. Download validation checks
  complete main/bonus/global geometry without touching active timer tables.
- Isolated native input/backend: synthetic confirmation was refused, native
  confirmation from a non-admin was denied, and a synthetic test admin stored
  the exact 44,643-byte saved file. Saved local zones and live account files were
  unchanged. This is not a real production role grant or public-service test.
- Dedicated SSQC arms: curated geometry loaded; saved-local geometry overrode
  it with a distinct geometry hash; invalid curated input plus a valid
  client-only download did not create authoritative server zones.
- NanoPi read-only preflight observed schema19, required Python modules, the
  real account DB schema, and free loopback8087. No main-app/schema mutation.

## Source and delivery state

Implementation verification is complete. Final inspected-commit builds and
Windows/fleet delivery are in progress; this paragraph must not be read as a
claim that the public upload endpoint is installed or any zone activated.

The owner's game is never killed/restarted. Native file locks are a per-file
blocker, not permission to stop independent progs/assets work. Fleet files may
be copied only from inspected source; occupied lobby restart gates remain in
force. Never use the sealed-main-app deployment path for the new service.

## Remaining owner/operational boundaries

1. The independent new draft service requires owner/root approval to apply its
   reviewed unit/nginx installation. Its helper defaults to dry run and verifies
   source, account schema, free port, process/listener ownership and HTTP source.
2. No live admin role was granted. Identity confirmation is not authorization;
   use a private approved-identity file only after explicit owner approval.
3. Uploads are drafts, not automatic publication. This preserves the owner's
   reviewed activation decision. Staging binds both explicitly reviewed zone
   and BSP SHA256; changed revisions and unsupported times policies refuse.
   Authoritative site/fleet activation and any hide/archive operation remain a
   separately reviewed action. Existing times are never silently changed.
4. Fresh public-testing coverage needs an authorized authenticated inventory or
   refreshed owner-supplied cache; cached coverage is labelled as such.

Operational overview: [mapmedia.md](../mapmedia.md), [zonepub.md](../zonepub.md).
Unique raw evidence, synthetic native harnesses and actual account/operational
output remain private. Retain originals and provenance; retire only explicitly
owned disposable copies, never canonical content/dependency trees.
