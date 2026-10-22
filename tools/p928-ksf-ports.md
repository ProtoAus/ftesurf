# P932 - KSF Watch on configured Momentum map versions

## Problem and boundary

The board already shared imported times across explicit map-port families, but
hid their recording IDs. Watch then refused differing map names, and simply
relaxing admission would still stop playback on the next frame. A downloaded
recording also lived under its actual source map, while a second lookup used the
board's map and fetched it again.

This is observational playback, not a claim that two BSPs, physics or recorded
runs are identical. Only configured families are allowed; suffix resemblance is
not permission. The recording retains its actual source header/hash and imported,
unknown-build, not-native-verified status. Native and Momentum playback fences,
verification eligibility and replay-serving bounds are unchanged.

## Implementation

- `cl_mapports.qc` accepts a bounded family from a successfully parsed board, or
  explicit `of` links from the same persisted map list/freshness choice used by
  the menu. Endpoints/root must be unique and the root unlinked. Unknown names,
  malformed/chained/duplicate relationships and oversized input fail closed.
- The original KSF loader and normalized Watch admission use the same policy.
  The explicit original-file source binding is still required. Existing binary
  layout, finite-value, marker, size/frame, style and bonus limits are unchanged.
- Watch keeps the source map separately from the approved loaded-map lifetime.
  Playback advances on that loaded map and stops after a map change. Non-KSF
  recordings retain their existing source-map lifetime behavior.
- The board exposes existing scoped recording IDs, KSF-only actual row maps and
  family metadata only for tiers containing KSF. Watch/board lines share the
  actual-source cache hint, preserving the existing stage-parent leg-zero hint.

## Verification

Supported `src/build.ps1 -Jobs 8 -NoDeploy`: server, client and menu compile with
zero warnings. Final source includes the independently reviewed correction to
the raw loader's earlier exact-map gate and its declaration ordering.

`tools/p928ksfports_smoke.py` reuses the existing retained-overlay/dedicated-socket
harness. Three actual-client actors provide 25 acted cases:

- Linked subject: 10 cases. The genuine retained Leacon Chateau-fix recording
  opens on Momentum Chateau and advances **10.0000 -> 11.0865**. Its original
  KSF binary advances **10.0000 -> 11.0538**. Source-map and unverified labels
  remain. An explicitly counterfactual exact-header recording advances too.
- Legacy control: 9 cases using the actual deployed P922 client program. Linked
  original/normalized inputs refuse, while the exact-header counterfactual
  advances. This proves the controls acted rather than merely showing silence.
- Unrelated, suffix-only, missing source/binding and raw-unrelated/missing cases
  finish closed with cursor released. Native map mismatch keeps its old warning
  and frame-time stop; it is not claimed as an admission-time rejection. A real
  loaded-map change clears the allowed recording.
- JSON/network/cache subject: 6 cases with deliberately empty owned map lists.
  The same linked input refuses before board-family metadata arrives; after an
  accepted fixture board it and the original binary advance. A real local HTTP
  download publishes byte-identical input under `surf_chateau_fix`; repeating
  the row fetch uses that cache, with exactly one replay GET overall.

The retained linked screenshot was inspected: course/rendered playback, clock,
source `surf_chateau_fix (linked build)` and imported/not-verified labels are
visible while the loaded map is `surf_chateau`. This is not owner feel acceptance.

Backend `test_ksfgrab.py` and `test_variants.py` pass. The optional
`SURFD_BASELINE_MODULE` variants contrast uses the same tiny fixture and synthetic
response clock: six native-only responses (three maps, ranked/community) are
byte-identical, while an old-masked/new-exposed KSF replay control acts.
`test_reccheck.py` and `test_ksfreplay_info.py` pass.

Native reader and held-metadata parser bytes are unchanged. A fixed-input
old/new sweep of 419 REC and 136 VIEW reports exactly the same 283 faulting
reports/284 diagnostics, with zero differing fault lists. The earlier captured
405 REC/120 VIEW corpus is a different dataset: a first absolute-count comparison
correctly failed and was preserved, not used to exclude or reclassify new files.
No native faults were repaired or hidden by this playback change.

## Evidence limits and delivery

