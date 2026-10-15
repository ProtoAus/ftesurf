# Momentum map pictures and latest-zone downloads

## Inventory and originals

`tools/mapmedia.py` unions the live approved surf/bhop API (including native
mode matches whose names lack a surf_/bhop_ prefix) with all readable Momentum
MSML caches. It validates pagination and refuses an empty/incomplete approved
census. Public-testing access requires an upstream login: testing entries here
are **cached coverage, not a fresh authenticated census**. No login is harvested.

The October 16 audit contains 1,124 maps, zero without an available image, and
1,124 preserved XL originals. One deleted primary thumbnail was recovered from
another screenshot of that same map; its original CDN identity is retained.
Compatibility aliases are derivatives, never invented XL originals.

Create an owned task root and OWNER.md under the documented workspace layout
before running these examples. `$Task` below denotes that root.

```powershell
python tools/mapmedia.py --output "$Task/archive" --fetch
# Retain archive/catalogue.json and coverage.json with the immutable originals.
# A separate larger export, regenerated without network access:
python tools/mapmedia.py --offline --catalogue "$Task/archive/catalogue.json" `
  --seed "$Task/archive" --output "$Task/larger" --width 2560 --max-bytes 1048576
```

Existing valid originals are reused. New XL downloads are bounded/decoded before
promotion; HTML/error bodies are not pictures. Every result records sizes and
SHA256. Missing/failed originals make the command fail rather than imply complete
coverage. Keep the original archive: a 128px atlas cannot reconstruct a larger
thumbnail.

## Atlas generation

```powershell
python tools/mapthumbs.py --gamedir "$Task/game" --images "$Task/archive" `
  --coverage "$Task/archive/coverage.json" --fill-missing --report
# An OFFLINE export, with a separate copied input mapmeta.txt:
python tools/mapthumbs.py --gamedir "$Task/export-game" --images "$Task/archive" `
  --coverage "$Task/archive/coverage.json" --cell-width 512 --report
```

The current game/milk atlas contract remains **128x72**. 256/512px output is an
explicit offline layout, labelled `game_compatible: false` in layout.json; do not
deploy it over the game's atlas/table. Larger cells choose an adequately sized
source instead of upscaling the medium derivative. `--fallback-images` can supply
an existing picture directory for maps outside the Momentum archive.

`--fill-missing` appends new pages, leaves existing cells/pages fixed, and never
removes old pages. `--start-page N` must exceed referenced pages; a deployer must
also account for physical existing pages. Stage against a snapshot of each
install's metadata, verify that only missing coordinates changed, publish the
new pages first, then replace the metadata only if its input hash is unchanged.
Do not edit player data or re-pack a live install in place.

## R2 and the selector

The public prefix is `https://dl.proto.bar/ftesurf/mapshots/`. It contains actual
`<image-id>-xl.jpg` originals, medium derivatives, bounded 1920x1080 `-bg.jpg`
backdrops, and `<map-name>.jpg` backdrop aliases. Aliases allow maps absent from
an older bundled metadata table to obtain a background.

Publish an explicit JPEG-only file list using **rclone copy**, never sync/delete.
Do not upload the local catalogue, private reports or player data. Verify all
published bytes (`rclone check --download`) and sample the public HTTPS origin.
The initial completed set has 4,497 JPEG objects. New larger offline derivatives
must NOT overwrite the default bounded runtime backdrops.

On a native engine with `drawgetimagesize_async`, selection starts a nonblocking
image load and draws the existing atlas until dimensions are valid. No error
texture is drawn for pending/failed images. Local large/XL files still work;
a bundled medium does not suppress the online backdrop. Old native engines and
offline users retain the local/atlas path. The async builtin preserves complete
HTTPS URLs; it does not change the legacy blocking image-size builtin.

The existing online consent is version 6. It discloses the boot manifest fetch,
selector image/zone endpoints, and optional admin draft submission. Boot manifest
refresh runs before the menu-focus gate but keeps the existing consent/rate/cache
checks. Inspect `ui_mapnet`, `ui_bginfo`, `ui_zoneprobe` after `menu_restart`.

## Latest zones

A selector download and local Play request the fixed public zone endpoint. Play
waits at most eight seconds, then continues using the installed predecessor/BSP
if the endpoint is unavailable. Refreshes are bounded, validated and promoted
reversibly; malformed/404 responses do not erase installed zones. Client-only
refresh does not reload an active nonempty timer table mid-run.

Precedence is saved local editor file > curated downloaded file > online layer
> client-only download (CSQC only) > BSP. SSQC never trusts the client-only layer.
Local edits are not overwritten. `ui_zonefetch <map> force` bypasses the refresh
cooldown for diagnostics, not validation or consent. Saved-zone uploads and the
separate review/activation boundary are documented in [zonepub.md](zonepub.md).
