# P1360 - priority ramp-mark library and optional R2 delivery

## Feature and scope

One whole-map replay-baked atlas per map, including available main, stage and
bonus recordings. Reuses P1339's unchanged baker, geometry format, shader and
bounded SHA256-checked on-request cache. `r_rampwear` remains opt-in; no atlases
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

- 241 ready whole-map bakes; every published candidate passes exact map binding,
 finite geometry/counts, client surface/triangle/file/encoded-size bounds,
 PNG dimensions, SHA256 and strict base64 round-trip checks.
- 92/100 popular main maps and 124/173 priority maps have a ready atlas.
- 195/278 priority bonuses have a held exact-course input; 186 also have a ready map
 atlas. This conjunction is explicitly NOT proof every ramp on that bonus was
 painted.
- The exact frozen coverage is `p1360-rampwear-coverage.json`:66requested maps
 remain missing-input/no-placed-contact gaps. Do not count an absent file, an
 unreadable input or no-contact bake as a pass. Existing served assets are not
 removed when a refreshed bake has a gap.
- 241 validated file sets total 483,884,196 raw bytes before HTTP text compression.
 Raw/player-bearing input bytes and path inventories stay private. Public assets
 contain only cosmetic geometry and atlas data, not a native-verification claim.

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

The first source pass selected a small set per course/style. The user asked for
ALL recordings possible, so an all-original expansion is running before final
completion:30,636held bound input files, including10,086rawKSF and16,137rawMomTV
full recordings, converted fallbacks only where originals are absent, plus598
native controls. All4,676local MomTV files also remain default bake inputs.
There is NO per-course/rank/style cap in this expanded snapshot. Ordinary paced
missing-bonus requests use the existing public importer queue; queued is not a
completed download or painted surface. Final coverage/size counts remain pending.

The existing on-demand client needs no rebuild/restart for added assets. Native
appearance/FPS, every bonus surface and owner visual acceptance remain unclaimed.

Evidence roots: `C:/FTESurf-worktrees/rampmarks-01a1b058` and the paired private
root; NanoPi `/srv/nvme/agent-work/rampmarks-01a1b058`. Retained runtime/rollback
ownership must remain documented; never blanket-clean these roots.
