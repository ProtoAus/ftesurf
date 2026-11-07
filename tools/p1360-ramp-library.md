# P1360 - priority ramp-mark library and optional R2 delivery

## Feature and scope

One whole-map replay-baked atlas per map, including available main, stage and
bonus recordings. Reuses P1339's geometry format, shader and bounded
SHA256-checked on-request cache. P1362 fixes only the baker's tiny-radius
serialization; it does not relax the client. `r_rampwear` remains opt-in; no atlases
are added to game packages. No native pin/tag, VM, physics, recording/evidence
semantics or QC Build change.

Owner's source: <https://docs.google.com/spreadsheets/d/1Hft-1XdK7lge5WWqP5hrNsSUJw_Ss2PS-t-c3CTawpQ>.
Retained HTTP CSV bytes SHA256 (CRLF):
`091911e4dbcb7421b36207c9033fef51307d2b47a1bd5e5588b942ab553d4188`.
Repository `rampwear-priorities.csv` SHA256 (policy-normalized LF):
`277f985229cf288bbac56925737e5116976559afaa7ceb615e0f42f2e1eb83d1`.
Only line endings differ; the parser records both byte and canonical-LF hashes.
The raw HTTP snapshot is retained, not silently relabelled as repository bytes.
The parser preserves all280mentions /278distinct bonuses and both split-course
classifications. Explicit installed-revision names reduce174sheet map names to
173physical map names; it NEVER bakes a different revision's replay against a
BSP by aliasing the recording header. Pending, unzoned and broken-Momentum notes
remain source labels, not playability promises.

Scope combines that list, the original Story/Event roster and the100main boards
with the most held run records. This is a reproducible popularity proxy, NOT
measured play telemetry. The union resolves to307map names.

## Verified asset inventory

- **249 ready whole-map bakes**. Every candidate passes exact map binding and the
 ACTUAL client bounds: positive radii, at most32768charts/131072triangles,
 finite positions, unit-range UVs and normal-length tolerance,32MiB geometry,
 6MiB encoded transport, PNG dimensions, SHA256 and strict base64 round-trip.
- **94/100** popular main maps and **129/173** priority maps have a ready atlas.
- **196/278** priority bonuses have an indexed held exact-course input; **192**
 also have a ready map atlas. This conservative conjunction is NOT proof every
 ramp on that bonus was painted; full recordings can touch additional surfaces.
- `p1360-rampwear-coverage.json` preserves **58** explicit requested-map gaps:
 43without replay inputs and15without placed contacts. Existing served assets
 are not removed merely because a refreshed bake has a gap.
- The249 validated sets total **704,161,490 raw bytes** before HTTP compression.
 Raw/player-bearing input bytes and path inventories stay private. These are
 cosmetic assets, not native run verification or measured play/FPS evidence.

## Implementation

`rampwear_batch.py --maps MAPS.json` adds a frozen safe-name library scope beside
its unchanged Story/Event mode. `rampwear_priorities.py` refuses unknown sheet
cells/layouts, preserves duplicate classifications and reports course input
availability separately from map bake readiness.

R2 mirror/gateway allow only `<map>.txt`, `<map>.<64hex>.png` and its `.png.b64`
transport under the existing public ramp path. PNG keeps its native compression;
geometry and base64 get gzip companions, fully read back/decompressed to the raw
digest before readiness. Range/non-gzip clients retain raw bodies. Existing
map gzip stays FTE-only. Dedicated ramp raw/gzip ledgers leave the map/zone ledger
untouched; missing/stale/unverified sources, failed R2 probes and a dead gateway
keep the current disk fallback. No raw recording can enter these groups.

## Verification

- Qualified c24ede65 compiler: all3VMs build with0warnings using the documented
 `build.ps1 -Jobs 8 -NoDeploy`; both real Windows installs untouched by this build.
