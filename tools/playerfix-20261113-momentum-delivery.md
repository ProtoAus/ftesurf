# 13 Nov 2026 — known Momentum map-set delivery

This records the development delivery for the fixed, previously admitted set of
589 Momentum maps. It is not a fresh census of every Momentum map, a release,
proof that every upstream map is still public, or in-game acceptance.

## Delivered and checked

- Both Windows installs have the 589 exact selected BSP builds and their 589
  client-format zone files. These existing full hash/byte checks were reused;
  the later R2 work did not rewrite those files.
- **587 BSP aliases are R2-verified and gateway-ready:** current canonical source
  signatures, sizes, SHA256 and immutable object keys agree. This includes
  `bhop_marathon`. The delivery registered 69 previously missing aliases, then
  refreshed four existing source-stale aliases through the selected SDK API.
- **586 zone aliases are R2-verified and gateway-ready.** Of 204 outstanding
  candidates, 203 passed fresh public/current-build-and-zone eligibility, full
  remote byte/hash verification and a full decoded public download. The other
  candidate was correctly held for upstream zone drift. Previously verified
  383 zone aliases were not redundantly downloaded.
- The existing image publication has 2,411 accepted original images and 641
  thumbnails copied/checksummed. Every selected map has its primary preview or
  a verified alternate. Eight existing full HTTPS image readbacks are sample
  evidence, not a claim that every upstream gallery image is available.
- The already-public normalized map-info table is now also on the existing
  static R2 destination: `ftesurf/media/mapmeta.txt`, 271,442 bytes, SHA256
  `d4c4c2513b25cd0fdb1b5b0e16245c6269228a8f04f88260da095ce9c797455f`.
  It has 2,844 total rows, including all 589 selected maps. One immutable copy
  and one full remote byte read/hash passed at 09:49:25 UTC. It uses short
  metadata caching, not the images' immutable-year policy. This did not reroute
  the existing public metadata URL, which continues to serve the origin table.

### Real R2 download follow-up

Initial public GETs can legitimately use the origin while the gateway's
asynchronous object probe warms. At 10:14:28 UTC, one later BSP request and its
zone request for `df_new2defrag` each followed one HTTPS redirect to R2 and
returned the exact decoded source bytes/SHA256 (176,076 and 523 bytes).
Redirect locations and signed URLs were not retained. This verifies a live R2
route for those two samples, not fresh readbacks of all aliases.

### Compression is a policy result, not a savings claim

The existing BSP gzip policy evaluated the new/refreshed bodies and correctly
skipped them; no new gzip objects or measured savings are claimed here. Zones
have no current gzip-companion policy. HTTP content encoding is not evidence of
an R2 gzip companion. Original images were not recompressed destructively.

## Explicit holds and remaining work

- `bhop_anomalous`: the observed current API status was outside the allowed
  public statuses. Its stale pending BSP/zone rows were not republished or
  relabelled ready. No meaning beyond that refusal is inferred for the status.
- `bhop_haddock`: no admitted canonical BSP/site zone. Its import still depends
  on the existing parked source-census transaction. Neither a client-side zone
  nor a cached census was substituted to bypass it.
- `bhop_kairos`: BSP ready, but its current API zone hash differs from the frozen
  site/protected/client zone. The old zone was not published as current. A new
  source qualification and the supported admission path are needed.
- The Native lobby metadata cache still lacks Kairos. A whole-table replacement
  would also change unselected rows, so it was not performed. A generated finite
  row/dependency candidate is being checked separately; it is not deployed by
  this record.
- Image sample checks and file availability do not establish visual/gameplay
  acceptance. The fixed set does not establish the complete authenticated
  testing universe or the availability of every optional gallery image.

## Source and preservation

The exact-selection SDK change is feature commit
`e4e1d1a87f178d860dfabee312cbba0a02fd8988`, merged in
`ea96309d8b9c39377210b751d939e3479d9954c0`. Selection still validates the full
configured inventory/floors and atomically changes only the explicitly selected
aliases; it is not a global catalogue scan.

Each publication used the existing SDK's source-stability and full-remote-hash
path, not manual SHA/signature/state SQL. Actual all-column unselected rows and
schemas were preserved across each short mutation window. Source files, SDK
configuration, unrelated data, services, cron jobs and running lobbies were not
changed by these R2 transactions. Temporary parts were absent and owned
processes were reaped. Private operational receipts retain the detailed UTC,
source bindings, row snapshots and limits; they are not public artifacts.

This is content/tooling delivery documentation. It does not claim an engine
patch, Build-number decision, optional-movement acceptance or release.