Initial test transport used the reserved P925 number; concurrently published
P926/P927 were integrated before the P928 proof build. Published P929-P931 then
advanced while those tests ran; final product metadata is P932. The only later
production-path overlap adds the committed weapon module declaration after the
replay modules; the six functional policy/cache/backend file hashes are unchanged.
Old P925/P928 artifacts and this transport file retain their original names/times. The first completed subject actor was regraded, not rerun,
after fixing a harness assumption: successful `Watch_Status` prints owner/clock,
whereas the explicit open/on tuple exists only in its closed branch. An initial
online fixture decoding error stopped before any actor; explicit UTF-8 fixed it.
Two independent source reviews plus a fresh raw-finding resolution review pass.

No separate frame-only counterfactual binary was needed: advancing playback with
source and loaded map still distinct directly falsifies the former frame fence.
This is not an exhaustive every-map/style/stage/bonus runtime matrix. Those paths
share the policy; their existing decoder/cut logic was not changed. KSF top-up's
separate exact-source queue bug remains tracked in BACKLOG.md, not claimed fixed.

## Development delivery and concurrent-update preservation

Main feature `3a8d2427` is published. Its clean supported build installed the
DAT/LNO sets in **both Windows installs**, retaining predecessors and leaving
native binaries/plugins/config/player data unchanged. Actual installed online
and warm-cache controls passed. Later mainline Windows work is not rolled back.

The Pi needed the existing REC13-compatible producer cohort, not full mainline.
An exact rebuild of published P931-compatible `2ec17923` matched the then-live
pair before adding P932. Clean compatible `240440a4` was delivered by the normal
empty-fleet `build.ps1 -Pi` at **2026-10-22 18:44 UTC**: all12 new processes,
unchanged native mappings,562 configuration hashes and27757 pre-existing data
size/mtime pairs. Older `.prev` bytes were retained separately before the normal
predecessor swap. Neither Windows install was touched by that Pi operation.

A concurrent P933 rollout then replaced this with P933-only `ae3eb28f`, which
explicitly excludes P932. A real cold-client readback caught the replacement;
publication or an earlier deployment is not evidence of what a later client runs.
The integrated source is **`1fdb668a2ad5253282b08cd45d2f8da7eff60456`**, merging
both inspected compatible branches. Its five replay-policy/cache QC files are
identical to P932 and all three Friends files to P933. Its SSQC is byte-identical
to the current P933 program (`9e0bde1c...`); recorder/shared/native sources and
producer qualification remain unchanged. Three VMs compile with zero warnings.

At **19:39 UTC**, readback already found that exact integrated pair and12 new
processes, so our predecessor guard correctly refused an unnecessary second
promotion. This is an observed promotion, not a claim that our second builder
ran. At **19:42 UTC** a fresh spectator-requesting real lobby connection actually
downloaded integrated CSQC **`86096e49550ae9f1851b7d36d5ee443e3bc16f8db0d909d046a4974dba4aca17`**
from the server; that version was not preseeded. Its unrelated-map raw fence
acted closed with cursor released. The same compiled bytes in an owned dedicated
Chateau fixture advance genuine normalized/raw input **10.0000 -> 11.6602 /
11.8010** and clear the native mismatch. These wall-clock/no-trace controls are
separate acceptance: the original combined frame/trace arm's frozen-clock
assertion is retained as a failure, not relabelled a pass. Both crossed
client/server isolation arms also passed their ten controls.

The schema20 code-only backend successor was measured/published at
**19:08 UTC** with the ordinary guarded receipt, all seven entrypoints/four cron
routes and12 heartbeats. All existing reader/native consumer bytes were retained;
no evidence policy or eligibility changed. Actual game API readbacks of both
`surf_chateau` and `surf_chateau_fix` expose the same197 KSF rows, explicit
family and Leacon replay21517 under its real `surf_chateau_fix` source. The
actual replay response equals the retained qualified playback input byte for
byte. The public HTTPS board also returned its exact expected page with200.
A subsequent social-only backend handoff belongs to the concurrent P933 rollout;
that rollout must preserve this P932 `surfd.py`, not restore the old masked one.

**Preservation contract:** do not deploy historical P922-only `94d74f14`,
P932-only `240440a4` or P933-only `ae3eb28f` over the integrated current cohort.
Keep both features; backend social updates must likewise retain P932's existing
recording-ID/source/family behavior. Reinspect actual source/hash and occupancy
at the final boundary, not only before a long preparation phase.

No release, Build-number bump, native binary, engine pin/tag, BSP identity or
evidence-policy change is part of P932. Human-only confirmation remains PENDING
in lextest.md; this is not a claim of exhaustive every-map compatibility.