- Windows: 25 mirror, 22 gateway, 11 gzip, 3 priority, 4 raster, 3 cosmetic replay-reader tests
 pass. One POSIX-only gateway symlink case is skipped on Windows, not a pass.
 ARM mirror/gateway/gzip: 25/22/11 pass with no skips, including the actual link refusal.
 The optional bounded transfer workers overlap transports (a two-party barrier
 proves they acted), retain a single ledger/process lock and per-worker SQLite
 connections, and still reject corrupt bodies/invalid worker bounds. Default1
 preserves serial behavior; per-worker rate limits must budget aggregate load.
 Initial new gzip concurrency tests had only one seeded row and an ineffective
 fake-corruption attribute; those FAILED fixtures/logs are retained. Corrected
 two-row/actual-body-corruption controls pass unchanged readiness assertions.
- Actual ARM unprivileged nginx/gunicorn and actual R2 preflight: public map/zone
 regression, all3ramp formats, gzip response metadata and decoded hashes,
 signed HEAD, byte-range206, private/listing/missing refusals, source replacement,
 dead-gateway fallback; all29acting checks pass, owned processes exited.
- Full originals exposed two oversized encoded atlases: Classics6,722,004bytes
 and Overgrowth2 6,837,296bytes, both above6,291,456. Coarser texels reduced them
 to4,974,776/5,101,536bytes; exact world XYZ/normal/chart-structure hashes match.
 Console texel values were rounded, not exact old numeric settings. No surfaces
 or client limits were dropped/raised to pass.
- The earlier delivery qualifier omitted the actual positive-radius predicate.
 Consumer-source inspection found Sinsane2's43radii serialized as0.0; its retained
 predecessor already had40. P1362 changes exactly those43tokens to0.1, with every
 header/other chart/triangle/UV/normal/image token identical. All249final sets
 now pass the actual predicate. Earlier weak-check output/refused bytes remain.
- A late source exporter reused `a` for argparse and fstat, failing before its
 manifest. The failed archive was retained. Body-only salvage then exposed a
 second staging error: known-body caching suppressed154required raw sidecars.
 Those are OUR FileNotFoundError failures, not absent upstream recordings. The
 exact retained bindings were recovered, the exporter corrected, and only14
 affected maps rebaked. Final missing-sidecar failures:0. Batch exit1 for explicit
 no-input/no-contact gaps is the documented partial result, not `bake_failed`.
- The first R2 preparation exposed credentials loaded from rclone rather than
 inline keys, then an SSH PATH without rclone. The same state/failed row was
 repaired by reusing the existing qualified mirror binary. No failed transaction
 was renamed or regraded. A wrong Python helper name was corrected to the existing
 CLI; no production activation was claimed by those failed preparation calls.

## Reproduce / refresh

```
python tools/rampwear_priorities.py --sheet tools/rampwear-priorities.csv --out PRIORITIES.json
python tools/rampwear_batch.py --maps MAPS.json --inputs PRIVATE_INPUT_LIST_DIR --gamedir OWNED_ASSET_DIR --reports OWNED_REPORT_DIR --workers 4
```

Inputs are frozen JSON lists per exact map, cosmetic-only and private. Read the
workspace/operations contracts first. Publish hash-named PNG/base64 bodies before
atomically replacing a map manifest; retain previous manifests and digest-bound
rollback. Scan the PUBLIC asset directory only, then use existing r2mirror and
r2gzip entrypoints with a separate ramp manifest/state. Verify actual public
HTTP hashes after activation, not merely upload status.

## Delivery and acceptance status

First wave is DELIVERED, not the whole requested end state. At05:52:03UTC7Nov,
723files for241fresh bakes were destination-hash verified:144new maps and97
refreshed manifests, with3older-only assets retained. **244map manifests LIVE**.
Actual public geometry GET/hash checks passed for Gigapede, Android KSF,
Beginner, Tensor2 and Hades2. Gateway code/config was installed05:55:13UTC from
67bd89e1. Owner ran the guarded root nginx activation06:05:27UTC; the inspected
predecessor and rollback are retained. Actual public3-format R2 redirects,
no-store, gzip decoded hashes, raw PNG hash, byte-range206, unchanged map/zone
routes and private/missing/listing refusals pass. The unrelated globe/chat MIME
warnings point to untouched snippets and were not repaired as part of this task.

The first pass selected a small set per course/style. The final full-source
snapshot at **06:59:05UTC7Nov** supplies **30,800held input files**:10,240rawKSF
and16,147rawMomTV originals,3,814Momentum/1KSF converted fallbacks only where
originals are absent, plus598native cosmetic inputs. All4,676local MomTV files
remain default bake inputs too. There is NO per-course/rank/style cap. The
existing reader rejects938entries (926ValueError/12FormatError); those are NOT
counted as successfully used recordings. This is a frozen availability snapshot,
not a promise that every upstream recording ever created was discoverable.

Ordinary paced missing-bonus interest:83unique boards,69acknowledged202 and14
unknown to the cached KSF leg inventory. Three429s were retried only after their
Retry-After window. Acknowledged/queued is not downloaded or painted; unknown
cached legs are not proof no replay exists. The ordinary importer retains its
locks, pacing/backoff and preservation rules; an attempted normal tick correctly
refused while its existing worker held the lock. No guard was bypassed.

Expanded data was first published07:23:35UTC (741files,247sets). Its transport
sync completed07:37:23UTC, but that receipt is NOT client-format acceptance:
Sinsane2 was restored only to our exact retained predecessor during the radius
repair. The final **249 qualified sets** include the corrected radius and paired
source inputs. Corrective generation `f20bf9b33c92c2eb`, source
`ade32eb035cd8ba89c0d8052a450b4e58eff1820`, published only11changed map sets
(33files:9replaced manifests/2new) at **08:00:22UTC**. **250map manifests LIVE**:
249newly qualified sets plus1older retained asset. Destination hashes of ALL
249sets/747files matched at08:01:57. The complete qualified index SHA256 is
`fc59535950d31b2da6ce44bba09c5c5143c0ca14090ffaf5b6f7b202123ededb`.

Corrective R2 refresh completed **08:02:55UTC**. Status08:09:26:all1,440allowlisted
raw bodies verified (595PNG,595base64,250geometry),845verified gzip companions,
0errors; these counts include retained hash-named history, NOT a single client
bulk download. The actual client `RW_BASE` is **play.proto.bar**. All9required
public HTTP checks there completed08:07:02:raw/gzip geometry for Sinsane2,
Happyhug and Overgrowth2; gzip base64/decoded PNG, raw PNG, raw byte-range206,
and signed no-store R2 redirects throughout. An EXTRA non-contract proto.bar
probe then returned404; that original dual-host controller failure is retained,
not called a pass or silently relabelled. Consumer-source inspection confirms
play.proto.bar is the game URL, and the9completed actual-host checks are reused
without repeating them just to fix the test's overbroad host scope.

The engine documentation commit is `b34b3021bdb054ad19ea39aefdea5ac9bf01be2d`.
Native pins/VM installs/qcbuild89 remain unchanged. Ordinary origin fallback,
previous manifests and immutable packs/indices remain available; Sinsane2's
predecessor has invalid zero radii and is history, NOT a valid native fallback.

The existing on-demand client needs no rebuild/restart for added assets. On the
current map, `rampwear_download` explicitly refreshes a copy already tried in this
session; `r_rampwear 1` enables the opt-in effect. Normal consent/download controls
remain. Native appearance/FPS, every bonus surface and owner visual acceptance
remain unclaimed.

Evidence roots: `C:/FTESurf-worktrees/rampmarks-01a1b058` and the paired private
root; NanoPi `/srv/nvme/agent-work/rampmarks-01a1b058`. Retained runtime/rollback
ownership must remain documented; never blanket-clean these roots.
